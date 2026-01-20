"""
AllTools class for discovering and accessing all available tools.

This module provides a convenient interface to discover, list, and access
all tools defined in the tools/ directory.
"""

import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel

from app.tools.tool_validator import ToolValidationError, ToolValidator
from app.tools.tools.base_tool import BaseTool
from utils.app_settings import TOOL_CHECKING


class AllTools:  # pylint: disable=too-many-public-methods
    """
    Utility class for discovering and accessing all available tools.

    Automatically discovers all tool classes from the tools/ directory
    and provides convenient class methods to access them.
    """

    _tools_map: Dict[str, BaseTool] = {}
    _tools_by_class: Dict[str, BaseTool] = {}
    _tool_instances: List[BaseTool] = []
    _all_tools: List[BaseTool] = []
    _valid_tools: List[BaseTool] = []
    _invalid_tools: List[BaseTool] = []
    _valid_tools_map: Dict[str, BaseTool] = {}
    _invalid_tools_map: Dict[str, BaseTool] = {}
    _initialized: bool = False

    @classmethod
    def _discover_tools(cls) -> List[BaseTool]:
        """
        Automatically discover all tool classes from the tools/ directory.

        Returns:
            List of tool instances
        """
        tools = []
        tools_dir = Path(__file__).parent / "tools"

        # Get all Python files in the tools directory
        for file_path in tools_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue

            module_name = file_path.stem
            try:
                # Import the module
                module = importlib.import_module(f"app.tools.tools.{module_name}")

                # Find all classes in the module that inherit from BaseTool
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTool) and obj is not BaseTool:
                        # Create an instance of the tool
                        tool_instance = obj()
                        tools.append(tool_instance)
            except (ImportError, AttributeError, TypeError, ValueError) as e:
                # Skip modules that can't be imported or don't have valid tools
                print(f"Warning: Could not import {module_name}: {e}")
                continue

        return tools

    @classmethod
    def _initialize(cls) -> None:
        """Initialize the tools mappings (lazy initialization)."""
        if not cls._initialized:
            cls._all_tools = list(cls._discover_tools())
            cls._valid_tools = []
            cls._invalid_tools = []

            # Separate valid and invalid tools
            for tool in cls._all_tools:
                try:
                    validator = ToolValidator(tool)
                    validator.validate()
                    cls._valid_tools.append(tool)
                except ToolValidationError as e:
                    print(f"Warning: Invalid tool {tool.name}: {e}")
                    cls._invalid_tools.append(tool)
                    # NOTE: Consider using enum for TOOL_CHECKING
                    if TOOL_CHECKING == "strict":
                        raise e
                except (AttributeError, ValueError, RuntimeError, TypeError) as e:
                    print(f"Warning: Unexpected error validating {tool.name}: {e}")
                    cls._invalid_tools.append(tool)
                    # NOTE: Consider using enum for TOOL_CHECKING
                    if TOOL_CHECKING == "strict":
                        raise e

            # Set tool_instances to valid tools only (for backward compatibility)
            cls._tool_instances = cls._valid_tools.copy()

            # Create mappings
            cls._tools_map = {tool.name: tool for tool in cls._valid_tools}
            cls._tools_by_class = {
                tool.__class__.__name__: tool for tool in cls._valid_tools
            }
            cls._valid_tools_map = {tool.name: tool for tool in cls._valid_tools}
            cls._invalid_tools_map = {tool.name: tool for tool in cls._invalid_tools}
            cls._initialized = True

    @classmethod
    def get_tools_map(cls) -> dict[str, BaseTool]:
        return cls._tools_map

    @classmethod
    def get_all_tools(cls) -> List[BaseTool]:
        """
        Get all discovered tool instances (both valid and invalid).

        Returns:
            List of all tool instances
        """
        cls._initialize()
        return list(cls._all_tools)

    @classmethod
    def get_valid_tools(cls) -> List[BaseTool]:
        """
        Get all valid tool instances.

        Returns:
            List of valid tool instances
        """
        cls._initialize()
        return list(cls._valid_tools)

    @classmethod
    def get_invalid_tools(cls) -> List[BaseTool]:
        """
        Get all invalid tool instances.

        Returns:
            List of invalid tool instances
        """
        cls._initialize()
        return list(cls._invalid_tools)

    @classmethod
    def get_by_name(cls, name: str) -> BaseTool:
        """
        Get a valid tool by its name.

        Args:
            name: The tool name (e.g., "take_a_nap", "NameCorrectionAgent")

        Returns:
            Tool instance if found

        Raises:
            ValueError: If tool with given name doesn't exist
        """
        cls._initialize()
        if name in cls._tools_map:
            return cls._tools_map[name]
        raise ValueError(f"Tool with name '{name}' doesn't exist")

    @classmethod
    def get_valid_tool_by_name(cls, name: str) -> BaseTool:
        """
        Get a valid tool by its name.

        Args:
            name: The tool name

        Returns:
            Valid tool instance if found

        Raises:
            ValueError: If valid tool with given name doesn't exist
        """
        cls._initialize()
        if name in cls._valid_tools_map:
            return cls._valid_tools_map[name]
        raise ValueError(f"Valid tool with name '{name}' doesn't exist")

    @classmethod
    def get_invalid_tool_by_name(cls, name: str) -> BaseTool:
        """
        Get an invalid tool by its name.

        Args:
            name: The tool name

        Returns:
            Invalid tool instance if found

        Raises:
            ValueError: If invalid tool with given name doesn't exist
        """
        cls._initialize()
        if name in cls._invalid_tools_map:
            return cls._invalid_tools_map[name]
        raise ValueError(f"Invalid tool with name '{name}' doesn't exist")

    @classmethod
    def get_any_tool_by_name(cls, name: str) -> BaseTool:
        """
        Get any tool by its name (valid or invalid).

        Args:
            name: The tool name

        Returns:
            Tool instance if found

        Raises:
            ValueError: If tool with given name doesn't exist
        """
        cls._initialize()
        # Check valid tools first
        if name in cls._valid_tools_map:
            return cls._valid_tools_map[name]
        # Check invalid tools
        if name in cls._invalid_tools_map:
            return cls._invalid_tools_map[name]
        raise ValueError(f"Tool with name '{name}' doesn't exist")

    @classmethod
    def get_by_class_name(cls, class_name: str) -> BaseTool:
        """
        Get a tool by its class name.

        Args:
            class_name: The tool class name (e.g., "TakeANapTool")

        Returns:
            Tool instance if found

        Raises:
            ValueError: If tool with given class name doesn't exist
        """
        cls._initialize()
        if class_name in cls._tools_by_class:
            return cls._tools_by_class[class_name]
        raise ValueError(f"Tool with class name '{class_name}' doesn't exist")

    @classmethod
    def list_names(cls) -> List[str]:
        """
        Get list of all valid tool names.

        Returns:
            List of valid tool names
        """
        cls._initialize()
        return list(cls._tools_map.keys())

    @classmethod
    def list_all_tool_names(cls) -> List[str]:
        """
        Get list of all tool names (both valid and invalid).

        Returns:
            List of all tool names
        """
        cls._initialize()
        return [tool.name for tool in cls._all_tools]

    @classmethod
    def list_valid_tool_names(cls) -> List[str]:
        """
        Get list of valid tool names.

        Returns:
            List of valid tool names
        """
        cls._initialize()
        return [tool.name for tool in cls._valid_tools]

    @classmethod
    def list_invalid_tool_names(cls) -> List[str]:
        """
        Get list of invalid tool names.

        Returns:
            List of invalid tool names
        """
        cls._initialize()
        return [tool.name for tool in cls._invalid_tools]

    @classmethod
    def list_class_names(cls) -> List[str]:
        """
        Get list of all tool class names.

        Returns:
            List of tool class names
        """
        cls._initialize()
        return list(cls._tools_by_class.keys())

    @classmethod
    def count(cls) -> int:
        """
        Get total number of valid tools.

        Returns:
            Number of valid tools
        """
        cls._initialize()
        return len(cls._tool_instances)

    @classmethod
    def count_all_tools(cls) -> int:
        """
        Get total number of all tools (valid and invalid).

        Returns:
            Number of all tools
        """
        cls._initialize()
        return len(cls._all_tools)

    @classmethod
    def count_valid_tools(cls) -> int:
        """
        Get total number of valid tools.

        Returns:
            Number of valid tools
        """
        cls._initialize()
        return len(cls._valid_tools)

    @classmethod
    def count_invalid_tools(cls) -> int:
        """
        Get total number of invalid tools.

        Returns:
            Number of invalid tools
        """
        cls._initialize()
        return len(cls._invalid_tools)

    @classmethod
    def exists(cls, name: str) -> bool:
        """
        Check if a valid tool exists by name.

        Args:
            name: The tool name to check

        Returns:
            True if valid tool exists, False otherwise
        """
        cls._initialize()
        return name in cls._tools_map

    @classmethod
    def exists_any(cls, name: str) -> bool:
        """
        Check if any tool exists by name (valid or invalid).

        Args:
            name: The tool name to check

        Returns:
            True if tool exists, False otherwise
        """
        cls._initialize()
        valid_exists = name in cls._valid_tools_map
        invalid_exists = name in cls._invalid_tools_map
        return valid_exists or invalid_exists

    @classmethod
    def exists_valid(cls, name: str) -> bool:
        """
        Check if a valid tool exists by name.

        Args:
            name: The tool name to check

        Returns:
            True if valid tool exists, False otherwise
        """
        cls._initialize()
        return name in cls._valid_tools_map

    @classmethod
    def exists_invalid(cls, name: str) -> bool:
        """
        Check if an invalid tool exists by name.

        Args:
            name: The tool name to check

        Returns:
            True if invalid tool exists, False otherwise
        """
        cls._initialize()
        return name in cls._invalid_tools_map

    @classmethod
    def get_tool_info(cls, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a tool.

        Args:
            name: The tool name

        Returns:
            Dictionary with tool information

        Raises:
            ValueError: If tool with given name doesn't exist
        """
        cls._initialize()
        if name not in cls._tools_map:
            raise ValueError(f"Tool with name '{name}' doesn't exist")

        tool = cls._tools_map[name]
        return {
            "name": tool.name,
            "class_name": tool.__class__.__name__,
            "description": tool.description,
            "has_parameters": bool(tool.parameters.properties),
            "parameters": (
                tool.parameters.properties
                if hasattr(tool.parameters, "properties")
                else {}
            ),
            "background_delay": tool.background_delay,
            "module": tool.__class__.__module__,
        }

    @classmethod
    def list_all_info(cls) -> List[Dict[str, Any]]:
        """
        Get detailed information about all tools.

        Returns:
            List of dictionaries with tool information
        """
        cls._initialize()
        if not cls._tools_map:
            return []

        result = []
        for name in cls._tools_map:
            info = cls.get_tool_info(name)
            if info:
                result.append(info)
        return result

    @classmethod
    def print_summary(cls) -> None:
        """Print a summary of all available tools."""
        cls._initialize()
        print(f"\n{'='*70}")
        print(f"{'TOOLS SUMMARY':^70}")
        print(f"{'='*70}\n")
        print(f"Total Tools: {cls.count_all_tools()}")
        print(f"Valid Tools: {cls.count_valid_tools()}")
        print(f"Invalid Tools: {cls.count_invalid_tools()}\n")

        if cls._valid_tools:
            print("✅ VALID TOOLS:")
            for tool in cls._valid_tools:
                print(f"📦 {tool.name}")
                print(f"   Class: {tool.__class__.__name__}")
                print(f"   Delay: {tool.background_delay}s")
                desc_preview = (
                    tool.description[:80] + "..."
                    if len(tool.description) > 80
                    else tool.description
                )
                print(f"   Description: {desc_preview}")
                print()

        if cls._invalid_tools:
            print("❌ INVALID TOOLS:")
            for tool in cls._invalid_tools:
                print(f"📦 {tool.name}")
                print(f"   Class: {tool.__class__.__name__}")
                print(f"   Delay: {tool.background_delay}s")
                desc_preview = (
                    tool.description[:80] + "..."
                    if len(tool.description) > 80
                    else tool.description
                )
                print(f"   Description: {desc_preview}")
                print()

        print(f"{'='*70}\n")


# Convenience function for quick access
def get_tool(name: str) -> BaseTool:
    """
    Convenience function to get a tool by name.

    Args:
        name: The tool name

    Returns:
        Tool instance if found

    Raises:
        ValueError: If tool with given name doesn't exist
    """
    return AllTools.get_by_name(name)


def list_tools() -> List[str]:
    """
    Convenience function to list all tool names.

    Returns:
        List of tool names
    """
    return AllTools.list_names()
