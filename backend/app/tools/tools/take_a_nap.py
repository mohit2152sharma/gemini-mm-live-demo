from datetime import datetime, timezone
from typing import Any
from google.genai import types

from .base_tool import BaseTool


class TakeANapTool(BaseTool):
    name: str = "take_a_nap"
    description: str = "A dummy function that takes a nap for 30 seconds and then wakes up with a friendly message. Use this to test long-running function calls and non-blocking execution."
    behavior: types.Behavior = types.Behavior.NON_BLOCKING

    @property
    def parameters(self) -> types.Schema:
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "duration": types.Schema(type=types.Type.NUMBER, description="Duration of the nap in seconds"),
            },
            required=["duration"],
        )

    @property
    def background_delay(self) -> int:
        return 30

    async def execute(self, session, queue, duration: int) -> dict[str, Any]:
        return {
            "status": "SUCCESS",
            "message": "I have slept really good, thanks for waking me up! 😴💤",
            "sleep_duration": f"{duration} seconds",
            "wake_up_time": datetime.now(timezone.utc).isoformat(),
        }
    
    def implementation(self, session, queue, duration: float):
        return super().implementation(session, queue, duration=duration)

    def get_pending_message(self, **kwargs) -> str:
        return "I'm going to take a short nap... I'll be back in 30 seconds."

    def get_system_message(self, result: dict[str, Any], **kwargs) -> str:
        import json

        return f"[SYSTEM]: The nap is over. Details: {json.dumps(result)}. Please inform the user."
