# S1-04: Tool Calling Bridge (Skills → LiteLLM Tools)
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
OpenClaw registered Python skills as "tools" in its config (`openclaw-config.json` skills.entries). The LLM could call these tools, and OpenClaw would execute `python3 run_skill.py <skill> <function> '<json>'`. We need a native bridge that:
1. Translates `aria_skills` function signatures into LiteLLM `tools` format (OpenAI function calling schema)
2. Executes tool calls locally (direct Python, no subprocess)
3. Returns results back to the LLM conversation

## Root Cause
`aria_mind/skills/run_skill.py` (597 lines) is the current OpenClaw ↔ Python bridge. It uses CLI invocation (`__main__`), which is OpenClaw-specific. The skill registry at `aria_mind/skills/_skill_registry.py` has 30+ skills with their module/class mappings. We need to convert this CLI bridge to a direct Python function call bridge.

The skill base class (`aria_skills/base.py`) already has well-defined method signatures. Each skill also has a `skill.json` manifest with function descriptions. We need to parse these into the OpenAI function calling format.

## Fix
### `aria_engine/tool_registry.py`
```python
"""
Tool Registry — Translates aria_skills into LiteLLM tool definitions.

Bridges the gap between:
- aria_skills with their skill.json manifests and Python methods
- LiteLLM's OpenAI-compatible function calling format

Handles:
- Auto-discovery from skill.json manifests
- Function signature → JSON Schema conversion
- Direct Python execution (no subprocess)
- Result formatting for LLM consumption
- Timeout enforcement and error handling
"""
import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from aria_engine.exceptions import ToolError

logger = logging.getLogger("aria.engine.tools")


@dataclass
class ToolDefinition:
    """A tool that can be called by the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any]
    skill_name: str
    function_name: str
    _handler: Optional[Callable] = field(default=None, repr=False)


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_call_id: str
    name: str
    content: str
    success: bool = True
    duration_ms: int = 0


class ToolRegistry:
    """
    Discovers and manages tools from aria_skills.
    
    Usage:
        registry = ToolRegistry()
        registry.discover_from_skills(skill_registry)
        
        # Get tool definitions for LLM:
        tools = registry.get_tools_for_llm()
        
        # Execute a tool call:
        result = await registry.execute(tool_call_id, function_name, arguments)
    """
    
    def __init__(self, timeout_seconds: int = 300):
        self._tools: Dict[str, ToolDefinition] = {}
        self._skill_instances: Dict[str, Any] = {}
        self._timeout = timeout_seconds
    
    def discover_from_skills(self, skill_registry) -> int:
        """
        Auto-discover tools from the skill registry.
        
        Reads skill.json manifests and public methods to build tool definitions.
        Returns count of registered tools.
        """
        count = 0
        skills_dir = Path(__file__).parent.parent / "aria_skills"
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            
            manifest_path = skill_dir / "skill.json"
            if not manifest_path.exists():
                continue
            
            try:
                manifest = json.loads(manifest_path.read_text())
                skill_name = manifest.get("name", skill_dir.name)
                
                # Get the skill instance from registry
                skill = skill_registry.get(skill_dir.name)
                if not skill:
                    continue
                
                self._skill_instances[skill_dir.name] = skill
                
                # Register each tool from manifest
                tools = manifest.get("tools", [])
                for tool_def in tools:
                    tool_name = f"{skill_dir.name}__{tool_def['name']}"
                    self._tools[tool_name] = ToolDefinition(
                        name=tool_name,
                        description=tool_def.get("description", ""),
                        parameters=tool_def.get("parameters", {"type": "object", "properties": {}}),
                        skill_name=skill_dir.name,
                        function_name=tool_def["name"],
                        _handler=getattr(skill, tool_def["name"], None),
                    )
                    count += 1
                    
            except Exception as e:
                logger.warning("Failed to discover tools from %s: %s", skill_dir.name, e)
        
        logger.info("Discovered %d tools from %d skills", count, len(self._skill_instances))
        return count
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        skill_name: str = "custom",
    ):
        """Manually register a tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            skill_name=skill_name,
            function_name=name,
            _handler=handler,
        )
    
    def get_tools_for_llm(self, filter_skills: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get tool definitions in OpenAI function calling format.
        
        Returns list of tool dicts compatible with litellm's tools parameter.
        """
        tools = []
        for name, tool in self._tools.items():
            if filter_skills and tool.skill_name not in filter_skills:
                continue
            
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        
        return tools
    
    async def execute(
        self,
        tool_call_id: str,
        function_name: str,
        arguments: str | Dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool call from the LLM.
        
        Args:
            tool_call_id: ID from the LLM's tool call
            function_name: Function name (format: skill__method)
            arguments: JSON string or dict of arguments
        
        Returns:
            ToolResult with stringified content
        """
        import time
        start = time.monotonic()
        
        tool = self._tools.get(function_name)
        if not tool:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=function_name,
                content=json.dumps({"error": f"Unknown tool: {function_name}"}),
                success=False,
            )
        
        if not tool._handler:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=function_name,
                content=json.dumps({"error": f"No handler for tool: {function_name}"}),
                success=False,
            )
        
        # Parse arguments
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                args = {"input": arguments}
        else:
            args = arguments
        
        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(tool._handler):
                result = await asyncio.wait_for(
                    tool._handler(**args),
                    timeout=self._timeout,
                )
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: tool._handler(**args)
                )
            
            elapsed_ms = int((time.monotonic() - start) * 1000)
            
            # Format result
            if hasattr(result, "to_dict"):
                content = json.dumps(result.to_dict())
            elif hasattr(result, "data"):
                content = json.dumps({"success": result.success, "data": result.data})
            elif isinstance(result, (dict, list)):
                content = json.dumps(result)
            else:
                content = str(result)
            
            return ToolResult(
                tool_call_id=tool_call_id,
                name=function_name,
                content=content,
                success=True,
                duration_ms=elapsed_ms,
            )
            
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=function_name,
                content=json.dumps({"error": f"Tool timed out after {self._timeout}s"}),
                success=False,
                duration_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Tool execution failed: %s — %s", function_name, e)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=function_name,
                content=json.dumps({"error": str(e)}),
                success=False,
                duration_ms=elapsed_ms,
            )
    
    def list_tools(self) -> List[Dict[str, str]]:
        """List all registered tools (for debugging)."""
        return [
            {
                "name": t.name,
                "skill": t.skill_name,
                "function": t.function_name,
                "description": t.description[:100],
            }
            for t in self._tools.values()
        ]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Tools execute skills which use api_client — layer preserved |
| 2 | .env for secrets | ❌ | No secrets in tool registry |
| 3 | models.yaml | ❌ | No model references |
| 4 | Docker-first | ✅ | Skill discovery uses relative paths |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-01 must complete first (needs aria_engine package)
- S1-02 should complete first (LLMGateway uses tools parameter)

## Verification
```bash
# 1. Imports work:
python -c "from aria_engine.tool_registry import ToolRegistry, ToolDefinition, ToolResult; print('OK')"
# EXPECTED: OK

# 2. Manual tool registration:
python -c "
from aria_engine.tool_registry import ToolRegistry
reg = ToolRegistry()
reg.register_tool('test_echo', 'Echo input', {'type': 'object', 'properties': {'text': {'type': 'string'}}}, lambda text: text)
tools = reg.get_tools_for_llm()
print(len(tools), tools[0]['function']['name'])
"
# EXPECTED: 1 test_echo

# 3. Tool list:
python -c "
from aria_engine.tool_registry import ToolRegistry
reg = ToolRegistry()
print(reg.list_tools())
"
# EXPECTED: []
```

## Prompt for Agent
```
Implement the Tool Registry for Aria Engine — translates aria_skills into LiteLLM function calling format.

FILES TO READ FIRST:
- aria_skills/base.py (full file — BaseSkill, SkillResult)
- aria_skills/registry.py (full file — SkillRegistry)
- aria_mind/skills/_skill_registry.py (full file — SKILL_REGISTRY dict)
- aria_mind/skills/run_skill.py (full file — current CLI bridge to understand)
- aria_skills/api_client/skill.json (example skill.json manifest)
- aria_skills/health/skill.json (example skill.json manifest)

STEPS:
1. Read all files above to understand skill structure
2. Create aria_engine/tool_registry.py
3. Implement discover_from_skills() — reads skill.json manifests
4. Implement get_tools_for_llm() — OpenAI function calling format
5. Implement execute() — direct Python calls with timeout
6. Implement manual register_tool() and list_tools()
7. Run verification commands

CONSTRAINTS:
- Constraint 1: Tools execute skills which use api_client — never bypass layers
```
