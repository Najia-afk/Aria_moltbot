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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aria_engine.exceptions import ToolError

logger = logging.getLogger("aria.engine.tools")


@dataclass
class ToolDefinition:
    """A tool that can be called by the LLM."""
    name: str
    description: str
    parameters: dict[str, Any]
    skill_name: str
    function_name: str
    _handler: Callable | None = field(default=None, repr=False)


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
        self._tools: dict[str, ToolDefinition] = {}
        self._skill_instances: dict[str, Any] = {}
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
        parameters: dict[str, Any],
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

    def get_tools_for_llm(self, filter_skills: list[str] | None = None) -> list[dict[str, Any]]:
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
        arguments: str | dict[str, Any],
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
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool._handler(**args)),
                    timeout=self._timeout,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Format result
            if hasattr(result, "to_dict"):
                content = json.dumps(result.to_dict())
            elif hasattr(result, "data"):
                content = json.dumps({"success": getattr(result, "success", True), "data": result.data})
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

    def list_tools(self) -> list[dict[str, str]]:
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
