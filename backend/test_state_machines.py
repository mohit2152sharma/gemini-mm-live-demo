"""
Test script for state machine implementation.

This script tests:
- State transitions are valid
- Tool results queue properly during bot speech
- Multiple pending tools trigger user confirmation
- User input blocked during inappropriate states
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.state.conversation_state import ConversationState, ConversationStateMachine
from app.state.tool_state import ToolState, ToolStateMachine


def test_conversation_state_transitions():
    """Test conversation state machine transitions."""
    print("\n" + "=" * 60)
    print("Testing Conversation State Machine")
    print("=" * 60)

    sm = ConversationStateMachine()

    # Test valid transitions
    print("\n✓ Testing valid transitions:")

    # IDLE -> USER_SPEAKING
    assert sm.transition(
        ConversationState.USER_SPEAKING, "test"
    ), "Should allow IDLE -> USER_SPEAKING"
    print("  ✓ IDLE -> USER_SPEAKING: Success")

    # USER_SPEAKING -> IDLE
    assert sm.transition(
        ConversationState.IDLE, "test"
    ), "Should allow USER_SPEAKING -> IDLE"
    print("  ✓ USER_SPEAKING -> IDLE: Success")

    # IDLE -> BOT_SPEAKING
    assert sm.transition(
        ConversationState.BOT_SPEAKING, "test"
    ), "Should allow IDLE -> BOT_SPEAKING"
    print("  ✓ IDLE -> BOT_SPEAKING: Success")

    # BOT_SPEAKING -> IDLE
    assert sm.transition(
        ConversationState.IDLE, "test"
    ), "Should allow BOT_SPEAKING -> IDLE"
    print("  ✓ BOT_SPEAKING -> IDLE: Success")

    # IDLE -> WAITING_FOR_USER
    assert sm.transition(
        ConversationState.WAITING_FOR_USER, "test"
    ), "Should allow IDLE -> WAITING_FOR_USER"
    print("  ✓ IDLE -> WAITING_FOR_USER: Success")

    # WAITING_FOR_USER -> USER_SPEAKING
    assert sm.transition(
        ConversationState.USER_SPEAKING, "test"
    ), "Should allow WAITING_FOR_USER -> USER_SPEAKING"
    print("  ✓ WAITING_FOR_USER -> USER_SPEAKING: Success")

    # Reset to IDLE
    sm.transition(ConversationState.IDLE, "reset")

    # Test invalid transitions
    print("\n✓ Testing invalid transitions:")

    # IDLE -> cannot directly go to USER_SPEAKING then BOT_SPEAKING without return
    sm.transition(ConversationState.USER_SPEAKING, "test")
    # USER_SPEAKING -> WAITING_FOR_USER is invalid
    result = sm.transition(ConversationState.WAITING_FOR_USER, "test")
    assert not result, "Should NOT allow USER_SPEAKING -> WAITING_FOR_USER"
    print("  ✓ USER_SPEAKING -> WAITING_FOR_USER: Correctly blocked")

    # Test can_accept_user_input
    print("\n✓ Testing can_accept_user_input:")
    sm.reset()

    sm.transition(ConversationState.IDLE, "test")
    assert sm.can_accept_user_input(), "Should accept input in IDLE"
    print("  ✓ IDLE state: Accepts input")

    sm.transition(ConversationState.BOT_SPEAKING, "test")
    assert (
        sm.can_accept_user_input()
    ), "Should accept input in BOT_SPEAKING (interruption)"
    print("  ✓ BOT_SPEAKING state: Accepts input (allows interruption)")

    sm.transition(ConversationState.IDLE, "test")
    sm.transition(ConversationState.WAITING_FOR_USER, "test")
    assert sm.can_accept_user_input(), "Should accept input in WAITING_FOR_USER"
    print("  ✓ WAITING_FOR_USER state: Accepts input")

    # Test state history
    print("\n✓ Testing state history:")
    history = sm.get_state_history()
    assert len(history) > 0, "Should have state history"
    print(f"  ✓ State history recorded: {len(history)} transitions")

    print("\n✅ Conversation State Machine: All tests passed!\n")


def test_tool_state_machine():
    """Test tool state machine."""
    print("\n" + "=" * 60)
    print("Testing Tool State Machine")
    print("=" * 60)

    sm = ToolStateMachine()

    print("\n✓ Testing tool registration and lifecycle:")

    # Register a tool
    record = sm.register_tool_call("test_tool", "call-001", {"param": "value"})
    assert record.state == ToolState.PENDING, "New tool should be PENDING"
    print(f"  ✓ Tool registered: {record.tool_name} (state: {record.state.value})")

    # Mark as executing
    sm.mark_executing("call-001")
    record = sm.get_tool_record("call-001")
    assert record.state == ToolState.EXECUTING, "Tool should be EXECUTING"
    print(f"  ✓ Tool executing: {record.tool_name} (state: {record.state.value})")

    # Mark as completed
    sm.mark_completed("call-001", {"status": "success"})
    record = sm.get_tool_record("call-001")
    assert record.state == ToolState.COMPLETED, "Tool should be COMPLETED"
    assert sm.has_pending_results(), "Should have pending results"
    print(f"  ✓ Tool completed: {record.tool_name} (state: {record.state.value})")
    print(f"  ✓ Pending results: {sm.get_pending_count()}")

    # Mark as delivering
    sm.mark_delivering("call-001")
    record = sm.get_tool_record("call-001")
    assert record.state == ToolState.DELIVERING, "Tool should be DELIVERING"
    assert not sm.has_pending_results(), "Should not have pending results (delivering)"
    print(f"  ✓ Tool delivering: {record.tool_name} (state: {record.state.value})")

    # Mark as delivered
    sm.mark_delivered("call-001")
    record = sm.get_tool_record("call-001")
    assert record.state == ToolState.IDLE, "Tool should be IDLE"
    print(f"  ✓ Tool delivered: {record.tool_name} (state: {record.state.value})")

    print("\n✓ Testing multiple pending tools:")

    # Register multiple tools
    for i in range(3):
        sm.register_tool_call(f"tool_{i}", f"call-{i}", {})
        sm.mark_executing(f"call-{i}")
        sm.mark_completed(f"call-{i}", {"result": i})

    assert sm.get_pending_count() == 3, "Should have 3 pending tools"
    print(f"  ✓ Registered 3 tools, pending count: {sm.get_pending_count()}")

    # Get next pending
    next_tool = sm.get_next_pending()
    assert next_tool is not None, "Should get next pending tool"
    assert next_tool.tool_name == "tool_0", "Should get first tool (FIFO)"
    print(f"  ✓ Next pending tool (FIFO): {next_tool.tool_name}")

    # Test can_deliver_results
    assert sm.can_deliver_results(), "Should be able to deliver results"
    print("  ✓ Can deliver results: True")

    # Set awaiting acknowledgment
    sm.set_awaiting_user_ack(True)
    assert (
        not sm.can_deliver_results()
    ), "Should NOT be able to deliver while awaiting ack"
    print("  ✓ Can deliver results (awaiting ack): False")

    sm.set_awaiting_user_ack(False)
    assert sm.can_deliver_results(), "Should be able to deliver after ack cleared"
    print("  ✓ Can deliver results (ack cleared): True")

    # Test status summary
    print("\n✓ Testing status summary:")
    summary = sm.get_status_summary()
    print(f"  ✓ Status summary: {summary}")
    assert summary["pending_delivery_count"] == 3, "Should show 3 pending"

    print("\n✅ Tool State Machine: All tests passed!\n")


def test_tool_failure():
    """Test tool failure handling."""
    print("\n" + "=" * 60)
    print("Testing Tool Failure Handling")
    print("=" * 60)

    sm = ToolStateMachine()

    # Register and fail a tool
    sm.register_tool_call("failing_tool", "call-fail", {})
    sm.mark_executing("call-fail")
    sm.mark_failed("call-fail", "Something went wrong")

    record = sm.get_tool_record("call-fail")
    assert record.state == ToolState.FAILED, "Tool should be FAILED"
    assert record.error is not None, "Tool should have error message"
    print(f"  ✓ Tool failed correctly: {record.error}")

    print("\n✅ Tool Failure Handling: All tests passed!\n")


async def test_integration_scenario():
    """Test integration scenario with both state machines."""
    print("\n" + "=" * 60)
    print("Testing Integration Scenario")
    print("=" * 60)

    conv_sm = ConversationStateMachine()
    tool_sm = ToolStateMachine()

    print("\n📝 Scenario: Tool completes while bot is speaking")

    # User asks a question
    print("  1. User asks question")
    conv_sm.transition(ConversationState.USER_SPEAKING, "user_input")
    conv_sm.transition(ConversationState.IDLE, "sent_to_gemini")

    # Bot starts responding
    print("  2. Bot starts speaking")
    conv_sm.transition(ConversationState.BOT_SPEAKING, "audio_start")

    # Tool completes during bot speech
    print("  3. Tool completes during bot speech")
    tool_sm.register_tool_call("booking_tool", "call-100", {})
    tool_sm.mark_executing("call-100")
    tool_sm.mark_completed("call-100", {"booking_id": "ABC123"})

    # Check states
    assert conv_sm.get_state() == ConversationState.BOT_SPEAKING
    assert tool_sm.has_pending_results()
    print(f"  ✓ Conversation state: {conv_sm.get_state().value}")
    print(f"  ✓ Pending tool results: {tool_sm.get_pending_count()}")

    # Simulate speech completion
    print("  4. Bot finishes speaking")
    conv_sm.transition(ConversationState.IDLE, "speech_complete")

    # Now we're in IDLE with pending results - coordinator would ask user
    assert conv_sm.get_state() == ConversationState.IDLE
    assert tool_sm.has_pending_results()
    print("  ✓ Ready to deliver results (IDLE + pending)")

    # User confirms they want results
    print("  5. User confirms they want results")
    conv_sm.transition(ConversationState.WAITING_FOR_USER, "asking_about_results")
    conv_sm.transition(ConversationState.USER_SPEAKING, "user_response")
    conv_sm.transition(ConversationState.IDLE, "confirmation_sent")

    # Deliver results
    print("  6. Delivering tool result")
    tool_sm.mark_delivering("call-100")
    tool_sm.mark_delivered("call-100")

    assert not tool_sm.has_pending_results()
    print(f"  ✓ Results delivered, pending count: {tool_sm.get_pending_count()}")

    print("\n✅ Integration Scenario: All tests passed!\n")


def main():
    """Run all tests."""
    print("\n" + "🚀" * 30)
    print("STATE MACHINE TEST SUITE")
    print("🚀" * 30)

    try:
        # Run synchronous tests
        test_conversation_state_transitions()
        test_tool_state_machine()
        test_tool_failure()

        # Run async tests
        asyncio.run(test_integration_scenario())

        print("\n" + "🎉" * 30)
        print("ALL TESTS PASSED!")
        print("🎉" * 30 + "\n")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
