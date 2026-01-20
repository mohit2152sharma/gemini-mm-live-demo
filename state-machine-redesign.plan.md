<!-- 0a7d776d-8960-46e9-85a4-23df7bc2a16f 4d8442fd-b49f-432f-bf7a-7a9c9716e1de -->
# State Machine Conversation Bot Redesign

## Architecture Overview

Implement two independent state machines:

1. **Conversation State Machine**: Manages user/bot interaction flow (IDLE, USER_SPEAKING, BOT_SPEAKING, WAITING_FOR_USER)
2. **Tool State Machine**: Manages tool execution lifecycle (IDLE, EXECUTING, COMPLETED, DELIVERING_RESULTS)

## Core Components to Create

### 1. State Machine Core (`backend/app/state/conversation_state.py`)

- Define `ConversationState` enum: IDLE, USER_SPEAKING, BOT_SPEAKING, WAITING_FOR_USER
- Implement `ConversationStateMachine` class with:
- State transitions with validation
- Event triggers (user_input, bot_start_speaking, bot_finish_speaking)
- Can-accept-input checks based on current state
- State history tracking

### 2. Tool State Manager (`backend/app/state/tool_state.py`)

- Define `ToolState` enum: IDLE, PENDING, EXECUTING, COMPLETED, DELIVERING
- Implement `ToolStateMachine` class with:
- Per-tool state tracking (multiple tools can run concurrently)
- Tool result queue management
- Delivery coordination logic
- Methods: can_deliver_results(), queue_tool_result(), get_pending_tools()

### 3. Coordinated Handler (`backend/app/handlers/state_machine_handler.py`)

- Main coordinator that bridges conversation and tool states
- Implements logic:
- If BOT_SPEAKING and tool completes → queue result
- If IDLE and pending results → deliver results
- If multiple pending results → ask user first
- Methods: coordinate_tool_delivery(), handle_state_transition()

### 4. State-Aware Client Handler (`backend/app/handlers/sm_client_handler.py`)

- Replaces client_input_handler.py
- Checks conversation state before accepting input
- Transitions: IDLE → USER_SPEAKING on input
- Forwards validated input to Gemini
- Integrates with ConversationStateMachine

### 5. State-Aware Response Handler (`backend/app/handlers/sm_response_handler.py`)

- Replaces gemini_response_handler.py
- Updates conversation state: BOT_SPEAKING when audio starts
- Tracks speech completion based on audio gaps
- Delegates tool calls to tool state machine
- Coordinates with tool delivery logic

### 6. Tool Execution Manager (`backend/app/state/tool_executor.py`)

- Manages async tool execution
- Updates tool state machine when tools start/complete
- Sends system messages back to Gemini when tools finish
- Tracks tool execution metadata (start time, duration, status)

## Key Implementation Details

### State Transition Rules

**Conversation States:**

- IDLE → USER_SPEAKING: User sends text/audio input
- USER_SPEAKING → IDLE: Input forwarded to Gemini
- IDLE → BOT_SPEAKING: Gemini starts sending audio
- BOT_SPEAKING → IDLE: No audio for 1.5s (speech gap detected)
- IDLE → WAITING_FOR_USER: Bot asks question about pending results

**Tool States (per tool):**

- IDLE → PENDING: Tool call received from Gemini
- PENDING → EXECUTING: Background task starts
- EXECUTING → COMPLETED: Background task finishes
- COMPLETED → DELIVERING: Results sent to Gemini
- DELIVERING → IDLE: Delivery confirmed

### Tool Result Coordination

1. When tool completes during BOT_SPEAKING:

- Mark as COMPLETED in tool state machine
- Queue result in pending list
- Wait for conversation state to return to IDLE

2. When conversation returns to IDLE with pending results:

- Check if multiple tools pending (>1)
- If yes: Ask user "I have N results ready. Would you like to hear them?"
- If user confirms: Deliver results sequentially
- If user declines: Keep in pending state

3. Sequential delivery prevents overlapping interruptions

### Integration Points

- `websocket_handler.py`: Initialize both state machines, pass to handlers
- Tool implementations: Remain unchanged in `implementations.py`
- System message queue: Used to send tool results back to Gemini

## Files to Create

1. `backend/app/state/__init__.py`
2. `backend/app/state/conversation_state.py` 
3. `backend/app/state/tool_state.py`
4. `backend/app/state/tool_executor.py`
5. `backend/app/handlers/state_machine_handler.py`
6. `backend/app/handlers/sm_client_handler.py`
7. `backend/app/handlers/sm_response_handler.py`

## Testing Strategy

Create test file to verify:

- State transitions are valid
- Tool results queue properly during bot speech
- Multiple pending tools trigger user confirmation
- User input blocked during inappropriate states

### To-dos

- [ ] Create conversation and tool state machine classes with enums, transitions, and validation
- [ ] Implement tool executor that manages async tool execution and updates tool state
- [ ] Build state machine handler that coordinates between conversation and tool states
- [ ] Implement state-aware client handler that validates input based on conversation state
- [ ] Implement state-aware response handler that tracks bot speech and coordinates tool delivery
- [ ] Update websocket handler to initialize state machines and use new handlers
- [ ] Create test script to verify state transitions and tool coordination work correctly