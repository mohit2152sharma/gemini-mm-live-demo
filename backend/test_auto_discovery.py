#!/usr/bin/env python3
"""
Test script to verify that AllTools auto-discovery works correctly.
"""

from app.tools import AllTools


def test_auto_discovery():
    """Test that AllTools can automatically discover all tools."""
    print("🔍 Testing Auto-Discovery of Tools")
    print("=" * 50)

    # Test basic discovery
    print(f"📊 Total tools discovered: {AllTools.count()}")

    # List all discovered tools
    print("\n📋 All discovered tools:")
    for tool in AllTools.get_all():
        print(f"  - {tool.name} ({tool.__class__.__name__})")

    # Test specific tool access
    print("\n🔍 Testing specific tool access:")
    nap_tool = AllTools.get_by_name("take_a_nap")
    if nap_tool:
        print(f"  ✅ Found 'take_a_nap': {nap_tool.__class__.__name__}")
    else:
        print("  ❌ Could not find 'take_a_nap'")

    # Test class-based access
    nap_tool_by_class = AllTools.get_by_class_name("TakeANapTool")
    if nap_tool_by_class:
        print(f"  ✅ Found by class 'TakeANapTool': {nap_tool_by_class.name}")
    else:
        print("  ❌ Could not find by class 'TakeANapTool'")

    # Test validation
    print("\n✅ Testing tool validation:")
    validation_results = AllTools.validate_all()
    all_valid = all(validation_results.values())
    print(f"  All tools valid: {all_valid}")

    if not all_valid:
        print("  Invalid tools:")
        for name, is_valid in validation_results.items():
            if not is_valid:
                print(f"    - {name}")

    # Test filtering
    print("\n🔍 Testing filtering by delay:")
    fast_tools = AllTools.filter_by_delay(max_delay=20)
    slow_tools = AllTools.filter_by_delay(min_delay=21)
    print(f"  Fast tools (≤20s): {[t.name for t in fast_tools]}")
    print(f"  Slow tools (>20s): {[t.name for t in slow_tools]}")

    # Test search
    print("\n🔍 Testing search by description:")
    booking_tools = AllTools.search_by_description("booking")
    print(f"  Tools with 'booking' in description: {[t.name for t in booking_tools]}")

    # Print summary
    print("\n📊 Tool Summary:")
    AllTools.print_summary()

    print("✅ Auto-discovery test completed!")


if __name__ == "__main__":
    test_auto_discovery()


