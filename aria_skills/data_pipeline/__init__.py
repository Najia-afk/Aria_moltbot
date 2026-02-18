# aria_skills/data_pipeline.py
"""
📊 Data Pipeline Skill - Data Architect/MLOps Focus

Provides data pipeline management for Aria's Data Architect persona.
Handles data transformations, validations, and ETL workflows.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass
class PipelineStep:
    """A step in a data pipeline."""
    name: str
    operation: str
    config: dict
    order: int


@dataclass
class DataSchema:
    """Schema for data validation."""
    fields: dict[str, str]  # field_name: type
    required: list[str]
    constraints: dict | None = None


@SkillRegistry.register
class DataPipelineSkill(BaseSkill):
    """
    Data pipeline management and ETL operations.
    
    Capabilities:
    - Pipeline definition and execution
    - Data validation and transformation
    - Schema inference and enforcement
    - Data quality checks
    """
    
    @property
    def name(self) -> str:
        return "data_pipeline"
    
    async def initialize(self) -> bool:
        """Initialize data pipeline skill."""
        # TODO: TICKET-12 - stub requires API endpoint for pipeline persistence.
        # Currently in-memory only. Needs POST/GET /api/pipelines endpoints.
        self.logger.warning("data_pipeline skill is in-memory only — API endpoint not yet available")
        self._pipelines: dict[str, list[PipelineStep]] = {}
        self._status = SkillStatus.AVAILABLE
        self.logger.info("📊 Data pipeline skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check pipeline skill availability."""
        return self._status
    
    async def define_pipeline(
        self,
        name: str,
        steps: list[dict]
    ) -> SkillResult:
        """
        Define a new data pipeline.
        
        Args:
            name: Pipeline name
            steps: List of step configurations
            
        Returns:
            SkillResult with pipeline definition
        """
        try:
            pipeline_steps = []
            for i, step in enumerate(steps):
                pipeline_steps.append(PipelineStep(
                    name=step.get("name", f"step_{i}"),
                    operation=step.get("operation", "transform"),
                    config=step.get("config", {}),
                    order=i
                ))
            
            self._pipelines[name] = pipeline_steps
            
            return SkillResult.ok({
                "pipeline": name,
                "steps": len(pipeline_steps),
                "step_names": [s.name for s in pipeline_steps],
                "defined_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Pipeline definition failed: {str(e)}")
    
    async def validate_data(
        self,
        data: list[dict],
        schema: dict
    ) -> SkillResult:
        """
        Validate data against a schema.
        
        Args:
            data: List of records to validate
            schema: Schema definition with fields, required, constraints
            
        Returns:
            SkillResult with validation results
        """
        try:
            data_schema = DataSchema(
                fields=schema.get("fields", {}),
                required=schema.get("required", []),
                constraints=schema.get("constraints")
            )
            
            errors = []
            warnings = []
            
            for i, record in enumerate(data):
                # Check required fields
                for field in data_schema.required:
                    if field not in record or record[field] is None:
                        errors.append(f"Row {i}: Missing required field '{field}'")
                
                # Check field types
                for field, expected_type in data_schema.fields.items():
                    if field in record and record[field] is not None:
                        actual_type = type(record[field]).__name__
                        if not self._check_type(record[field], expected_type):
                            warnings.append(f"Row {i}: Field '{field}' expected {expected_type}, got {actual_type}")
                
                # Check constraints
                if data_schema.constraints:
                    for field, constraint in data_schema.constraints.items():
                        if field in record:
                            violation = self._check_constraint(record[field], constraint)
                            if violation:
                                errors.append(f"Row {i}: {violation}")
            
            return SkillResult.ok({
                "valid": len(errors) == 0,
                "records_checked": len(data),
                "errors": errors,
                "warnings": warnings,
                "validated_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Validation failed: {str(e)}")
    
    async def infer_schema(self, data: list[dict]) -> SkillResult:
        """
        Infer schema from data samples.
        
        Args:
            data: Sample data records
            
        Returns:
            SkillResult with inferred schema
        """
        try:
            if not data:
                return SkillResult.fail("No data provided for schema inference")
            
            fields = {}
            required = []
            field_nulls = {}
            
            # Analyze all records
            for record in data:
                for field, value in record.items():
                    if field not in fields:
                        fields[field] = set()
                        field_nulls[field] = 0
                    
                    if value is None:
                        field_nulls[field] += 1
                    else:
                        fields[field].add(type(value).__name__)
            
            # Determine types and required fields
            inferred_fields = {}
            for field, types in fields.items():
                # Pick the most common type, prefer str for mixed
                if not types:
                    inferred_fields[field] = "any"
                elif len(types) == 1:
                    inferred_fields[field] = list(types)[0]
                elif "str" in types:
                    inferred_fields[field] = "str"
                else:
                    inferred_fields[field] = "any"
                
                # Required if never null
                if field_nulls[field] == 0:
                    required.append(field)
            
            return SkillResult.ok({
                "schema": {
                    "fields": inferred_fields,
                    "required": required
                },
                "records_analyzed": len(data),
                "fields_found": len(inferred_fields),
                "inferred_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Schema inference failed: {str(e)}")
    
    async def transform_data(
        self,
        data: list[dict],
        transformations: list[dict]
    ) -> SkillResult:
        """
        Apply transformations to data.
        
        Args:
            data: Input data records
            transformations: List of transformation operations
            
        Returns:
            SkillResult with transformed data
        """
        try:
            result = data.copy()
            
            for transform in transformations:
                op = transform.get("operation")
                field = transform.get("field")
                config = transform.get("config", {})
                
                if op == "rename":
                    new_name = config.get("new_name")
                    if field and new_name:
                        result = [
                            {new_name if k == field else k: v for k, v in r.items()}
                            for r in result
                        ]
                
                elif op == "drop":
                    if field:
                        result = [{k: v for k, v in r.items() if k != field} for r in result]
                
                elif op == "cast":
                    target_type = config.get("type", "str")
                    if field:
                        result = [
                            {k: self._cast_value(v, target_type) if k == field else v for k, v in r.items()}
                            for r in result
                        ]
                
                elif op == "fill_null":
                    fill_value = config.get("value")
                    if field:
                        result = [
                            {k: fill_value if k == field and v is None else v for k, v in r.items()}
                            for r in result
                        ]
                
                elif op == "filter":
                    condition = config.get("condition")  # e.g., "> 0", "!= null"
                    if field and condition:
                        result = [r for r in result if self._check_filter(r.get(field), condition)]
            
            return SkillResult.ok({
                "data": result,
                "input_count": len(data),
                "output_count": len(result),
                "transformations_applied": len(transformations),
                "transformed_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Transformation failed: {str(e)}")
    
    async def data_quality_check(self, data: list[dict]) -> SkillResult:
        """
        Run data quality checks.
        
        Args:
            data: Data to analyze
            
        Returns:
            SkillResult with quality metrics
        """
        try:
            if not data:
                return SkillResult.fail("No data provided")
            
            total_records = len(data)
            all_fields = set()
            field_stats = {}
            
            # Collect all fields
            for record in data:
                all_fields.update(record.keys())
            
            # Analyze each field
            for field in all_fields:
                values = [r.get(field) for r in data]
                non_null = [v for v in values if v is not None]
                
                field_stats[field] = {
                    "completeness": len(non_null) / total_records,
                    "null_count": total_records - len(non_null),
                    "unique_count": len(set(str(v) for v in non_null)),
                    "sample_values": list(set(str(v) for v in non_null[:5]))
                }
            
            # Overall quality score
            avg_completeness = sum(s["completeness"] for s in field_stats.values()) / len(field_stats) if field_stats else 0
            
            # Detect duplicates
            seen = set()
            duplicates = 0
            for record in data:
                key = json.dumps(record, sort_keys=True, default=str)
                if key in seen:
                    duplicates += 1
                seen.add(key)
            
            return SkillResult.ok({
                "total_records": total_records,
                "total_fields": len(all_fields),
                "field_stats": field_stats,
                "duplicate_records": duplicates,
                "overall_completeness": round(avg_completeness, 3),
                "quality_score": round(avg_completeness * (1 - duplicates / total_records), 3),
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Quality check failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _check_type(self, value: Any, expected: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": (int, float),
            "number": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict,
        }
        expected_type = type_map.get(expected.lower())
        if expected_type:
            return isinstance(value, expected_type)
        return True
    
    def _check_constraint(self, value: Any, constraint: dict) -> str | None:
        """Check value against constraint, return violation message or None."""
        if "min" in constraint and value < constraint["min"]:
            return f"Value {value} below minimum {constraint['min']}"
        if "max" in constraint and value > constraint["max"]:
            return f"Value {value} above maximum {constraint['max']}"
        if "pattern" in constraint:
            import re
            if not re.match(constraint["pattern"], str(value)):
                return f"Value does not match pattern {constraint['pattern']}"
        if "enum" in constraint and value not in constraint["enum"]:
            return f"Value {value} not in allowed values {constraint['enum']}"
        return None
    
    def _cast_value(self, value: Any, target_type: str) -> Any:
        """Cast value to target type."""
        if value is None:
            return None
        try:
            if target_type in ("str", "string"):
                return str(value)
            elif target_type in ("int", "integer"):
                return int(float(value))
            elif target_type in ("float", "number"):
                return float(value)
            elif target_type in ("bool", "boolean"):
                return bool(value)
        except (ValueError, TypeError):
            return value
        return value
    
    def _check_filter(self, value: Any, condition: str) -> bool:
        """Check if value passes filter condition."""
        if condition == "!= null":
            return value is not None
        if condition == "== null":
            return value is None
        
        # Numeric comparisons
        try:
            if condition.startswith("> "):
                return value > float(condition[2:])
            elif condition.startswith("< "):
                return value < float(condition[2:])
            elif condition.startswith(">= "):
                return value >= float(condition[3:])
            elif condition.startswith("<= "):
                return value <= float(condition[3:])
            elif condition.startswith("== "):
                return str(value) == condition[3:]
        except (ValueError, TypeError):
            pass
        
        return True


# Skill instance factory
def create_skill(config: SkillConfig) -> DataPipelineSkill:
    """Create a data pipeline skill instance."""
    return DataPipelineSkill(config)
