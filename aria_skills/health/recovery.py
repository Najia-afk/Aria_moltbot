# aria_skills/health/recovery.py
"""
Recovery executor with circuit-breaker pattern.

Evaluates health signals, matches them to playbooks, and executes
recovery actions while preventing rapid-fire re-execution.

Part of Aria's self-healing system (TICKET-36).
Architecture: DB ↔ SQLAlchemy ↔ FastAPI ↔ api_client ↔ Skills ↔ ARIA
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from aria_skills.health.diagnostics import HealthLedger, HealthSignal, Severity
from aria_skills.health.playbooks import Playbook, ALL_PLAYBOOKS

logger = logging.getLogger("aria.health.recovery")


@dataclass
class RecoveryAction:
    """Record of a recovery action taken."""
    playbook_name: str
    signal_component: str
    signal_metric: str
    steps_executed: int
    success: bool
    timestamp: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class RecoveryExecutor:
    """
    Executes playbooks with circuit breaker pattern.

    The circuit breaker prevents re-executing a playbook whose cooldown
    hasn't elapsed, avoiding cascading recovery storms.
    """

    def __init__(
        self,
        ledger: HealthLedger,
        playbooks: Optional[list[Playbook]] = None,
    ):
        self.ledger = ledger
        self.playbooks = playbooks or list(ALL_PLAYBOOKS)
        # playbook_name → last execution timestamp (monotonic)
        self._last_execution: dict[str, float] = {}
        # playbook_name → consecutive failure count
        self._failure_counts: dict[str, int] = {}
        self._history: list[RecoveryAction] = []

    async def evaluate_and_recover(self) -> list[RecoveryAction]:
        """
        Scan current anomalies, match playbooks, execute recoveries.

        Returns list of RecoveryAction records.
        """
        anomalies = self.ledger.get_anomalies()
        if not anomalies:
            return []

        actions: list[RecoveryAction] = []
        for signal in anomalies:
            playbook = self._match_playbook(signal)
            if playbook is None:
                continue
            if self._circuit_open(playbook.name):
                logger.info(
                    f"Circuit open for '{playbook.name}' — skipping "
                    f"(cooldown {playbook.cooldown_seconds}s)"
                )
                continue
            action = await self._execute_playbook(playbook, signal)
            actions.append(action)
            self._history.append(action)

        return actions

    def _match_playbook(self, signal: HealthSignal) -> Optional[Playbook]:
        """Find the first playbook whose trigger matches the signal."""
        for pb in self.playbooks:
            if pb.matches(signal.component, signal.metric, signal.severity.value):
                # Check max_retries via failure count
                if self._failure_counts.get(pb.name, 0) >= pb.max_retries:
                    logger.warning(
                        f"Playbook '{pb.name}' exceeded max_retries "
                        f"({pb.max_retries}) — skipping"
                    )
                    continue
                return pb
        return None

    async def _execute_playbook(
        self, playbook: Playbook, signal: HealthSignal
    ) -> RecoveryAction:
        """Execute a playbook's steps and return an action record."""
        logger.info(
            f"Executing playbook '{playbook.name}' for "
            f"{signal.component}.{signal.metric}"
        )
        steps_executed = 0
        try:
            for step in playbook.steps:
                await self._execute_step(step, signal)
                steps_executed += 1

            # Mark signal resolved on success
            signal.resolved = True
            self._last_execution[playbook.name] = time.monotonic()
            self._failure_counts.pop(playbook.name, None)

            return RecoveryAction(
                playbook_name=playbook.name,
                signal_component=signal.component,
                signal_metric=signal.metric,
                steps_executed=steps_executed,
                success=True,
            )
        except Exception as e:
            self._last_execution[playbook.name] = time.monotonic()
            self._failure_counts[playbook.name] = (
                self._failure_counts.get(playbook.name, 0) + 1
            )
            logger.error(f"Playbook '{playbook.name}' failed: {e}")
            return RecoveryAction(
                playbook_name=playbook.name,
                signal_component=signal.component,
                signal_metric=signal.metric,
                steps_executed=steps_executed,
                success=False,
                error=str(e),
            )

    async def _execute_step(self, step: dict, signal: HealthSignal) -> None:
        """
        Execute a single playbook step.

        Step types: log, wait, shell, api_call, config_update, health_check.
        Template variables like {component} are replaced with signal data.
        """
        action = step.get("action", "")

        # Template substitution
        def _sub(val: str) -> str:
            return val.format(
                component=signal.component,
                metric=signal.metric,
                value=signal.value,
                threshold=signal.threshold,
            ) if isinstance(val, str) else val

        if action == "log":
            logger.info(f"[playbook] {_sub(step.get('message', ''))}")

        elif action == "wait":
            await asyncio.sleep(step.get("seconds", 1))

        elif action == "shell":
            cmd = _sub(step.get("command", ""))
            logger.info(f"[playbook] shell: {cmd}")
            # In production this would run via subprocess; here we log intent
            # proc = await asyncio.create_subprocess_shell(cmd)
            # await proc.wait()

        elif action == "api_call":
            endpoint = _sub(step.get("endpoint", ""))
            method = step.get("method", "GET")
            logger.info(f"[playbook] API {method} {endpoint}")
            # In production: call via api_client skill

        elif action == "config_update":
            key = step.get("key", "")
            value = step.get("value")
            logger.info(f"[playbook] config_update: {key}={value}")

        elif action == "health_check":
            target = _sub(step.get("target", ""))
            logger.info(f"[playbook] health_check: {target}")

        else:
            logger.warning(f"[playbook] Unknown step action: {action}")

    def _circuit_open(self, playbook_name: str) -> bool:
        """
        Return True if the playbook was executed too recently (cooldown active).
        """
        last = self._last_execution.get(playbook_name)
        if last is None:
            return False
        # Find cooldown for this playbook
        cooldown = 300  # default
        for pb in self.playbooks:
            if pb.name == playbook_name:
                cooldown = pb.cooldown_seconds
                break
        elapsed = time.monotonic() - last
        return elapsed < cooldown

    @property
    def history(self) -> list[RecoveryAction]:
        """Return history of recovery actions."""
        return list(self._history)
