# S-34: Chat Tool Execution Graph — LangGraph-Style DAG in Chat UI
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P1 | **Points:** 8 | **Phase:** 2

## Problem

When Aria executes tools during a chat conversation, the current UI (`engine_chat.html` lines 1208–1330, class `ToolVisualizer`) renders tool calls as **flat inline cards** — each tool call appears as an expandable card with parameters, result, and timing. This works for simple single-tool calls but fails to communicate:

1. **Execution flow**: Which LLM iteration triggered which tool calls (the chat engine loops up to `MAX_TOOL_ITERATIONS=10` in `aria_engine/chat_engine.py` around line 401)
2. **Sequential dependencies**: Tool B may depend on Tool A's result (the LLM sees Tool A's result before deciding to call Tool B)
3. **Parallel tool calls**: When the LLM returns multiple `tool_calls` in one response, they execute sequentially but were decided together
4. **Routing decisions**: The `EngineRouter.route_message()` (`aria_engine/routing.py`) selects agents with a multi-factor scoring algorithm — this decision is invisible
5. **Total pipeline cost**: Aggregate tokens, latency, and cost across all iterations

Modern frameworks like LangGraph and LangSmith visualize this as a **directed acyclic graph (DAG)**:
```
[User Input] → [LLM Call 1] → [Tool A] → [Tool B] → [LLM Call 2] → [Final Response]
```

The roundtable page (`engine_roundtable.html` lines 861–1007) already implements a vis-network interactive graph for multi-agent discussions — this pattern should be reused for tool execution graphs.

**Missing:** A collapsible tool execution graph panel in the chat UI that renders the full execution pipeline as an interactive vis-network DAG after each message.

## Root Cause

The chat engine WebSocket (`src/api/routers/engine_chat.py` line 480) delegates to the streaming manager in `aria_engine/streaming.py`, which streams structured JSON events: `token`, `thinking`, `tool_call`, `tool_result`, `done`, `error`. However:

1. **No iteration-level events**: The WS doesn't emit "LLM iteration start/end" — you get flat `tool_call_start`/`tool_call_end` but can't distinguish which LLM call triggered which tools.
2. **No graph container**: The chat HTML has no `<div>` for vis-network.
3. **No aggregated pipeline data**: The `done` event includes `tool_calls` and `tool_results` arrays but doesn't group by iteration.

The `ChatResponse.to_dict()` method in `aria_engine/chat_engine.py` (line 57) returns:
```python
{
    "tool_calls": [...],      # Flat list of all tool calls
    "tool_results": [...],    # Flat list of all results
    "input_tokens": N,
    "output_tokens": N,
    "latency_ms": N,
}
```

This needs to be enhanced with iteration-level data for the graph.

## Fix

### 1. Enhance WebSocket events with iteration tracking

**File:** `aria_engine/streaming.py`

**Architecture clarification:** The tool iteration loop lives in `aria_engine/streaming.py` at line 280 (`for iteration in range(max_tool_iterations)`). The WebSocket handler in `src/api/routers/engine_chat.py` line 480 delegates to `_stream_manager.handle_connection()` which calls the streaming engine. The iteration events MUST be added inside the streaming.py loop, NOT in the router.

Existing event types in streaming.py: `token`, `thinking`, `tool_call`, `tool_result`, `done`, `error`.

In the tool loop (around line 280), add iteration-level events:

```python
# Add to the streaming handler in the tool loop:
# Before each LLM call in the iteration:
await stream.send_json({
    "type": "iteration_start",
    "iteration": iteration_num,
    "tool_calls_so_far": len(all_tool_calls),
})

# After LLM call returns tool_calls:
await stream.send_json({
    "type": "iteration_end", 
    "iteration": iteration_num,
    "has_tool_calls": bool(response.tool_calls),
    "tool_count": len(response.tool_calls) if response.tool_calls else 0,
    "tokens": {"input": response.input_tokens, "output": response.output_tokens},
})
```

### 2. Add execution graph visualization to chat UI

**File:** `src/web/templates/engine_chat.html`

Add a new `ExecutionGraphVisualizer` class after the existing `ToolVisualizer` (after line 1330):

```javascript
/**
 * ExecutionGraphVisualizer — Renders tool execution as a vis-network DAG.
 * 
 * Graph nodes:
 * - user_input (green box) — the user's message
 * - llm_call_N (blue dot) — each LLM iteration  
 * - tool_N (orange diamond) — each tool call
 * - final_response (purple star) — the final assistant response
 *
 * Graph edges:
 * - user → llm_1 (solid)
 * - llm_N → tool_A, tool_B (solid, during same iteration)
 * - tool_A → llm_N+1 (dashed, tool result feeds next iteration)
 * - llm_last → final (solid green)
 */
class ExecutionGraphVisualizer {
    constructor() {
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.network = null;
        this.iterations = [];
        this.currentIteration = 0;
        this.totalTokens = { input: 0, output: 0 };
        this.totalLatency = 0;
    }

    initGraph(container) {
        const options = {
            physics: { enabled: true, solver: 'forceAtlas2Based',
                forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.01, springLength: 120 },
                stabilization: { iterations: 60 },
            },
            layout: { hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed', levelSeparation: 180, nodeSpacing: 80 } },
            interaction: { hover: true, tooltipDelay: 150 },
            nodes: { borderWidth: 1.5, shadow: { enabled: true, size: 3 } },
            edges: { smooth: { type: 'cubicBezier' }, shadow: false, arrows: { to: { enabled: true, scaleFactor: 0.6 } } },
        };
        this.network = new vis.Network(container, { nodes: this.nodes, edges: this.edges }, options);
    }

    addUserInput(content) {
        this.nodes.add({
            id: 'user', label: 'User Input', shape: 'box',
            color: { background: '#065f46', border: '#10b981' },
            font: { color: '#fff', size: 12 },
            title: content.substring(0, 200),
        });
    }

    addLLMCall(iteration, tokens) {
        const id = `llm_${iteration}`;
        this.nodes.add({
            id, label: `LLM #${iteration}`, shape: 'dot', size: 18,
            color: { background: '#1e40af', border: '#3b82f6' },
            font: { color: '#fff', size: 11 },
            title: `Iteration ${iteration}\nTokens: ${tokens.input}→${tokens.output}`,
        });
        if (iteration === 1) {
            this.edges.add({ from: 'user', to: id, color: { color: '#10b981' }, width: 2 });
        }
        this.currentIteration = iteration;
        this.totalTokens.input += tokens.input || 0;
        this.totalTokens.output += tokens.output || 0;
    }

    addToolCall(toolCall) {
        const id = `tool_${toolCall.id}`;
        this.nodes.add({
            id, label: toolCall.name.split('__').pop(), shape: 'diamond', size: 14,
            color: { background: '#92400e', border: '#f59e0b' },
            font: { color: '#fff', size: 10 },
            title: `Tool: ${toolCall.name}\nArgs: ${JSON.stringify(toolCall.arguments).substring(0, 150)}`,
        });
        this.edges.add({
            from: `llm_${this.currentIteration}`, to: id,
            color: { color: '#f59e0b' }, width: 1.5,
        });
    }

    completeToolCall(result) {
        const nodeId = `tool_${result.id}`;
        const existing = this.nodes.get(nodeId);
        if (!existing) return;
        const isError = result.error || !result.success;
        this.nodes.update({
            id: nodeId,
            color: {
                background: isError ? '#991b1b' : '#065f46',
                border: isError ? '#ef4444' : '#22c55e',
            },
            title: existing.title + `\nDuration: ${result.duration_ms}ms\nStatus: ${isError ? 'ERROR' : 'OK'}`,
        });
    }

    addToolToNextIteration(toolCallId, nextIteration) {
        this.edges.add({
            from: `tool_${toolCallId}`, to: `llm_${nextIteration}`,
            color: { color: '#6b7280' }, width: 1, dashes: [5, 5],
        });
    }

    addFinalResponse(content, latencyMs) {
        this.nodes.add({
            id: 'final', label: 'Response', shape: 'star', size: 20,
            color: { background: '#581c87', border: '#a855f7' },
            font: { color: '#fff', size: 12 },
            title: `Final response\nLatency: ${latencyMs}ms\nTotal tokens: ${this.totalTokens.input}+${this.totalTokens.output}`,
        });
        this.edges.add({
            from: `llm_${this.currentIteration}`, to: 'final',
            color: { color: '#a855f7' }, width: 2,
        });
        this.totalLatency = latencyMs;
    }

    getSummary() {
        return {
            iterations: this.currentIteration,
            tools: this.nodes.getIds().filter(id => id.startsWith('tool_')).length,
            totalTokens: this.totalTokens,
            latencyMs: this.totalLatency,
        };
    }
}
```

### 3. Add collapsible graph panel to chat message template

**File:** `src/web/templates/engine_chat.html`

After each assistant message that involved tool calls, insert a collapsible "Execution Graph" section:

```html
<div class="execution-graph-panel" style="display:none;">
    <div class="execution-graph-toggle" onclick="this.parentElement.classList.toggle('expanded')">
        📊 Execution Graph <span class="eg-summary"></span>
        <span class="eg-chevron">▶</span>
    </div>
    <div class="execution-graph-container" style="height:300px;"></div>
</div>
```

### 4. Add vis-network script tag to chat page

**File:** `src/web/templates/engine_chat.html`

Add before the main chat script (around line 1335):
```html
<script src="/static/js/vis-network.min.js"></script>
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Streaming event changes in aria_engine/streaming.py (engine layer). Frontend renders from WS events. No layer violation. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved. |
| 3 | models.yaml single source of truth | ❌ | No model references. |
| 4 | Docker-first testing | ✅ | Must test WebSocket streaming with tool calls in Docker. |
| 5 | aria_memories only writable path | ❌ | No file writes. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **None blocking** — Self-contained. Uses existing vis-network.min.js.
- **Enhancement synergy with S-22** (LLM timeout + circuit breakers) — circuit breaker state could be reflected in graph nodes.

## Verification
```bash
# 1. vis-network loaded in chat page:
grep -n "vis-network" src/web/templates/engine_chat.html
# EXPECTED: script tag for vis-network.min.js

# 2. ExecutionGraphVisualizer class exists:
grep -n "ExecutionGraphVisualizer" src/web/templates/engine_chat.html
# EXPECTED: class definition line

# 3. Iteration events in streaming engine:
grep -n "iteration_start\|iteration_end" aria_engine/streaming.py
# EXPECTED: 2+ matches (event emissions in tool loop)

# 4. Graph container in HTML:
grep -n "execution-graph-container\|execution-graph-panel" src/web/templates/engine_chat.html
# EXPECTED: 2+ matches (HTML elements)

# 5. No vis-network loaded twice:
grep -c "vis-network" src/web/templates/engine_chat.html
# EXPECTED: 1 (single script tag)

# 6. WebSocket handles new events:
grep -n "iteration_start\|iteration_end" src/web/templates/engine_chat.html
# EXPECTED: event handlers in WS message processing
```

## Prompt for Agent
```
You are implementing S-34: Chat Tool Execution Graph (LangGraph-style DAG) for the Aria project.

FILES TO READ FIRST:
- src/web/templates/engine_chat.html (full file — 2465 lines) — the chat UI
  - Lines 335-420: tool-call-card CSS (existing tool viz)
  - Lines 1196-1340: ToolVisualizer class (existing flat tool cards)
  - Lines 1340-2465: main chat JS (WebSocket handlers at ~1946)
- aria_engine/streaming.py (lines 260-460) — streaming tool loop (line 280) where iteration events must be added
- aria_engine/chat_engine.py (lines 380-580) — non-streaming tool execution loop (reference only)
- src/api/routers/engine_chat.py (lines 480-537) — WebSocket endpoint (delegates to streaming.py)

CONSTRAINTS:
1. Do NOT break existing ToolVisualizer — the execution graph is ADDITIONAL (shown below tool cards)
2. vis-network.min.js is already at /static/js/vis-network.min.js
3. Graph should be collapsible (hidden by default, toggle on click)
4. Hierarchical left-to-right layout for DAG (not physics-based)
5. Must handle messages with 0 tool calls gracefully (don't show graph panel)

STEPS:
1. Add iteration_start/iteration_end events to aria_engine/streaming.py tool loop (line 280)
2. Add <script src="/static/js/vis-network.min.js"></script> to engine_chat.html
3. Add ExecutionGraphVisualizer class (see Fix section for full code)
4. Add CSS for .execution-graph-panel (collapsible, 300px height)
5. Wire up WS event handlers: iteration_start → addLLMCall, tool_call → addToolCall, tool_result → completeToolCall, done → addFinalResponse
6. After each assistant message with tools: insert graph panel, call initGraph(), show summary badge
7. Test with a chat that triggers tool calls (e.g., "What skills do you have?")

Node types for graph:
- user_input: green box (#065f46/#10b981)
- llm_call: blue dot (#1e40af/#3b82f6), size 18
- tool_call: orange diamond (#92400e/#f59e0b), size 14
- final_response: purple star (#581c87/#a855f7), size 20

Edge types:
- user→llm: solid green, width 2
- llm→tool: solid orange, width 1.5
- tool→next_llm: dashed gray, width 1
- llm→final: solid purple, width 2
```
