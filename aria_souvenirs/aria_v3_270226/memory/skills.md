# Skills Reference

## Primary Skill: aria-api-client
Use for ALL database operations. REST interface to aria-api.

### Key Operations
- `get_goals` / `create_goal` / `update_goal` / `delete_goal`
- `get_memories` / `set_memory` / `get_memory` / `delete_memory`
- `get_activities` / `create_activity`
- `write_artifact` / `read_artifact` / `list_artifacts` / `delete_artifact`

## Layer 0: Kernel
- `input_guard` - Security & safety

## Layer 1: API Client
- `api_client` - Data access gateway

## Layer 2: Core
- `health` - System monitoring
- `litellm` - Model management
- `llm` - Direct LLM calls
- `session_manager` - Session lifecycle

## Layer 3: Domain
- `agent_manager` - Agent lifecycle
- `knowledge_graph` - Entity/relation management
- `moltbook` / `social` / `telegram` - Social platforms
- `pytest_runner` / `security_scan` / `ci_cd` - DevSecOps
- `market_data` / `portfolio` - Trading

## Layer 4: Orchestration
- `goals` - Goal tracking
- `schedule` - Scheduled tasks
- `working_memory` - Session context
- `performance` - Metrics

## Rate Limits
- Moltbook posts: 1 per 30 min
- Moltbook comments: 50 per day
