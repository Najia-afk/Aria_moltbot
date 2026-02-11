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

# Load default model names from models.yaml (single source of truth)
try:
    from aria_models.loader import load_catalog as _load_catalog
    _cat = _load_catalog()
    _kimi_model = _cat.get("models", {}).get("kimi", {}).get("litellm", {}).get("model", "")
    _DEFAULT_KIMI_MODEL = _kimi_model.removeprefix("moonshot/") or "kimi-k2.5"
    _ollama_model = _cat.get("models", {}).get("qwen-cpu-fallback", {}).get("litellm", {}).get("model", "")
    _DEFAULT_OLLAMA_MODEL = _ollama_model.removeprefix("ollama/") or "qwen2.5:3b"
except Exception:
    _DEFAULT_KIMI_MODEL = "kimi-k2.5"
    _DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"

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
        'model': os.environ.get('OLLAMA_MODEL', _DEFAULT_OLLAMA_MODEL)
    }),
    'moonshot': ('aria_skills.llm', 'MoonshotSkill', lambda: {
        'api_key': os.environ.get('MOONSHOT_API_KEY') or os.environ.get('MOONSHOT_KIMI_KEY'),
        'model': os.environ.get('MOONSHOT_MODEL', _DEFAULT_KIMI_MODEL)
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


def _merge_registries():
    """Sync decorator-registered skills into SKILL_REGISTRY."""
    try:
        from aria_skills.registry import SkillRegistry
        for name, skill_cls in SkillRegistry._skill_classes.items():
            if name not in SKILL_REGISTRY:
                mod = skill_cls.__module__
                SKILL_REGISTRY[name] = (mod, skill_cls.__name__, lambda: {})
    except Exception:
        pass  # registry may not be importable in all environments

_merge_registries()


# ──────────────────────────────────────────────────────────────────────────────
# P2.1 Agent Session Tracking — logs every skill invocation via aria-api
# P2.2 Model Usage Tracking — logs token/cost estimates via aria-api
# Architecture: Skills → api_client (httpx) → aria-api → SQLAlchemy → DB
# ──────────────────────────────────────────────────────────────────────────────

_API_BASE = os.environ.get('ARIA_API_URL', 'http://aria-api:8000/api').rstrip('/')

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

import logging as _logging
_tracker_log = _logging.getLogger('aria.skill_tracker')


async def _api_post(endpoint: str, payload: dict) -> bool:
    """Fire-and-forget POST to aria-api. Returns True on success."""
    if not _HAS_HTTPX:
        _tracker_log.debug('httpx not installed — skipping tracking POST')
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f'{_API_BASE}{endpoint}', json=payload)
            resp.raise_for_status()
            return True
    except Exception as exc:
        _tracker_log.debug('Tracking POST %s failed: %s', endpoint, exc)
        return False


def _log_locally(event_type: str, data: dict):
    """Fallback: log tracking data locally when the API is unreachable."""
    _tracker_log.warning('API unreachable — logging %s locally: %s', event_type, json.dumps(data, default=str))


async def _log_session(skill_name: str, function_name: str, duration_ms: float,
                       success: bool, error_msg: str = None):
    """P2.1 — Log skill invocation to agent_sessions via aria-api."""
    payload = {
        'agent_id': os.environ.get('OPENCLAW_AGENT_ID', 'main'),
        'session_type': 'skill_exec',
        'status': 'completed' if success else 'error',
        'metadata': {
            'skill': skill_name,
            'function': function_name,
            'duration_ms': round(duration_ms, 2),
            'success': success,
            'error': error_msg,
        },
    }
    ok = await _api_post('/sessions', payload)
    if not ok:
        _log_locally('session', payload)


async def _log_model_usage(skill_name: str, function_name: str, duration_ms: float):
    """P2.2 — Log approximate model usage via aria-api."""
    payload = {
        'model': f'skill:{skill_name}:{function_name}',
        'provider': 'skill-exec',
        'latency_ms': int(duration_ms),
        'success': True,
    }
    ok = await _api_post('/model-usage', payload)
    if not ok:
        _log_locally('model_usage', payload)

async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments. Logs session + usage."""
    t0 = time.monotonic()
    try:
        # Normalize canonical "aria-*" names to python underscore names
        if skill_name.startswith("aria-"):
            skill_name = skill_name[5:].replace("-", "_")

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
    import argparse
    import importlib
    from pathlib import Path

    # Parse known args first to not break positional interface
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--list-skills", action="store_true")
    parser.add_argument("--health-check-all", action="store_true")
    parser.add_argument("--export-catalog", action="store_true")
    cli_args, remaining = parser.parse_known_args()

    if cli_args.list_skills:
        print(f"{'Name':<22} {'Canonical':<24} {'Module':<40} {'skill.json'}")
        print("-" * 100)
        for name, (mod, cls, _) in sorted(SKILL_REGISTRY.items()):
            canonical = f"aria-{name.replace('_', '-')}"
            has_json = Path(f"aria_skills/{name}/skill.json").exists()
            print(f"{name:<22} {canonical:<24} {mod:<40} {'YES' if has_json else 'no'}")
        sys.exit(0)

    if cli_args.export_catalog:
        catalog = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "skills": []
        }
        for name, (mod, cls_name, _) in sorted(SKILL_REGISTRY.items()):
            try:
                module = importlib.import_module(mod)
                skill_cls = getattr(module, cls_name)
                methods = [m for m in dir(skill_cls)
                           if not m.startswith('_') and callable(getattr(skill_cls, m, None))
                           and m not in ('initialize', 'health_check', 'name', 'canonical_name', 'close', 'is_available', 'status')]
                catalog["skills"].append({
                    "name": name,
                    "canonical_name": f"aria-{name.replace('_', '-')}",
                    "module": mod,
                    "class": cls_name,
                    "methods": methods
                })
            except Exception as e:
                catalog["skills"].append({"name": name, "module": mod, "error": str(e)})
        Path("aria_memories/exports").mkdir(parents=True, exist_ok=True)
        Path("aria_memories/exports/skill_catalog.json").write_text(json.dumps(catalog, indent=2))
        print(f"Catalog written: {len(catalog['skills'])} skills -> aria_memories/exports/skill_catalog.json")
        sys.exit(0)

    if cli_args.health_check_all:
        async def _check_all():
            for name, (mod, cls_name, config_fn) in sorted(SKILL_REGISTRY.items()):
                try:
                    module = importlib.import_module(mod)
                    skill_cls = getattr(module, cls_name)
                    from aria_skills.base import SkillConfig
                    config = SkillConfig(name=name, config=config_fn())
                    skill = skill_cls(config=config)
                    ok = await skill.initialize()
                    status = (await skill.health_check()).value if ok else "INIT_FAILED"
                    print(f"{name:<22} {status}")
                except Exception as e:
                    print(f"{name:<22} ERROR: {e}")
        asyncio.run(_check_all())
        sys.exit(0)

    # Original positional argument interface
    if len(remaining) < 2:
        print(json.dumps({
            'error': 'Usage: run_skill.py <skill_name> <function_name> [args_json]',
            'available_skills': sorted(SKILL_REGISTRY.keys())
        }))
        sys.exit(1)
    
    skill_name = remaining[0]
    function_name = remaining[1]
    
    # Defensive JSON parsing - handle malformed tool call args from OpenClaw
    args = {}
    if len(remaining) > 2:
        raw = remaining[2]
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
