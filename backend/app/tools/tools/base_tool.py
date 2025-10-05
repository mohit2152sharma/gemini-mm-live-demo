import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Callable

from google.genai import types


class BaseTool(ABC):
    """Base class for all tools with background execution support."""

    @property
    @abstractmethod
    def behavior(self) -> types.Behavior:
        """Behaviour of the tool."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for Gemini."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> types.Schema:
        """Tool parameters schema. Override if tool has parameters."""
        ...

    @property
    def response_schema(self) -> types.Schema | None:
        """Response schema. Override if needed."""
        return None

    @property
    def declaration(self) -> types.FunctionDeclaration:
        """Auto-generated declaration from tool properties."""
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            response=self.response_schema,
            # NOTE: behavior parameter is not supported in vertexai
            # behavior=self.behavior,
        )

    @abstractmethod
    async def execute(self, session, queue, **kwargs) -> dict[str, Any]:
        """
        Core tool logic. Implement this with your actual business logic.
        Returns the final result dict.
        """
        ...

    def get_pending_message(self, **kwargs) -> str:
        """
        Override to customize the immediate pending response message.
        Default message can use kwargs to be more specific.
        """
        return f"Processing {self.name}..."

    def get_system_message(self, result: dict[str, Any], **kwargs) -> str:
        """
        Override to customize the system message sent after completion.
        Default formats the result as JSON.
        """
        return f"[SYSTEM]: The {self.name} operation completed. Details: {json.dumps(result)}. Please inform the user."

    def implementation(self, session, queue, **kwargs):
        """
        Returns the actual callable implementation that integrates with your registry.
        This is the function that gets called by CallbackBasedFunctionRegistry.
        """
        asyncio.create_task(self.execute(session, queue, **kwargs))
