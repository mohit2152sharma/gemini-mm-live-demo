import asyncio
from typing import Any

from google.genai import types

from .base_tool import BaseTool


class AddTwoNumbersTool(BaseTool):
    name: str = "add_two_numbers"
    description: str = (
        "Adds two numeric inputs and returns the computed sum."
        " Use for simple arithmetic queries like 'What is 24 plus 48?'"
    )
    behavior: types.Behavior = types.Behavior.NON_BLOCKING

    @property
    def parameters(self) -> types.Schema:
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "first_number": types.Schema(
                    type=types.Type.NUMBER,
                    description="First operand to add",
                ),
                "second_number": types.Schema(
                    type=types.Type.NUMBER,
                    description="Second operand to add",
                ),
            },
            required=["first_number", "second_number"],
        )

    @property
    def background_delay(self) -> int:
        return 5

    async def execute(
        self,
        session,
        queue,
        first_number: float,
        second_number: float,
    ) -> dict[str, Any]:
        await asyncio.sleep(5)
        total = first_number + second_number
        return {
            "status": "SUCCESS",
            "sum": total,
            "operands": {
                "first_number": first_number,
                "second_number": second_number,
            },
        }

    def implementation(self, session, queue, first_number: float, second_number: float):
        return super().implementation(
            session,
            queue,
            first_number=first_number,
            second_number=second_number,
        )

    def get_pending_message(self, **kwargs) -> str:
        return "Crunching the numbers—give me 5 seconds."
