```skill
---
name: aria-factcheck
description: "🔍 Fact-checking and claim verification for Journalist"
metadata: {"openclaw": {"emoji": "🔍"}}
---
```

# aria-factcheck

Fact-checking and claim verification. Extract claims from text, assess credibility, compare sources, and generate verdict summaries.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check <function> '<json_args>'
```

## Functions

### extract_claims
Extract checkable claims from text.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check extract_claims '{"text": "The earth is flat and the moon is made of cheese."}'
```

### assess_claim
Assess a claim and generate verdict.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check assess_claim '{"claim": "The earth is flat"}'
```

### quick_check
Quick assessment of a claim's characteristics.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check quick_check '{"claim": "Water boils at 100C"}'
```

### compare_sources
Compare how different sources report a claim.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check compare_sources '{"claim": "...", "sources": ["source1", "source2"]}'
```

### get_verdict_summary
Get summary of verdicts.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py fact_check get_verdict_summary '{}'
```
