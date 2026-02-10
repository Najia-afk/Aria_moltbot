# aria_skills/input_guard/__init__.py
"""
🛡️ Input Guard Skill - Runtime security for Aria's inputs.

Provides real-time security analysis for user inputs, API requests,
and skill parameters. Integrates with aria_mind.security module.

Config:
    block_threshold: Minimum threat level to block (default: high)
    enable_logging: Log security events (default: true)
    rate_limit_rpm: Requests per minute per user (default: 60)
    api_base_url: Base URL for Aria API (default: http://aria-api:8000)
"""
import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    from aria_mind.security import (
        AriaSecurityGateway,
        PromptGuard,
        InputSanitizer,
        OutputFilter,
        RateLimitConfig,
        ThreatLevel,
        SafeQueryBuilder,
    )
    HAS_SECURITY = True
except ImportError:
    HAS_SECURITY = False


@SkillRegistry.register
class InputGuardSkill(BaseSkill):
    """
    Runtime input security skill.
    
    Provides Aria with the ability to:
    - Analyze inputs for injection attempts
    - Sanitize user data
    - Validate API parameters
    - Build safe database queries
    - Filter sensitive output
    """
    
    @property
    def name(self) -> str:
        return "input_guard"
    
    async def initialize(self) -> bool:
        """Initialize input guard skill."""
        if not HAS_SECURITY:
            self.logger.error("aria_mind.security module not available")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        # Configure security gateway
        block_threshold_str = self.config.config.get("block_threshold", "high")
        threshold_map = {
            "low": ThreatLevel.LOW,
            "medium": ThreatLevel.MEDIUM,
            "high": ThreatLevel.HIGH,
            "critical": ThreatLevel.CRITICAL,
        }
        block_threshold = threshold_map.get(block_threshold_str, ThreatLevel.HIGH)
        
        rate_limit_rpm = self.config.config.get("rate_limit_rpm", 60)
        
        self._gateway = AriaSecurityGateway(
            rate_limit_config=RateLimitConfig(
                requests_per_minute=rate_limit_rpm,
                requests_per_hour=rate_limit_rpm * 10,
            ),
            enable_audit_log=self.config.config.get("enable_logging", True),
        )
        self._gateway.prompt_guard.block_threshold = block_threshold
        
        self._query_builder = SafeQueryBuilder(
            allowed_tables={
                "goals", "hourly_goals", "thoughts", "memories",
                "activity_log", "social_posts",
                "knowledge_entities", "knowledge_relations",
                "model_usage", "agent_sessions", "security_events",
                "heartbeat_log", "performance_log", "scheduled_jobs",
            }
        )
        
        # API config for logging security events
        self._api_base_url = self.config.config.get(
            "api_base_url",
            os.environ.get("ARIA_API_URL", "http://aria-api:8000/api").split("/api")[0]
        )
        self._enable_logging = self.config.config.get("enable_logging", True)
        
        self._status = SkillStatus.AVAILABLE
        self.logger.info(f"🛡️ Input guard initialized (threshold: {block_threshold_str})")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check skill availability."""
        return self._status
    
    async def _log_security_event(
        self,
        threat_level: str,
        threat_type: str,
        threat_patterns: List[str],
        input_preview: str,
        source: str,
        user_id: Optional[str],
        blocked: bool,
        details: Optional[Dict] = None,
    ) -> None:
        """Log security event to database via API."""
        if not self._enable_logging:
            return
        
        try:
            # Truncate input preview for safety
            preview = input_preview[:500] if input_preview else ""
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self._api_base_url}/api/security-events",
                    json={
                        "threat_level": threat_level,
                        "threat_type": threat_type,
                        "threat_patterns": threat_patterns,
                        "input_preview": preview,
                        "source": source,
                        "user_id": user_id,
                        "blocked": blocked,
                        "details": details or {},
                    }
                )
        except Exception as e:
            self.logger.warning(f"Failed to log security event: {e}")
    
    async def analyze_input(
        self,
        text: str,
        source: str = "user",
        user_id: Optional[str] = None,
    ) -> SkillResult:
        """
        Analyze input text for security threats.
        
        Args:
            text: Input text to analyze
            source: Source of input (user, api, skill, etc.)
            user_id: Optional user identifier for rate limiting
            
        Returns:
            SkillResult with analysis:
            - allowed: bool
            - threat_level: str
            - detections: list of detected patterns
            - sanitized: str (if allowed)
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        try:
            result = self._gateway.check_input(
                text,
                source=source,
                user_id=user_id,
                check_rate_limit=bool(user_id),
            )
            
            self._log_usage("analyze_input", True)
            
            # Log to database if threat detected
            if result.threat_level.value != "NONE" and result.detections:
                # Determine threat type from detections
                threat_type = "prompt_injection"
                if any("sql" in d.lower() for d in result.detections):
                    threat_type = "sql_injection"
                elif any("path" in d.lower() for d in result.detections):
                    threat_type = "path_traversal"
                elif any("command" in d.lower() for d in result.detections):
                    threat_type = "command_injection"
                elif any("xss" in d.lower() for d in result.detections):
                    threat_type = "xss"
                
                # Fire and forget - don't block on logging
                asyncio.create_task(
                    self._log_security_event(
                        threat_level=result.threat_level.value,
                        threat_type=threat_type,
                        threat_patterns=result.detections,
                        input_preview=text,
                        source=source,
                        user_id=user_id,
                        blocked=not result.allowed,
                        details={
                            "rejection_message": result.rejection_message,
                        }
                    )
                )
            
            return SkillResult.ok({
                "allowed": result.allowed,
                "threat_level": result.threat_level.value,
                "rejection_message": result.rejection_message,
                "detections": result.detections,
                "sanitized": result.sanitized_input,
            })
            
        except Exception as e:
            self._log_usage("analyze_input", False)
            return SkillResult.fail(f"Analysis failed: {e}")
    
    async def sanitize_for_html(self, text: str) -> SkillResult:
        """
        Sanitize text for safe HTML display.
        
        Escapes HTML entities to prevent XSS.
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        sanitized = InputSanitizer.sanitize_html(text)
        return SkillResult.ok({"original": text, "sanitized": sanitized})
    
    async def check_sql_safety(self, text: str) -> SkillResult:
        """
        Check if text contains SQL injection patterns.
        
        Returns:
            SkillResult with is_safe and reason
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        is_safe, reason = InputSanitizer.check_sql_injection(text)
        return SkillResult.ok({
            "is_safe": is_safe,
            "reason": reason,
        })
    
    async def check_path_safety(self, path: str) -> SkillResult:
        """
        Check if path contains traversal attempts.
        
        Returns:
            SkillResult with is_safe and reason
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        is_safe, reason = InputSanitizer.check_path_traversal(path)
        return SkillResult.ok({
            "is_safe": is_safe,
            "reason": reason,
        })
    
    async def filter_output(
        self,
        text: str,
        strict: bool = False,
    ) -> SkillResult:
        """
        Filter sensitive data from output text.
        
        Removes or masks:
        - API keys
        - Passwords
        - Connection strings
        - Tokens
        
        Args:
            text: Text to filter
            strict: More aggressive filtering
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        filtered = OutputFilter.filter_output(text, strict=strict)
        contains_sensitive = OutputFilter.contains_sensitive(text)
        
        return SkillResult.ok({
            "original_length": len(text),
            "filtered": filtered,
            "contained_sensitive": contains_sensitive,
        })
    
    async def build_safe_query(
        self,
        operation: str,
        table: str,
        data: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> SkillResult:
        """
        Build a safe parameterized SQL query.
        
        Args:
            operation: select, insert, or update
            table: Table name (must be in allowed list)
            data: Data for insert/update
            columns: Columns for select
            where: WHERE conditions
            order_by: ORDER BY column (prefix with - for DESC)
            limit: LIMIT value
            
        Returns:
            SkillResult with query string and parameters
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        try:
            if operation == "select":
                if not columns:
                    return SkillResult.fail("SELECT requires columns")
                query, params = self._query_builder.select(
                    table, columns, where=where, order_by=order_by, limit=limit
                )
            elif operation == "insert":
                if not data:
                    return SkillResult.fail("INSERT requires data")
                query, params = self._query_builder.insert(table, data)
            elif operation == "update":
                if not data or not where:
                    return SkillResult.fail("UPDATE requires data and where")
                query, params = self._query_builder.update(table, data, where)
            else:
                return SkillResult.fail(f"Unknown operation: {operation}")
            
            self._log_usage("build_safe_query", True)
            
            return SkillResult.ok({
                "query": query,
                "params": params,
                "operation": operation,
                "table": table,
            })
            
        except ValueError as e:
            self._log_usage("build_safe_query", False)
            return SkillResult.fail(f"Query build failed: {e}")
    
    async def get_security_summary(self, hours: int = 24) -> SkillResult:
        """
        Get summary of recent security events.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            SkillResult with event summary
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        summary = self._gateway.get_security_summary(hours)
        return SkillResult.ok(summary)
    
    async def validate_api_params(
        self,
        params: Dict[str, Any],
        schema: Dict[str, str],
    ) -> SkillResult:
        """
        Validate API parameters against a schema.
        
        Args:
            params: Parameters to validate
            schema: Dict of param_name -> type (str, int, bool, list, dict)
            
        Returns:
            SkillResult with validation results
        """
        if not self.is_available:
            return SkillResult.fail("Input guard not available")
        
        errors = []
        sanitized = {}
        
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }
        
        for param_name, expected_type in schema.items():
            if param_name not in params:
                continue
            
            value = params[param_name]
            python_type = type_map.get(expected_type)
            
            if python_type and not isinstance(value, python_type):
                errors.append(f"{param_name}: expected {expected_type}, got {type(value).__name__}")
                continue
            
            # Additional validation for strings
            if isinstance(value, str):
                # Check for injection in string values
                sql_safe, _ = InputSanitizer.check_sql_injection(value)
                if not sql_safe:
                    errors.append(f"{param_name}: contains unsafe SQL patterns")
                    continue
                
                # Sanitize for logging
                sanitized[param_name] = InputSanitizer.sanitize_for_logging(value, 500)
            else:
                sanitized[param_name] = value
        
        return SkillResult.ok({
            "valid": len(errors) == 0,
            "errors": errors,
            "sanitized": sanitized,
        })
