# aria_agents/loader.py
"""
Agent configuration loader.

Loads agent definitions from AGENTS.md.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from aria_agents.base import AgentConfig, AgentRole


class AgentLoader:
    """
    Loads agent configurations from AGENTS.md files.
    
    Format:
        ## agent_id
        - model: gemini-pro
        - parent: aria
        - capabilities: [research, summarize]
        - skills: [gemini, browser]
    """
    
    @staticmethod
    def load_from_file(filepath: str) -> Dict[str, AgentConfig]:
        """
        Load agent configs from a markdown file.
        
        Args:
            filepath: Path to AGENTS.md
            
        Returns:
            Dict of agent_id -> AgentConfig
        """
        path = Path(filepath)
        if not path.exists():
            return {}
        
        content = path.read_text(encoding="utf-8")
        return AgentLoader.parse_agents_md(content)
    
    @staticmethod
    def parse_agents_md(content: str) -> Dict[str, AgentConfig]:
        """
        Parse AGENTS.md content into AgentConfig objects.
        
        Args:
            content: Markdown content
            
        Returns:
            Dict of agent_id -> AgentConfig
        """
        agents = {}
        
        # Split by h2 headers (## agent_id)
        sections = re.split(r'^## ', content, flags=re.MULTILINE)
        
        for section in sections[1:]:  # Skip content before first ##
            lines = section.strip().split('\n')
            if not lines:
                continue
            
            # First line is the agent ID
            agent_id = lines[0].strip().lower().replace(' ', '_')
            
            # Parse properties
            props: Dict[str, Any] = {
                "id": agent_id,
                "name": lines[0].strip(),
            }
            
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('- '):
                    # Parse "- key: value" format
                    match = re.match(r'-\s*(\w+):\s*(.+)', line)
                    if match:
                        key = match.group(1).lower()
                        value = match.group(2).strip()
                        
                        # Parse list values [a, b, c]
                        if value.startswith('[') and value.endswith(']'):
                            value = [v.strip() for v in value[1:-1].split(',')]
                        
                        props[key] = value
            
            # Map role string to enum
            role_str = props.get("role", "coordinator")
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.COORDINATOR
            
            # Create config
            config = AgentConfig(
                id=agent_id,
                name=props.get("name", agent_id),
                role=role,
                model=props.get("model", "gemini-pro"),
                parent=props.get("parent"),
                capabilities=props.get("capabilities", []),
                skills=props.get("skills", []),
                temperature=float(props.get("temperature", 0.7)),
                max_tokens=int(props.get("max_tokens", 2048)),
            )
            
            agents[agent_id] = config
        
        return agents
    
    @staticmethod
    def get_agent_hierarchy(agents: Dict[str, AgentConfig]) -> Dict[str, List[str]]:
        """
        Build parent -> children hierarchy.
        
        Args:
            agents: Dict of agent configs
            
        Returns:
            Dict mapping parent_id -> list of child_ids
        """
        hierarchy: Dict[str, List[str]] = {}
        
        for agent_id, config in agents.items():
            if config.parent:
                if config.parent not in hierarchy:
                    hierarchy[config.parent] = []
                hierarchy[config.parent].append(agent_id)
        
        return hierarchy
