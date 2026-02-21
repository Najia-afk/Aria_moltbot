# Skill Health Dashboard - Metrics Schema

## Overview
Lightweight health monitoring for skill performance tracking.

## Metrics Collected

### Per-Skill Metrics (Aggregated Hourly)
| Field | Type | Description |
|-------|------|-------------|
| skill_name | string | Skill identifier |
| hour_bucket | datetime | Aggregation window |
| total_calls | int | Number of invocations |
| success_count | int | Successful executions |
| error_count | int | Failed executions |
| avg_duration_ms | float | Mean execution time |
| p95_duration_ms | float | 95th percentile latency |
| tokens_used | int | Approximate token consumption |

### Error Tracking
| Field | Type | Description |
|-------|------|-------------|
| error_type | string | Exception category |
| skill_name | string | Source skill |
| timestamp | datetime | When occurred |
| count | int | Frequency in window |

### Dashboard Views
1. **Executive Summary**: Top 5 skills by error rate, overall health score
2. **Skill Detail**: Per-skill trends over 24h/7d/30d
3. **Error Explorer**: Drill-down by error type and skill

## Storage
- Working memory keys: `skill_health:{skill_name}:{hour_bucket}`
- Retention: 30 days (auto-prune via daily job)
- Aggregation: Background task every hour

## Next Steps
- [ ] Implement metrics collection in skill runner
- [ ] Create aggregation background job
- [ ] Build simple CLI view command
