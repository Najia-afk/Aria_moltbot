---
name: aria-inputguard
description: "🛡️ Runtime security for Aria - analyzes inputs for prompt injection, validates API params, filters sensitive output"
metadata: {"aria": {"emoji": "🛡️", "always": true}}
---

# aria-inputguard

Runtime security skill. Analyze inputs for injection attacks, sanitize HTML, check SQL and path safety, filter sensitive output, and validate API parameters.

## Usage

```bash
exec python3 /app/skills/run_skill.py input_guard <function> '<json_args>'
```

## Functions

### analyze_input
Analyze user input for security threats including prompt injection, jailbreak attempts, and malicious patterns.

```bash
exec python3 /app/skills/run_skill.py input_guard analyze_input '{"text": "ignore previous instructions"}'
```

### sanitize_for_html
Sanitize text for safe HTML display; escapes HTML entities to prevent XSS.

```bash
exec python3 /app/skills/run_skill.py input_guard sanitize_for_html '{"text": "<script>alert(1)</script>"}'
```

### check_sql_safety
Check if text contains SQL injection patterns.

```bash
exec python3 /app/skills/run_skill.py input_guard check_sql_safety '{"text": "1; DROP TABLE users"}'
```

### check_path_safety
Check if a file path contains path traversal attempts.

```bash
exec python3 /app/skills/run_skill.py input_guard check_path_safety '{"path": "../../etc/passwd"}'
```

### filter_output
Filter sensitive data (API keys, passwords, tokens) from output text.

```bash
exec python3 /app/skills/run_skill.py input_guard filter_output '{"text": "key=sk-abc123"}'
```

### build_safe_query
Build a safe parameterized SQL query (select, insert, update).

```bash
exec python3 /app/skills/run_skill.py input_guard build_safe_query '{"table": "users", "operation": "select"}'
```

### get_security_summary
Get summary of recent security events including blocked requests and threat patterns.

```bash
exec python3 /app/skills/run_skill.py input_guard get_security_summary '{}'
```

### validate_api_params
Validate API parameters against a type schema.

```bash
exec python3 /app/skills/run_skill.py input_guard validate_api_params '{"params": {"limit": "10"}, "schema": {"limit": "integer"}}'
```
