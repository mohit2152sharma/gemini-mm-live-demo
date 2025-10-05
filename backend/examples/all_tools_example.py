"""
Example usage of the AllTools class for discovering and accessing tools.
"""

from app.tools import AllTools, get_tool, list_tools


def main():
    print("=" * 70)
    print("AllTools Usage Examples")
    print("=" * 70)
    print()

    # 1. Print summary of all tools
    print("1. Print Summary of All Tools:")
    AllTools.print_summary()

    # 2. Get tool count
    print(f"2. Total number of tools: {AllTools.count()}\n")

    # 3. List all tool names
    print("3. List all tool names:")
    print(f"   {', '.join(AllTools.list_names())}\n")

    # 4. Get a specific tool by name
    print("4. Get a specific tool by name:")
    tool = AllTools.get_by_name("take_a_nap")
    if tool:
        print(f"   Found: {tool.name}")
        print(f"   Class: {tool.__class__.__name__}")
        print(f"   Description: {tool.description[:80]}...\n")

    # 5. Check if a tool exists
    print("5. Check if tools exist:")
    print(f"   'take_a_nap' exists: {AllTools.exists('take_a_nap')}")
    print(f"   'non_existent_tool' exists: {AllTools.exists('non_existent_tool')}\n")

    # 6. Get detailed info about a tool
    print("6. Get detailed info about 'NameCorrectionAgent':")
    info = AllTools.get_tool_info("NameCorrectionAgent")
    if info:
        print(f"   Name: {info['name']}")
        print(f"   Class: {info['class_name']}")
        print(f"   Module: {info['module']}")
        print(f"   Background Delay: {info['background_delay']}s")
        print(f"   Has Parameters: {info['has_parameters']}\n")

    # 7. Filter tools by delay
    print("7. Filter tools by background delay:")
    fast_tools = AllTools.filter_by_delay(min_delay=0, max_delay=20)
    slow_tools = AllTools.filter_by_delay(min_delay=21)
    print(f"   Fast tools (≤20s): {[t.name for t in fast_tools]}")
    print(f"   Slow tools (>20s): {[t.name for t in slow_tools]}\n")

    # 8. Search tools by description
    print("8. Search tools by keyword 'booking':")
    booking_tools = AllTools.search_by_description("booking")
    print(f"   Found {len(booking_tools)} tools:")
    for tool in booking_tools:
        print(f"   - {tool.name}\n")

    # 9. Get all tool info
    print("9. List all tools with their info:")
    all_info = AllTools.list_all_info()
    print(f"   Retrieved info for {len(all_info)} tools\n")
    for info in all_info[:3]:  # Show first 3
        print(f"   - {info['name']} ({info['class_name']})")
    print(f"   ... and {len(all_info) - 3} more\n")

    # 10. Validate all tools
    print("10. Validate all tools:")
    validation_results = AllTools.validate_all()
    all_valid = all(validation_results.values())
    print(f"    All tools valid: {all_valid}")
    if not all_valid:
        print("    Invalid tools:")
        for name, is_valid in validation_results.items():
            if not is_valid:
                print(f"    - {name}")
    print()

    # 11. Using convenience functions
    print("11. Using convenience functions:")
    print(f"    list_tools(): {list_tools()[:3]}... (showing first 3)")
    tool = get_tool("take_a_nap")
    print(f"    get_tool('take_a_nap'): {tool.name if tool else 'Not found'}\n")

    # 12. Get tool by class name
    print("12. Get tool by class name:")
    tool = AllTools.get_by_class_name("TakeANapTool")
    if tool:
        print(f"    Found: {tool.name} (class: {tool.__class__.__name__})\n")

    # 13. List all class names
    print("13. List all tool class names:")
    class_names = AllTools.list_class_names()
    print(f"    {', '.join(class_names[:3])}... ({len(class_names)} total)\n")

    print("=" * 70)
    print("End of examples")
    print("=" * 70)


if __name__ == "__main__":
    main()


