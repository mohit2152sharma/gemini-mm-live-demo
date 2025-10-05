"""Manages the execution of tools"""

import asyncio

from google.genai.live import AsyncSession
from pydantic import BaseModel

from app.tools.all_tools import AllTools
from app.tools.tools.base_tool import BaseTool
from utils._logger import logger


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
