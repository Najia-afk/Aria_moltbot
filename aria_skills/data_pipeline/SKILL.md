---
name: aria-datapipeline
description: "ðŸ“Š Data pipeline management and ETL operations for Data Architect"
metadata: {"aria": {"emoji": "ðŸ“Š"}}
---

# aria-datapipeline

Data pipeline management and ETL. Define pipelines, validate data, infer schemas, transform data, and run quality checks.

## Usage

```bash
exec python3 /app/skills/run_skill.py data_pipeline <function> '<json_args>'
```

## Functions

### define_pipeline
Define a new data pipeline.

```bash
exec python3 /app/skills/run_skill.py data_pipeline define_pipeline '{"name": "etl_daily", "steps": [{"type": "extract"}]}'
```

### validate_data
Validate data against a schema.

```bash
exec python3 /app/skills/run_skill.py data_pipeline validate_data '{"data": [...], "schema": {...}}'
```

### infer_schema
Infer schema from data samples.

```bash
exec python3 /app/skills/run_skill.py data_pipeline infer_schema '{"data": [...]}'
```

### transform_data
Apply transformations to data.

```bash
exec python3 /app/skills/run_skill.py data_pipeline transform_data '{"data": [...], "transforms": [...]}'
```

### data_quality_check
Run data quality checks.

```bash
exec python3 /app/skills/run_skill.py data_pipeline data_quality_check '{"data": [...]}'
```
