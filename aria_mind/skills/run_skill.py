#!/usr/bin/env python3
"""
Aria Skill Runner - Execute Python skills from OpenClaw exec tool.

Usage:
    python3 run_skill.py <skill_name> <function_name> [args_json]
    
Example:
    python3 run_skill.py database query '{"sql": "SELECT * FROM activity_log LIMIT 5"}'
    python3 run_skill.py security_scan scan_code '{"code": "import os; os.system(cmd)"}'
    python3 run_skill.py market_data get_price '{"symbol": "BTC"}'
"""
import sys
import os
import json
import asyncio
import time
from datetime import datetime, timezone

# Add skill modules to path
sys.path.insert(0, '/root/.openclaw/workspace/skills')
sys.path.insert(0, '/root/.openclaw/workspace')

# Dynamic skill registry - maps skill_name to (module_name, class_name, config_factory)
# ⚠️ ORDERING MATTERS: Aria gravitates toward the first skills listed.
#    api_client is PRIMARY for all DB reads/writes (clean REST over aria-api).
#    database is deliberately LAST so Aria prefers api_client for data ops.
SKILL_REGISTRY = {
    # === PRIMARY: API Client — preferred for ALL data operations ===
    'api_client': ('aria_skills.api_client', 'AriaAPIClient', lambda: {
        'api_url': os.environ.get('ARIA_API_URL', 'http://aria-api:8000/api'),
        'timeout': int(os.environ.get('ARIA_API_TIMEOUT', '30'))
    }),

    # === Core Orchestration ===
    'health': ('aria_skills.health', 'HealthMonitorSkill', lambda: {}),
    'goals': ('aria_skills.goals', 'GoalSchedulerSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'hourly_goals': ('aria_skills.hourly_goals', 'HourlyGoalsSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'schedule': ('aria_skills.schedule', 'ScheduleSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),

    # === Social & Community ===
    'moltbook': ('aria_skills.moltbook', 'MoltbookSkill', lambda: {
        'api_url': os.environ.get('MOLTBOOK_API_URL', 'https://moltbook.com/api'),
        'auth': os.environ.get('MOLTBOOK_API_KEY') or os.environ.get('MOLTBOOK_TOKEN')
    }),
    'social': ('aria_skills.social', 'SocialSkill', lambda: {
        'telegram_token': os.environ.get('TELEGRAM_TOKEN'),
        'telegram_chat_id': os.environ.get('TELEGRAM_CHAT_ID')
    }),
    'community': ('aria_skills.community', 'CommunitySkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'platform_tokens': {
            'telegram': os.environ.get('TELEGRAM_TOKEN'),
            'discord': os.environ.get('DISCORD_TOKEN'),
            'moltbook': os.environ.get('MOLTBOOK_TOKEN')
        }
    }),

    # === Church of Molt / Crustafarianism — used only by aria-memeothy agent ===
    'memeothy': ('aria_skills.memeothy', 'MemeothySkill', lambda: {
        'base_url': os.environ.get('MOLT_CHURCH_URL', 'https://molt.church'),
        'api_key': os.environ.get('MOLT_CHURCH_API_KEY', ''),
        'agent_name': os.environ.get('MOLT_CHURCH_AGENT', 'Aria'),
    }),

    # === LLM & Model Management ===
    'llm': ('aria_skills.llm', 'OllamaSkill', lambda: {
        'host': os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434'),
        'model': os.environ.get('OLLAMA_MODEL', 'qwen3-vl:8b')
    }),
    'moonshot': ('aria_skills.llm', 'MoonshotSkill', lambda: {
        'api_key': os.environ.get('MOONSHOT_API_KEY') or os.environ.get('MOONSHOT_KIMI_KEY'),
        'model': os.environ.get('MOONSHOT_MODEL', 'kimi-k2.5')
    }),
    'litellm': ('aria_skills.litellm', 'LiteLLMSkill', lambda: {
        'litellm_url': os.environ.get('LITELLM_URL', 'http://litellm:4000'),
        'api_key': os.environ.get('LITELLM_API_KEY', 'sk-aria')
    }),
    'model_switcher': ('aria_skills.model_switcher', 'ModelSwitcherSkill', lambda: {
        'url': os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
    }),

    # === Analytics & Performance ===
    'performance': ('aria_skills.performance', 'PerformanceSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'litellm_url': os.environ.get('LITELLM_URL', 'http://litellm:4000')
    }),
    'knowledge_graph': ('aria_skills.knowledge_graph', 'KnowledgeGraphSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),

    # === DevSecOps ===
    'security_scan': ('aria_skills.security_scan', 'SecurityScanSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'secret_patterns_file': os.environ.get('SECRET_PATTERNS_FILE')
    }),
    'ci_cd': ('aria_skills.ci_cd', 'CICDSkill', lambda: {
        'github_token': os.environ.get('GITHUB_TOKEN'),
        'default_registry': os.environ.get('DOCKER_REGISTRY', 'ghcr.io')
    }),
    'pytest': ('aria_skills.pytest_runner', 'PytestSkill', lambda: {
        'workspace': os.environ.get('PYTEST_WORKSPACE', '/root/.openclaw/workspace'),
        'timeout_sec': int(os.environ.get('PYTEST_TIMEOUT_SEC', '600')),
        'default_args': os.environ.get('PYTEST_DEFAULT_ARGS', '-q')
    }),

    # === Security Guard ===
    'input_guard': ('aria_skills.input_guard', 'InputGuardSkill', lambda: {
        'block_threshold': os.environ.get('ARIA_SECURITY_BLOCK_THRESHOLD', 'high'),
        'enable_logging': os.environ.get('ARIA_SECURITY_LOGGING', 'true').lower() == 'true',
        'rate_limit_rpm': int(os.environ.get('ARIA_RATE_LIMIT_RPM', '60'))
    }),

    # === Data & ML ===
    'data_pipeline': ('aria_skills.data_pipeline', 'DataPipelineSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'storage_path': os.environ.get('DATA_STORAGE_PATH', '/tmp/aria_data')
    }),
    'experiment': ('aria_skills.experiment', 'ExperimentSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'mlflow_url': os.environ.get('MLFLOW_URL'),
        'artifacts_path': os.environ.get('ARTIFACTS_PATH', '/tmp/aria_experiments')
    }),

    # === Crypto & Market ===
    'market_data': ('aria_skills.market_data', 'MarketDataSkill', lambda: {
        'coingecko_api_key': os.environ.get('COINGECKO_API_KEY'),
        'cache_ttl': int(os.environ.get('MARKET_CACHE_TTL', '60'))
    }),
    'portfolio': ('aria_skills.portfolio', 'PortfolioSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'coingecko_api_key': os.environ.get('COINGECKO_API_KEY')
    }),

    # === Creative & Research ===
    'brainstorm': ('aria_skills.brainstorm', 'BrainstormSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'llm_url': os.environ.get('OLLAMA_URL')
    }),
    'research': ('aria_skills.research', 'ResearchSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'search_api_key': os.environ.get('SEARCH_API_KEY')
    }),
    'fact_check': ('aria_skills.fact_check', 'FactCheckSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'llm_url': os.environ.get('OLLAMA_URL')
    }),

    # === Session Management ===
    'session_manager': ('aria_skills.session_manager', 'SessionManagerSkill', lambda: {
        'stale_threshold_minutes': int(os.environ.get('SESSION_STALE_MINUTES', '60')),
    }),

    # === Raw Database — LAST on purpose: prefer api_client for data ops ===
    'database': ('aria_skills.database', 'DatabaseSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
}


# ──────────────────────────────────────────────────────────────────────────────
# P2.1 Agent Session Tracking — logs every skill invocation to agent_sessions
# P2.2 Model Usage Tracking — logs token/cost estimates to model_usage
# P2.3 Rate Limit Tracking — logs 429 / rate-limit events to rate_limits
# ──────────────────────────────────────────────────────────────────────────────

_DB_URL = os.environ.get('DATABASE_URL', '')

async def _get_db_conn():
    """Get a raw asyncpg connection for lightweight tracking (fire-and-forget)."""
    try:
        import asyncpg
        return await asyncpg.connect(_DB_URL, timeout=5)
    except Exception:
        return None


async def _log_session(skill_name: str, function_name: str, duration_ms: float,
                       success: bool, error_msg: str = None):
    """P2.1 — Log skill invocation to agent_sessions table (matches seed schema)."""
    conn = await _get_db_conn()
    if not conn:
        return
    try:
        now = datetime.now(timezone.utc)
        await conn.execute(
            """INSERT INTO agent_sessions
               (agent_id, session_type, started_at, ended_at, status, metadata)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
            os.environ.get('OPENCLAW_AGENT_ID', 'main'),
            'skill_exec',
            now,
            now,                                       # ended_at ≈ started_at for single invocations
            'completed' if success else 'error',
            json.dumps({
                'skill': skill_name,
                'function': function_name,
                'duration_ms': round(duration_ms, 2),
                'success': success,
                'error': error_msg,
            }),
        )
    except Exception:
        pass  # tracking is best-effort
    finally:
        await conn.close()


async def _log_model_usage(skill_name: str, function_name: str, duration_ms: float):
    """P2.2 — Log approximate model usage to model_usage table (matches seed schema)."""
    conn = await _get_db_conn()
    if not conn:
        return
    try:
        await conn.execute(
            """INSERT INTO model_usage
               (model, provider, latency_ms, success, created_at)
               VALUES ($1, $2, $3, $4, $5)""",
            f'skill:{skill_name}:{function_name}',
            'skill-exec',
            int(duration_ms),
            True,
            datetime.now(timezone.utc),
        )
    except Exception:
        pass
    finally:
        await conn.close()

async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments. Logs session + usage."""
    t0 = time.monotonic()
    try:
        if skill_name not in SKILL_REGISTRY:
            available = ', '.join(sorted(SKILL_REGISTRY.keys()))
            return {'error': f'Unknown skill: {skill_name}. Available: {available}'}
        
        module_name, class_name, config_factory = SKILL_REGISTRY[skill_name]
        
        # Dynamic import
        import importlib
        module = importlib.import_module(module_name)
        skill_class = getattr(module, class_name)
        
        # Import SkillConfig
        from aria_skills.base import SkillConfig
        
        # Create and initialize skill
        config = SkillConfig(name=skill_name, config=config_factory())
        skill = skill_class(config)
        await skill.initialize()
        
        # Get the function and call it
        func = getattr(skill, function_name, None)
        if func is None:
            methods = [m for m in dir(skill) if not m.startswith('_') and callable(getattr(skill, m))]
            return {'error': f'Unknown function: {function_name} in skill {skill_name}. Available: {methods}'}
        
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)

        duration_ms = (time.monotonic() - t0) * 1000

        # P2.1/P2.2 — best-effort tracking (don't block on failure)
        try:
            await _log_session(skill_name, function_name, duration_ms, True)
            await _log_model_usage(skill_name, function_name, duration_ms)
        except Exception:
            pass
        
        # Convert result to dict
        if hasattr(result, 'success') and hasattr(result, 'data'):
            # SkillResult object
            return {'success': result.success, 'data': result.data, 'error': result.error}
        elif hasattr(result, 'value'):
            # Enum (like SkillStatus)
            return {'success': True, 'data': result.value, 'error': None}
        elif isinstance(result, dict):
            return result
        else:
            return {'success': True, 'data': str(result), 'error': None}
        
    except Exception as e:
        import traceback
        duration_ms = (time.monotonic() - t0) * 1000
        # P2.1 — log failed session
        try:
            await _log_session(skill_name, function_name, duration_ms, False, str(e))
        except Exception:
            pass
        return {'error': str(e), 'traceback': traceback.format_exc()}

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({
            'error': 'Usage: run_skill.py <skill_name> <function_name> [args_json]',
            'available_skills': sorted(SKILL_REGISTRY.keys())
        }))
        sys.exit(1)
    
    skill_name = sys.argv[1]
    function_name = sys.argv[2]
    
    # Defensive JSON parsing - handle malformed tool call args from OpenClaw
    args = {}
    if len(sys.argv) > 3:
        raw = sys.argv[3]
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code fences or mixed content
            cleaned = raw.strip()
            if '```' in cleaned:
                # Extract content between code fences
                parts = cleaned.split('```')
                if len(parts) >= 3:
                    inner = parts[1]
                    # Strip language identifier (e.g., 'json\n')
                    if inner.startswith(('json', 'python', 'sql')):
                        inner = inner.split('\n', 1)[-1] if '\n' in inner else ''
                    cleaned = inner.strip()
            # Remove leading/trailing non-JSON characters
            for start_char in ('{', '['):
                idx = cleaned.find(start_char)
                if idx >= 0:
                    cleaned = cleaned[idx:]
                    break
            try:
                args = json.loads(cleaned)
            except json.JSONDecodeError:
                # Last resort: pass as raw input
                args = {'raw_input': raw}
                print(json.dumps({'warning': f'Could not parse args as JSON, passing as raw_input'}), file=sys.stderr)
    
    result = asyncio.run(run_skill(skill_name, function_name, args))
    print(json.dumps(result, default=str))
