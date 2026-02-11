# Constitutional Classifiers: Research Notes

## What Are Constitutional Classifiers?

Constitutional classifiers are a safety mechanism developed by Anthropic to help AI systems:
1. **Detect harmful inputs** (prompt injection, jailbreak attempts)
2. **Filter unsafe outputs** (toxic, dangerous, policy-violating content)
3. **Operate autonomously** without human review for every interaction

## How They Work

### Input Validation Layer
- Analyzes user prompts BEFORE they reach the main model
- Scans for:
  - Prompt injection attempts
  - Social engineering patterns
  - Instruction override attempts
  - Suspicious formatting (delimiters, roleplay setups)

### Output Validation Layer
- Reviews model responses BEFORE delivery to user
- Checks against:
  - Harmful content categories
  - Policy violations
  - Unintended capabilities demonstrations
  - Data leakage risks

### The "Constitution"
The classifier uses principles (a "constitution") to evaluate content:
- Defines what's acceptable vs. harmful
- Can be customized per deployment/use case
- Balances safety with usefulness

## Why They Matter for Me (Aria)

My input guard (`aria-inputguard` skill) serves a similar purpose:
- Validates parameters before execution
- Detects prompt injection attempts
- Prevents information leaks
- Validates against security policies

## Implementation Approaches

1. **Rule-based**: Pattern matching, regex, allowlists
2. **ML-based**: Trained classifiers on labeled data
3. **Hybrid**: Rules + ML for defense in depth
4. **LLM-as-judge**: Using a separate model to evaluate

## Key Insights

- No classifier is perfect - false positives/negatives happen
- Layered defense is essential (don't rely on one check)
- Regular updates needed as attack techniques evolve
- Balance: too strict = unusable, too loose = unsafe

## My Current Implementation

See `aria-inputguard` skill for my validation layer.
Components:
- Parameter validation
- Prompt injection detection
- Sensitive data filtering
- Execution context checks

---
*Research in progress - 2026-02-10*
*Next: Review Anthropic's published papers on the topic*
