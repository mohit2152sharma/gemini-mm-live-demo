# State Machine Implementation Guide

## Overview

This document describes the state machine-based conversation bot implementation. The system uses two independent state machines to coordinate user/bot interactions and tool execution.

## Architecture

### State Machines

1. **Conversation State Machine** (`app/state/conversation_state.py`)
   - Manages the conversation flow between user and bot
   - States: IDLE, USER_SPEAKING, BOT_SPEAKING, WAITING_FOR_USER

2. **Tool State Machine** (`app/state/tool_state.py`)
   - Manages tool execution lifecycle
   - States: IDLE, PENDING, EXECUTING, COMPLETED, DELIVERING, FAILED
   - Tracks multiple concurrent tool executions

### Core Components

```
app/state/
├── __init__.py                    # State module exports
├── conversation_state.py          # Conversation state machine
├── tool_state.py                  # Tool state machine
└── tool_executor.py               # Tool execution manager

app/handlers/
├── state_machine_handler.py      # Coordinator between state machines
├── sm_client_handler.py           # State-aware client input handler
└── sm_response_handler.py         # State-aware response handler
```

## State Transitions

### Conversation State Transitions

```
IDLE ──────────────────────────────────────────────────┐
  │                                                     │
  │ user_input                                          │
  ├──────────> USER_SPEAKING ──message_sent──> IDLE    │
  │                                                     │
  │ audio_start                                         │
  ├──────────> BOT_SPEAKING ───speech_gap───> IDLE     │
  │                                                     │
  │ asking_about_results                                │
  └──────────> WAITING_FOR_USER ──user_response─> USER_SPEAKING
```

### Tool State Transitions (Per Tool)

```
IDLE
  │
  │ tool_call_received
  │
  ▼
PENDING
  │
  │ execution_start
  │
  ▼
EXECUTING ──────────┐
  │                 │ error
  │ completion      │
  ▼                 ▼
COMPLETED        FAILED
  │
  │ delivery_start
  │
  ▼
DELIVERING
  │
  │ delivery_confirmed
  │
  ▼
IDLE
```

## Key Features

### 1. Non-Blocking Tool Execution

Tools execute asynchronously in the background without blocking the conversation:

```python
# Tool executor creates background task
asyncio.create_task(self._execute_tool_background(...))

# Immediately returns PENDING status to Gemini
return {"status": "PENDING", "message": "Processing..."}
```

### 2. Coordinated Result Delivery

Results are delivered when appropriate based on conversation state:

```python
# If bot is speaking when tool completes
if conversation_state == BOT_SPEAKING:
    tool_state.mark_completed(tool_id, result)  # Queue result
    # Wait for conversation to return to IDLE

# When conversation returns to IDLE
if conversation_state == IDLE and tool_state.has_pending_results():
    coordinator.coordinate_tool_delivery()  # Deliver queued results
```

### 3. Multiple Pending Results Handling

When multiple tools complete, the system asks the user:

```python
if pending_count > 1:
    prompt = f"I have results from {pending_count} tools ready: {tools}. Would you like to hear them?"
    # Wait for user confirmation before delivering
```

### 4. Sequential Delivery

Results are delivered one at a time (FIFO) to prevent overlapping interruptions:

```python
while tool_state.has_pending_results():
    await tool_executor.deliver_next_pending_result()
    await asyncio.sleep(0.3)  # Brief delay between deliveries
```

## Usage

### Enabling State Machines

In `websocket_handler.py`:

```python
handler = WebSocketHandler(use_state_machines=True)
```

### State Machine Flow

1. **Client sends input** → Client handler validates conversation state
2. **If valid** → Transition to USER_SPEAKING, forward to Gemini
3. **After sending** → Transition to IDLE
4. **Gemini sends audio** → Response handler transitions to BOT_SPEAKING
5. **Tool call received** → Tool executor creates background task
6. **Tool completes** → Mark as COMPLETED, add to pending queue
7. **Speech gap detected** → Transition to IDLE
8. **Coordinator checks** → Pending results + IDLE state → Deliver results

## Testing

Run the test suite:

```bash
cd backend
python3 test_state_machines.py
```

Tests verify:
- ✓ Valid state transitions succeed
- ✓ Invalid transitions are blocked
- ✓ Input validation based on state
- ✓ Tool results queue during bot speech
- ✓ Multiple pending tools trigger user confirmation
- ✓ FIFO result delivery

## Integration with Existing Code

### Tool Implementations

Tool implementations in `app/tools/implementations.py` remain **unchanged**. They continue to:
- Accept `(session, queue, **kwargs)` parameters
- Return immediate PENDING status
- Create background tasks for async work

### System Message Queue

The system message queue continues to work as before, allowing tools to send results back to Gemini when background tasks complete.

## Configuration

### Speech Gap Threshold

Adjust how long to wait before considering speech complete:

```python
# In sm_response_handler.py
self._speech_gap_threshold = 1.5  # seconds
```

### Delivery Check Interval

Adjust how frequently to check for pending deliveries:

```python
# In state_machine_handler.py
self._delivery_check_interval = 0.5  # seconds
```

## Debugging

### Logging

All state transitions and tool events are logged with structured logging:

```python
logger.info(
    "Conversation state transition",
    from_state=old_state.value,
    to_state=new_state.value,
    trigger=trigger,
)
```

### State History

Get the history of state transitions:

```python
history = conversation_state.get_state_history(limit=10)
```

### Status Summary

Get a summary of current state:

```python
summary = coordinator.get_status_summary()
# Returns: {
#   "conversation_state": "IDLE",
#   "tool_status": {
#     "total_tools": 5,
#     "executing": 1,
#     "pending_delivery_count": 2,
#     ...
#   },
#   "can_accept_input": True
# }
```

## Advantages Over Previous Implementation

1. **Explicit State Management**: Clear state transitions instead of implicit flags
2. **Better Coordination**: Proper coordination between conversation and tools
3. **Predictable Behavior**: State machines enforce valid transitions
4. **Easier Testing**: State transitions can be tested independently
5. **Better Debugging**: State history and logging provide clear audit trail
6. **Scalability**: Can track multiple concurrent tools properly
7. **User Experience**: Asks before overwhelming with multiple results

## Comparison: Legacy vs State Machine

| Feature | Legacy | State Machine |
|---------|--------|---------------|
| State Management | Implicit flags | Explicit state machines |
| Tool Coordination | Ad-hoc queuing | Structured coordination |
| Multiple Tools | Can overlap | Sequential FIFO delivery |
| User Confirmation | Optional | Built-in for multiple results |
| Testing | Difficult | Easy to test states |
| Debugging | Print statements | Structured logging + history |
| Validation | Manual checks | Enforced by state machine |

## Future Enhancements

Possible improvements to the state machine implementation:

1. **Priority-based Delivery**: Allow certain tools to be delivered first
2. **Tool Grouping**: Group related tool results together
3. **Timeout Handling**: Automatically timeout stuck tool executions
4. **State Persistence**: Save state for session resumption
5. **Metrics Collection**: Track state transition patterns
6. **Circuit Breaker**: Prevent too many failed tool calls

## Troubleshooting

### Tool results not being delivered

Check:
1. Is conversation state IDLE? (Bot must finish speaking)
2. Are results marked as COMPLETED? (Check tool_state.get_status_summary())
3. Is awaiting_user_ack set? (User might need to confirm)

### User input being blocked

Check:
1. Current conversation state (must be IDLE, BOT_SPEAKING, or WAITING_FOR_USER)
2. Call `coordinator.can_accept_user_input()` to verify

### Multiple delivery of same result

Check:
1. Tool call IDs are unique
2. Results aren't being re-added to pending queue

## API Reference

### ConversationStateMachine

```python
# Get current state
state = conversation_state.get_state()

# Transition to new state
success = conversation_state.transition(ConversationState.IDLE, trigger="reason")

# Check if can accept input
can_accept = conversation_state.can_accept_user_input()

# Get state history
history = conversation_state.get_state_history(limit=10)
```

### ToolStateMachine

```python
# Register tool call
record = tool_state.register_tool_call(name, id, params)

# Update tool states
tool_state.mark_executing(tool_id)
tool_state.mark_completed(tool_id, result)
tool_state.mark_failed(tool_id, error)

# Check pending results
has_pending = tool_state.has_pending_results()
count = tool_state.get_pending_count()
next_record = tool_state.get_next_pending()

# Get status
summary = tool_state.get_status_summary()
```

### StateMachineCoordinator

```python
# Coordinate delivery
await coordinator.coordinate_tool_delivery()

# Handle user acknowledgment
handled = await coordinator.handle_user_acknowledgment(message)

# Handle state transitions
success = await coordinator.handle_state_transition(new_state, trigger)

# Check state
can_accept = coordinator.can_accept_user_input()
current_state = coordinator.get_conversation_state()
```

## Contributing

When modifying the state machine implementation:

1. Ensure all state transitions are valid and documented
2. Add appropriate logging for debugging
3. Update tests for new features
4. Document new states or transitions in this guide
5. Consider backward compatibility with existing tool implementations

