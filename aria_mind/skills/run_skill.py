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
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add skill modules to path
sys.path.insert(0, '/root/.openclaw/workspace/skills')
sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aria_mind.skills._skill_registry import SKILL_REGISTRY, _merge_registries
from aria_mind.skills._tracking import _log_model_usage, _log_session
from aria_mind.skills._cli_tools import (
    handle_export_catalog,
    handle_health_check_all,
    handle_list_skills,
)


_SUPPORT_SKILL_DIRS = {'_template', '__pycache__', 'pipelines'}


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _skill_dir(skill_name: str) -> Path:
    return _workspace_root() / 'aria_skills' / skill_name


def _has_skill_changes(skill_name: str) -> bool:
    """Return True when git reports changes under this skill directory."""
    try:
        root = _workspace_root()
        rel = f"aria_skills/{skill_name}"
        proc = subprocess.run(
            ['git', 'status', '--porcelain', '--', rel],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return bool((proc.stdout or '').strip())
    except Exception:
        return False


def _validate_skill_coherence(skill_name: str) -> dict:
    """Validate __init__.py, skill.json, SKILL.md coherence for a skill directory."""
    skill_path = _skill_dir(skill_name)
    report = {
        'skill_name': skill_name,
        'canonical_name': f"aria-{skill_name.replace('_', '-')}",
        'skill_path': str(skill_path),
        'has_changes': _has_skill_changes(skill_name),
        'checks': {},
        'errors': [],
        'warnings': [],
        'coherent': True,
    }

    init_path = skill_path / '__init__.py'
    json_path = skill_path / 'skill.json'
    md_path = skill_path / 'SKILL.md'

    report['checks']['init_exists'] = init_path.exists()
    report['checks']['json_exists'] = json_path.exists()
    report['checks']['md_exists'] = md_path.exists()

    if not init_path.exists():
        report['errors'].append('Missing __init__.py')
    if not json_path.exists():
        report['errors'].append('Missing skill.json')
    if not md_path.exists():
        report['errors'].append('Missing SKILL.md')

    if json_path.exists():
        try:
            manifest = json.loads(json_path.read_text(encoding='utf-8'))
            expected_name = report['canonical_name']
            actual_name = manifest.get('name')
            report['checks']['json_name_matches'] = actual_name == expected_name
            report['checks']['manifest_name'] = actual_name
            if actual_name != expected_name:
                report['errors'].append(
                    f"skill.json name mismatch: expected '{expected_name}', got '{actual_name}'"
                )
        except Exception as exc:
            report['checks']['json_name_matches'] = False
            report['errors'].append(f'skill.json parse error: {exc}')

    if init_path.exists():
        try:
            init_text = init_path.read_text(encoding='utf-8')
            has_registry = '@SkillRegistry.register' in init_text
            has_skill_class = 'class ' in init_text and 'Skill' in init_text
            report['checks']['init_registry_decorator'] = has_registry
            report['checks']['init_has_skill_class'] = has_skill_class
            if not has_registry:
                report['warnings'].append('No @SkillRegistry.register in __init__.py')
            if not has_skill_class:
                report['errors'].append('No Skill class definition found in __init__.py')
        except Exception as exc:
            report['errors'].append(f'__init__.py read error: {exc}')

    if md_path.exists():
        try:
            md_text = md_path.read_text(encoding='utf-8').lower()
            expected_canonical = report['canonical_name']
            expected_python = skill_name
            mentions_name = (expected_canonical in md_text) or (expected_python in md_text)
            report['checks']['md_mentions_skill'] = mentions_name
            if not mentions_name:
                report['warnings'].append(
                    f"SKILL.md does not mention '{expected_canonical}' or '{expected_python}'"
                )
        except Exception as exc:
            report['errors'].append(f'SKILL.md read error: {exc}')

    report['coherent'] = len(report['errors']) == 0
    return report


def _write_aria_mind_run_report(report: dict):
    """Persist mandatory skill-run report into aria_mind/skills."""
    root = _workspace_root()
    reports_dir = root / 'aria_mind' / 'skills'
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = {
        **report,
        'reported_at': datetime.now(timezone.utc).isoformat(),
    }

    latest_path = reports_dir / 'last_skill_run_report.json'
    latest_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')

    jsonl_path = reports_dir / 'skill_run_reports.jsonl'
    with jsonl_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(report, default=str) + '\n')


def _collect_skill_alignment_report(include_support: bool = False) -> dict:
    root = _workspace_root() / 'aria_skills'
    rows = []
    if not root.exists():
        return {
            'root': str(root),
            'skills': [],
            'count': 0,
            'coherent_count': 0,
            'incoherent_count': 0,
            'coherent': True,
        }

    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if not include_support and entry.name in _SUPPORT_SKILL_DIRS:
            continue

        skill_name = entry.name
        canonical = f"aria-{skill_name.replace('_', '-')}"
        init_path = entry / '__init__.py'
        json_path = entry / 'skill.json'
        md_path = entry / 'SKILL.md'

        row = {
            'skill_name': skill_name,
            'canonical_name': canonical,
            'is_support_dir': skill_name in _SUPPORT_SKILL_DIRS,
            'has_init': init_path.exists(),
            'has_skill_json': json_path.exists(),
            'has_skill_md': md_path.exists(),
            'name_matches': None,
            'errors': [],
            'coherent': True,
        }

        if not row['has_init']:
            row['errors'].append('Missing __init__.py')
        if not row['has_skill_json']:
            row['errors'].append('Missing skill.json')
        if not row['has_skill_md']:
            row['errors'].append('Missing SKILL.md')

        if row['has_skill_json']:
            try:
                manifest = json.loads(json_path.read_text(encoding='utf-8'))
                manifest_name = manifest.get('name')
                row['manifest_name'] = manifest_name
                row['name_matches'] = manifest_name == canonical
                if manifest_name != canonical:
                    row['errors'].append(
                        f"skill.json name mismatch: expected '{canonical}', got '{manifest_name}'"
                    )
            except Exception as exc:
                row['name_matches'] = False
                row['errors'].append(f'skill.json parse error: {exc}')

        row['coherent'] = len(row['errors']) == 0
        rows.append(row)

    coherent_count = sum(1 for row in rows if row['coherent'])
    return {
        'root': str(root),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'skills': rows,
        'count': len(rows),
        'coherent_count': coherent_count,
        'incoherent_count': len(rows) - coherent_count,
        'coherent': coherent_count == len(rows),
        'include_support': include_support,
    }


def _write_skill_alignment_report(include_support: bool = False) -> dict:
    report = _collect_skill_alignment_report(include_support=include_support)
    reports_dir = _workspace_root() / 'aria_mind' / 'skills'
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_path = reports_dir / 'skill_alignment_report.json'
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    return {'path': str(out_path), 'report': report}


async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments. Logs session + usage."""
    t0 = time.monotonic()
    requested_skill_name = skill_name
    try:
        # Normalize canonical "aria-*" names to python underscore names
        if skill_name.startswith("aria-"):
            skill_name = skill_name[5:].replace("-", "_")

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

if __name__ == '__main__':
    import argparse

    # Parse known args first to not break positional interface
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--list-skills", action="store_true")
    parser.add_argument("--health-check-all", action="store_true")
    parser.add_argument("--export-catalog", action="store_true")
    parser.add_argument("--coherence-report", action="store_true")
    parser.add_argument("--include-support", action="store_true")
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
