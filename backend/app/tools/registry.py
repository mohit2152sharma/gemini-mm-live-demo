"""Tool registry compatible with the new BaseTool-style tool definitions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Mapping

from google.genai import types

from app.tools.all_tools import AllTools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

travel_tool = types.Tool(
    function_declarations=[tool.declaration for tool in AllTools.get_valid_tools()]
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _bind_tool(tool, session, queue) -> Callable[..., Awaitable[Any] | Any]:
    """Bind a tool implementation to the session/queue signature."""

    async def _run(**kwargs):
        result = tool.implementation(session, queue, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    _run.__name__ = tool.name  # For validator parity
    return _run


def create_available_functions(session, queue) -> Dict[str, Callable]:
    """Return mapping of tool name -> bound implementation."""

    bound = {}
    for tool in AllTools.get_valid_tools():
        bound[tool.name] = _bind_tool(tool, session, queue)
    return bound


available_functions: Dict[str, Callable] = {}


# ---------------------------------------------------------------------------
# Callback-based registry
# ---------------------------------------------------------------------------


class CallbackBasedFunctionRegistry:
    """Executes tool functions asynchronously and manages callbacks."""

    def __init__(
        self,
        session,
        functions_dict: Mapping[str, Callable] | None = None,
        tool_results_queue: asyncio.Queue | None = None,
    ) -> None:
        self.session = session
        self.tool_results_queue = tool_results_queue
        self.functions: Dict[str, Callable] = (
            dict(functions_dict)
            if functions_dict is not None
            else create_available_functions(session, tool_results_queue)
        )

        available_functions.clear()
        available_functions.update(self.functions)

        self.running_tasks: Dict[str, asyncio.Task] = {}

    async def execute_function_async(
        self, function_name: str, arguments: Dict[str, Any], call_id: str
    ) -> Dict[str, Any]:
        start_ms = time.time()

        if function_name not in self.functions:
            raise ValueError(f"Function '{function_name}' not found in registry")

        func = self.functions[function_name]

        try:
            result = await func(**arguments)
            return {
                "result": result,
                "status": "success",
                "function_name": function_name,
                "call_id": call_id,
            }
        except Exception as exc:  # noqa: BLE001 - bubble in payload
            logger.exception(
                "registry_execute_error", fun=function_name, call_id=call_id
            )
            return {
                "error": str(exc),
                "status": "error",
                "function_name": function_name,
                "call_id": call_id,
            }
        finally:
            self.running_tasks.pop(call_id, None)

    def start_function_execution(
        self, function_name: str, arguments: Dict[str, Any], call_id: str
    ) -> asyncio.Task:
        task = asyncio.create_task(
            self.execute_function_async(function_name, arguments, call_id)
        )
        self.running_tasks[call_id] = task
        return task

    async def _on_function_completed(
        self, task: asyncio.Task, call_id: str, function_name: str
    ) -> None:
        try:
            payload = await task
        except Exception:  # noqa: BLE001 - log and bail
            logger.exception(
                "registry_callback_error", fun=function_name, call_id=call_id
            )
            return

        result = payload.get("result") if isinstance(payload, dict) else payload

        if isinstance(result, dict) and result.get("status") == "PENDING":
            await self._send_pending(function_name, call_id, result)
            return

        await self._send_final(function_name, call_id, result)

    async def _send_pending(self, function_name: str, call_id: str, body: dict) -> None:
        if not self.session:
            return
        await self.session.send_tool_response(
            function_responses=[
                types.FunctionResponse(name=function_name, response=body, id=call_id)
            ]
        )

    async def _send_final(self, function_name: str, call_id: str, body: Any) -> None:
        response = body if isinstance(body, dict) else {"result": body}
        function_response = types.FunctionResponse(
            name=function_name, response=response, id=call_id
        )

        if self.tool_results_queue is not None:
            await self.tool_results_queue.put(function_response)
            return

        if self.session:
            await self.session.send_tool_response(
                function_responses=[function_response]
            )

    def start_function_with_callback(
        self, function_name: str, arguments: Dict[str, Any], call_id: str | None = None
    ) -> str:
        call_id = call_id or str(uuid.uuid4())
        task = self.start_function_execution(function_name, arguments, call_id)
        task.add_done_callback(  # fire-and-forget callback chain
            lambda t, cid=call_id, fname=function_name: asyncio.create_task(
                self._on_function_completed(t, cid, fname)
            )
        )
        return call_id

    def get_running_tasks(self) -> Dict[str, asyncio.Task]:
        return dict(self.running_tasks)

    def is_function_available(self, name: str) -> bool:
        return name in self.functions


def create_callback_registry(
    session,
    functions_dict: Mapping[str, Callable] | None = None,
    tool_results_queue: asyncio.Queue | None = None,
):
    return CallbackBasedFunctionRegistry(session, functions_dict, tool_results_queue)
