#!/usr/bin/env python3
"""
Aria Skill Runner - Execute Python skills from OpenClaw exec tool.

Usage:
    python3 aria_mind/skills/run_skill.py <skill_name> <function_name> [args_json]
    
Example:
    python3 aria_mind/skills/run_skill.py api_client get_activities '{"limit": 5}'
    python3 aria_mind/skills/run_skill.py security_scan scan_directory '{"directory": "/workspace", "extensions": [".py"]}'
    python3 aria_mind/skills/run_skill.py market_data get_price '{"symbol": "BTC"}'
"""
import sys
import os
import json
import asyncio
import time
from pathlib import Path
from typing import Optional, Tuple

# Add skill modules to path
sys.path.insert(0, '/root/.openclaw/workspace/skills')
sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from aria_mind.skills._skill_registry import SKILL_REGISTRY, _merge_registries
    from aria_mind.skills._tracking import _log_model_usage, _log_session
    from aria_mind.skills._tracking import _log_skill_invocation
    from aria_mind.skills._cli_tools import (
        handle_export_catalog,
        handle_health_check_all,
        handle_list_skills,
    )
    from aria_mind.skills._coherence import (
        workspace_root as _coh_workspace_root,
        has_skill_changes as _coh_has_skill_changes,
        validate_skill_coherence as _coh_validate_skill_coherence,
        write_aria_mind_run_report as _coh_write_aria_mind_run_report,
        collect_skill_alignment_report as _coh_collect_skill_alignment_report,
        write_skill_alignment_report as _coh_write_skill_alignment_report,
    )
    from aria_mind.skills._skill_introspection import collect_skill_info
    from aria_mind.skills._kernel_router import auto_route_task_to_skills
except ModuleNotFoundError:
    from _skill_registry import SKILL_REGISTRY, _merge_registries
    from _tracking import _log_model_usage, _log_session
    from _tracking import _log_skill_invocation
    from _cli_tools import (
        handle_export_catalog,
        handle_health_check_all,
        handle_list_skills,
    )
    from _coherence import (
        workspace_root as _coh_workspace_root,
        has_skill_changes as _coh_has_skill_changes,
        validate_skill_coherence as _coh_validate_skill_coherence,
        write_aria_mind_run_report as _coh_write_aria_mind_run_report,
        collect_skill_alignment_report as _coh_collect_skill_alignment_report,
        write_skill_alignment_report as _coh_write_skill_alignment_report,
    )
    from _skill_introspection import collect_skill_info
    from _kernel_router import auto_route_task_to_skills


_SUPPORT_SKILL_DIRS = {'_template', '__pycache__', 'pipelines'}


def _is_allowed_skill_method(function_name: str) -> bool:
    if not isinstance(function_name, str):
        return False
    fn = function_name.strip()
    if not fn or fn.startswith("_"):
        return False
    return fn.isidentifier()


def _workspace_root() -> Path:
    return _coh_workspace_root()


def _skill_dir(skill_name: str) -> Path:
    return _workspace_root() / 'aria_skills' / skill_name


def _has_skill_changes(skill_name: str) -> bool:
    return _coh_has_skill_changes(_workspace_root(), skill_name)


def _validate_skill_coherence(skill_name: str) -> dict:
    return _coh_validate_skill_coherence(
        skill_name,
        workspace_root_fn=_workspace_root,
        has_skill_changes_fn=_has_skill_changes,
    )


def _write_aria_mind_run_report(report: dict):
    try:
        _coh_write_aria_mind_run_report(report, workspace_root_fn=_workspace_root)
    except Exception:
        pass


def _collect_skill_alignment_report(include_support: bool = False) -> dict:
    return _coh_collect_skill_alignment_report(
        include_support=include_support,
        workspace_root_fn=_workspace_root,
        support_skill_dirs=_SUPPORT_SKILL_DIRS,
    )


def _write_skill_alignment_report(include_support: bool = False) -> dict:
    return _coh_write_skill_alignment_report(
        include_support=include_support,
        workspace_root_fn=_workspace_root,
        support_skill_dirs=_SUPPORT_SKILL_DIRS,
    )


async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments. Logs session + usage."""
    t0 = time.monotonic()
    requested_skill_name = skill_name
    try:
        # Normalize canonical "aria-*" names to python underscore names
        if skill_name.startswith("aria-"):
            skill_name = skill_name[5:].replace("-", "_")

        if not _is_allowed_skill_method(function_name):
            duration_ms = (time.monotonic() - t0) * 1000
            error_msg = (
                "Invalid function_name. Only public python identifiers are allowed "
                "(no private/dunder methods)."
            )
            _write_aria_mind_run_report({
                'requested_skill_name': requested_skill_name,
                'normalized_skill_name': skill_name,
                'function_name': function_name,
                'args_keys': sorted(list((args or {}).keys())) if isinstance(args, dict) else [],
                'status': 'failed',
                'error': error_msg,
                'duration_ms': round(duration_ms, 2),
                'mandatory_enforced': True,
            })
            return {'error': error_msg}

        if not isinstance(args, dict):
            duration_ms = (time.monotonic() - t0) * 1000
            error_msg = 'Invalid args payload. Expected a JSON object.'
            _write_aria_mind_run_report({
                'requested_skill_name': requested_skill_name,
                'normalized_skill_name': skill_name,
                'function_name': function_name,
                'args_keys': [],
                'status': 'failed',
                'error': error_msg,
                'duration_ms': round(duration_ms, 2),
                'mandatory_enforced': True,
            })
            return {'error': error_msg}

        coherence = _validate_skill_coherence(skill_name)

        if skill_name not in SKILL_REGISTRY:
            available = ', '.join(sorted(SKILL_REGISTRY.keys()))
            report = {
                'requested_skill_name': requested_skill_name,
                'normalized_skill_name': skill_name,
                'function_name': function_name,
                'args_keys': sorted(list((args or {}).keys())),
                'status': 'failed',
                'error': f'Unknown skill: {skill_name}. Available: {available}',
                'duration_ms': round((time.monotonic() - t0) * 1000, 2),
                'coherence': coherence,
                'mandatory_enforced': True,
            }
            _write_aria_mind_run_report(report)
            return {'error': f'Unknown skill: {skill_name}. Available: {available}'}

        # Mandatory policy: if this skill changed, all 3 files must be coherent
        if coherence.get('has_changes') and not coherence.get('coherent'):
            duration_ms = (time.monotonic() - t0) * 1000
            error_msg = (
                'Skill coherence check failed for changed skill. '
                'Require __init__.py + skill.json + SKILL.md to be coherent before execution.'
            )
            report = {
                'requested_skill_name': requested_skill_name,
                'normalized_skill_name': skill_name,
                'function_name': function_name,
                'args_keys': sorted(list((args or {}).keys())),
                'status': 'blocked_coherence',
                'error': error_msg,
                'duration_ms': round(duration_ms, 2),
                'coherence': coherence,
                'mandatory_enforced': True,
            }
            _write_aria_mind_run_report(report)
            return {
                'error': error_msg,
                'coherence': coherence,
            }
        
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
            report = {
                'requested_skill_name': requested_skill_name,
                'normalized_skill_name': skill_name,
                'function_name': function_name,
                'args_keys': sorted(list((args or {}).keys())),
                'status': 'failed',
                'error': f'Unknown function: {function_name} in skill {skill_name}. Available: {methods}',
                'duration_ms': round((time.monotonic() - t0) * 1000, 2),
                'coherence': coherence,
                'mandatory_enforced': True,
            }
            _write_aria_mind_run_report(report)
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
            await _log_skill_invocation(skill_name, function_name, duration_ms, True)
        except Exception:
            pass

        _write_aria_mind_run_report({
            'requested_skill_name': requested_skill_name,
            'normalized_skill_name': skill_name,
            'function_name': function_name,
            'args_keys': sorted(list((args or {}).keys())),
            'status': 'success',
            'duration_ms': round(duration_ms, 2),
            'coherence': coherence,
            'mandatory_enforced': True,
        })
        
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
            await _log_skill_invocation(skill_name, function_name, duration_ms, False, str(e))
        except Exception:
            pass

        _write_aria_mind_run_report({
            'requested_skill_name': requested_skill_name,
            'normalized_skill_name': skill_name,
            'function_name': function_name,
            'args_keys': sorted(list((args or {}).keys())),
            'status': 'failed',
            'error': str(e),
            'duration_ms': round(duration_ms, 2),
            'coherence': _validate_skill_coherence(skill_name),
            'mandatory_enforced': True,
        })
        return {'error': str(e), 'traceback': traceback.format_exc()}


def _parse_args_payload(raw: Optional[str]) -> Tuple[dict, Optional[str]]:
    """Defensive JSON parsing for CLI payloads."""
    if raw is None:
        return {}, None

    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if '```' in cleaned:
            parts = cleaned.split('```')
            if len(parts) >= 3:
                inner = parts[1]
                if inner.startswith(('json', 'python', 'sql')):
                    inner = inner.split('\n', 1)[-1] if '\n' in inner else ''
                cleaned = inner.strip()

        for start_char in ('{', '['):
            idx = cleaned.find(start_char)
            if idx >= 0:
                cleaned = cleaned[idx:]
                break

        try:
            return json.loads(cleaned), None
        except json.JSONDecodeError:
            truncated = raw[:2000]
            if len(raw) > 2000:
                return {
                    'raw_input': truncated,
                    'truncated': True,
                    'original_length': len(raw),
                }, 'Could not parse args as JSON, passing truncated raw_input'
            return {'raw_input': raw}, 'Could not parse args as JSON, passing as raw_input'

if __name__ == '__main__':
    import argparse

    # Parse known args first to not break positional interface
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--list-skills", action="store_true")
    parser.add_argument("--health-check-all", action="store_true")
    parser.add_argument("--export-catalog", action="store_true")
    parser.add_argument("--coherence-report", action="store_true")
    parser.add_argument("--include-support", action="store_true")
    parser.add_argument("--skill-info", type=str)
    parser.add_argument("--auto-task", type=str)
    parser.add_argument("--route-limit", type=int, default=5)
    parser.add_argument("--route-no-info", action="store_true")
    parser.add_argument("--auto-exec", action="store_true")
    parser.add_argument("--auto-exec-function", type=str, default="health_check")
    parser.add_argument("--auto-exec-args", type=str, default="{}")
    cli_args, remaining = parser.parse_known_args()

    if cli_args.list_skills:
        handle_list_skills()

    if cli_args.export_catalog:
        handle_export_catalog()

    if cli_args.health_check_all:
        handle_health_check_all()

    if cli_args.coherence_report:
        out = _write_skill_alignment_report(include_support=cli_args.include_support)
        print(json.dumps({
            'report_path': out['path'],
            'count': out['report']['count'],
            'coherent_count': out['report']['coherent_count'],
            'incoherent_count': out['report']['incoherent_count'],
            'coherent': out['report']['coherent'],
        }))
        sys.exit(0)

    if cli_args.skill_info:
        info = collect_skill_info(
            skill_name=cli_args.skill_info,
            registry=SKILL_REGISTRY,
            validate_skill_coherence_fn=_validate_skill_coherence,
            workspace_root_fn=_workspace_root,
        )
        print(json.dumps(info, default=str))
        sys.exit(0)

    if cli_args.auto_task:
        route = asyncio.run(
            auto_route_task_to_skills(
                task=cli_args.auto_task,
                limit=max(1, cli_args.route_limit or 5),
                registry=SKILL_REGISTRY,
                validate_skill_coherence_fn=_validate_skill_coherence,
                workspace_root_fn=_workspace_root,
                include_info=not cli_args.route_no_info,
            )
        )

        if cli_args.auto_exec:
            candidates = route.get('candidates') or []
            if not candidates:
                print(json.dumps({
                    'error': 'No candidate skills available for auto execution',
                    'task': cli_args.auto_task,
                    'route': route,
                }, default=str))
                sys.exit(1)

            exec_args, warning = _parse_args_payload(cli_args.auto_exec_args)
            selected = candidates[0]
            selected_skill = selected.get('skill_name')
            if not selected_skill:
                print(json.dumps({
                    'error': 'Top candidate did not include skill_name',
                    'task': cli_args.auto_task,
                    'route': route,
                }, default=str))
                sys.exit(1)

            execution = asyncio.run(
                run_skill(
                    selected_skill,
                    cli_args.auto_exec_function,
                    exec_args,
                )
            )

            payload = {
                'task': cli_args.auto_task,
                'route_source': route.get('route_source'),
                'route_diagnostics': route.get('route_diagnostics', []),
                'selected': selected,
                'execution': execution,
            }
            if warning:
                payload['warning'] = warning
            print(json.dumps(payload, default=str))
            sys.exit(0)

        print(json.dumps(route, default=str))
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
        args, warning = _parse_args_payload(remaining[2])
        if warning:
            print(json.dumps({'warning': warning}), file=sys.stderr)
    
    result = asyncio.run(run_skill(skill_name, function_name, args))
    print(json.dumps(result, default=str))
