"""Manages the execution of tools"""

import asyncio

from google.genai.live import AsyncSession

from app.tools.tools.base_tool import BaseTool


class ToolState:
    pass


class ToolsExecutor:
    def __init__(
        self,
        gemini_session: AsyncSession,
        tool_queue: asyncio.Queue,
        tools: dict[str, BaseTool],
    ):
        self.gemini_session = gemini_session
        self.tool_queue = tool_queue
        self.tools = tools
