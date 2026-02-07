```skill
---
name: aria-experiment
description: "🧪 ML experiment tracking and model management for Data Architect"
metadata: {"openclaw": {"emoji": "🧪"}}
---
```

# aria-experiment

ML experiment tracking and model management. Create experiments, log metrics, compare results, and manage model lifecycle.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment <function> '<json_args>'
```

## Functions

### create_experiment
Create a new ML experiment.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment create_experiment '{"name": "bert-finetune", "description": "Fine-tune BERT"}'
```

### log_metrics
Log metrics to an experiment.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment log_metrics '{"experiment_id": "abc", "metrics": {"loss": 0.5, "accuracy": 0.9}}'
```

### complete_experiment
Mark experiment as completed.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment complete_experiment '{"experiment_id": "abc"}'
```

### compare_experiments
Compare multiple experiments.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment compare_experiments '{"experiment_ids": ["abc", "def"]}'
```

### register_model
Register a model version.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment register_model '{"name": "bert-v1", "experiment_id": "abc", "path": "/models/bert"}'
```

### promote_model
Promote model to a new stage (development, staging, production).

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py experiment promote_model '{"model_name": "bert-v1", "version": "1", "stage": "production"}'
```
