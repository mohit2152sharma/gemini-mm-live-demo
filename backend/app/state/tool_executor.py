"""
Tool Execution Manager for handling asynchronous tool execution.

This module manages the lifecycle of tool execution, updating the tool state machine
as tools progress through their execution phases.
"""

import asyncio
from typing import Callable, Dict

from google.genai import types

from app.state.tool_state import ToolStateMachine
from app.utils.logging import logger


class ToolExecutor:
    """
    Manages asynchronous tool execution and coordinates with the tool state machine.
    """

    def __init__(
        self,
        session,
        tool_state_machine: ToolStateMachine,
        available_functions: Dict[str, Callable],
        system_message_queue: asyncio.Queue,
    ):
        """
        Initialize the tool executor.

        Args:
            session: Gemini session for sending results back.
            tool_state_machine: Tool state machine to track execution.
            available_functions: Dictionary of available tool functions.
            system_message_queue: Queue for sending system messages to Gemini.
        """
        self.session = session
        self.tool_state = tool_state_machine
        self.available_functions = available_functions
        self.system_message_queue = system_message_queue

    async def execute_tool_call(self, tool_call) -> str:
        """
        Execute a tool call asynchronously.

        Args:
            tool_call: Tool call object from Gemini.

        Returns:
            str: Tool call ID for tracking.
        """
        function_name = tool_call.function_calls[0].name
        function_args = tool_call.function_calls[0].args
        tool_call_id = tool_call.function_calls[0].id

        # Note: Don't add UUID to function_args as tools may not expect it
        # The tool_call_id is already unique and sufficient for tracking

        # Register the tool call
        record = self.tool_state.register_tool_call(
            tool_name=function_name,
            tool_call_id=tool_call_id,
            parameters=function_args,
        )

        logger.info(
            "Executing tool call",
            tool_name=function_name,
            tool_call_id=tool_call_id,
            parameters=function_args,
        )

        # IMPORTANT: Send immediate PENDING response first
        try:
            # Get the bound function to call it for the pending response
            if function_name in self.available_functions:
                function_to_call = self.available_functions[function_name]
                # Call the function to get the immediate PENDING response
                pending_result = await function_to_call(**function_args)

                # Send the PENDING response immediately to Gemini
                await self.session.send_tool_response(
                    function_responses=[
                        types.FunctionResponse(
                            name=function_name,
                            id=tool_call_id,
                            response=pending_result,
                        )
                    ]
                )

                logger.info(
                    "Sent immediate PENDING response for tool",
                    tool_name=function_name,
                    tool_call_id=tool_call_id,
                    response=pending_result,
                )

        except Exception as e:
            logger.error(
                "Failed to send immediate PENDING response",
                tool_name=function_name,
                tool_call_id=tool_call_id,
                error=str(e),
                exc_info=True,
            )

        # Start background monitoring for system messages
        asyncio.create_task(
            self._monitor_system_messages_for_tool(tool_call_id, function_name)
        )

        return tool_call_id

    async def _monitor_system_messages_for_tool(
        self, tool_call_id: str, function_name: str
    ):
        """
        Monitor system message queue for messages from this tool's background task.

        Args:
            tool_call_id: ID of the tool call to monitor.
            function_name: Name of the function.
        """
        logger.info(
            "Starting system message monitor for tool",
            tool_name=function_name,
            tool_call_id=tool_call_id,
        )

        # Monitor for up to 60 seconds (adjust based on tool's background_delay)
        max_wait_time = 120  # 2 minutes max
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < max_wait_time:
            try:
                # Check system message queue for messages
                if not self.system_message_queue.empty():
                    try:
                        system_message = await asyncio.wait_for(
                            self.system_message_queue.get(), timeout=0.1
                        )

                        # Send system message to Gemini
                        from google.genai import types

                        user_content = types.Content(
                            role="user",
                            parts=[types.Part(text=system_message["parts"][0]["text"])],
                        )
                        await self.session.send_client_content(turns=user_content)

                        logger.info(
                            "Delivered system message from background task",
                            tool_name=function_name,
                            tool_call_id=tool_call_id,
                            message_preview=system_message["parts"][0]["text"][:100]
                            + "...",
                        )

                        # Mark tool as completed in our state machine
                        self.tool_state.mark_completed(
                            tool_call_id, {"status": "SUCCESS"}
                        )

                        # Task done
                        self.system_message_queue.task_done()
                        break

                    except Exception as e:
                        logger.error(
                            "Error processing system message",
                            tool_name=function_name,
                            error=str(e),
                            exc_info=True,
                        )

                # Small delay between checks
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(
                    "Error in system message monitor",
                    tool_name=function_name,
                    tool_call_id=tool_call_id,
                    error=str(e),
                    exc_info=True,
                )
                break

        logger.info(
            "System message monitor finished",
            tool_name=function_name,
            tool_call_id=tool_call_id,
        )

    async def deliver_tool_result(self, tool_call_id: str) -> bool:
        """
        Deliver a completed tool result to Gemini.

        Args:
            tool_call_id: ID of the tool call to deliver.

        Returns:
            bool: True if delivery was successful.
        """
        record = self.tool_state.get_tool_record(tool_call_id)
        if not record:
            logger.error(
                "Cannot deliver unknown tool result", tool_call_id=tool_call_id
            )
            return False

        if not record.result:
            logger.error(
                "Cannot deliver tool result without result data",
                tool_call_id=tool_call_id,
            )
            return False

        try:
            # Mark as delivering
            self.tool_state.mark_delivering(tool_call_id)

            # Create function response
            function_response = types.LiveClientToolResponse(
                function_responses=[
                    types.FunctionResponse(
                        name=record.tool_name,
                        id=tool_call_id,
                        response=record.result,
                    )
                ]
            )

            # Send to Gemini
            await self.session.send_tool_response(
                function_responses=[function_response.function_responses[0]]
            )

            # Mark as delivered
            self.tool_state.mark_delivered(tool_call_id)

            logger.info(
                "Tool result delivered to Gemini",
                tool_name=record.tool_name,
                tool_call_id=tool_call_id,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to deliver tool result",
                tool_name=record.tool_name,
                tool_call_id=tool_call_id,
                error=str(e),
                exc_info=True,
            )
            # Put back in pending state on failure
            self.tool_state.mark_completed(tool_call_id, record.result)
            return False

    async def deliver_next_pending_result(self) -> bool:
        """
        Deliver the next pending tool result.

        Returns:
            bool: True if a result was delivered.
        """
        next_record = self.tool_state.get_next_pending()
        if not next_record:
            return False

        return await self.deliver_tool_result(next_record.tool_call_id)

    def get_pending_tool_names(self) -> list:
        """
        Get list of tool names with pending results.

        Returns:
            List of tool names.
        """
        records = self.tool_state.get_all_pending_records()
        return [record.tool_name for record in records]
