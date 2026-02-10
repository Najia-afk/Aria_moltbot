# Orphan Tables Backup Manifest (S-37)

Before running the Alembic migration `s37_drop_orphans`, back up these 9 tables
using `pg_dump` or equivalent:

1. `bubble_monetization`
2. `model_cost_reference`
3. `model_discovery_log`
4. `moltbook_users`
5. `opportunities`
6. `secops_work`
7. `spending_alerts`
8. `spending_log`
9. `yield_positions`

## Backup command example

```bash
for table in bubble_monetization model_cost_reference model_discovery_log \
  moltbook_users opportunities secops_work \
  spending_alerts spending_log yield_positions; do
  pg_dump -t "$table" --if-exists --clean aria_db > "aria_memories/archive/${table}.sql"
done
```

## Restore

```bash
psql aria_db < aria_memories/archive/<table>.sql
```
