# aria_skills/goals.py
"""
Goal and task scheduling skill.

Manages Aria's objectives, tasks, and schedules.
"""
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str
    name: str
    cron: Optional[str] = None  # Simplified: "daily", "hourly", "weekly"
    interval_seconds: Optional[int] = None
    handler: Optional[str] = None  # Skill.method to call
    priority: TaskPriority = TaskPriority.MEDIUM
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    """A high-level goal."""
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    subtasks: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0-100
    metadata: Dict[str, Any] = field(default_factory=dict)


@SkillRegistry.register
class GoalSchedulerSkill(BaseSkill):
    """
    Goal and task scheduling.
    
    Config:
        persistence: database | file | memory
        check_interval: Seconds between schedule checks (default: 60)
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._persistence = config.config.get("persistence", "memory")
        self._check_interval = config.config.get("check_interval", 60)
        self._tasks: Dict[str, ScheduledTask] = {}
        self._goals: Dict[str, Goal] = {}
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._db_skill: Optional["DatabaseSkill"] = None
    
    @property
    def name(self) -> str:
        return "goal_scheduler"
    
    def set_database(self, db_skill: "DatabaseSkill") -> None:
        """Inject database skill for persistence."""
        self._db_skill = db_skill
    
    async def initialize(self) -> bool:
        """Initialize scheduler."""
        # Load scheduled tasks from HEARTBEAT.md if available
        await self._load_scheduled_tasks()
        self._status = SkillStatus.AVAILABLE
        return True
    
    async def health_check(self) -> SkillStatus:
        """Scheduler health check."""
        return SkillStatus.AVAILABLE
    
    async def _load_scheduled_tasks(self) -> None:
        """Load tasks from HEARTBEAT.md configuration."""
        # These match the HEARTBEAT.md definitions
        default_tasks = [
            ScheduledTask(
                id="daily_reflection",
                name="Daily Reflection",
                cron="daily",
                handler="aria_mind.reflect",
                priority=TaskPriority.HIGH,
            ),
            ScheduledTask(
                id="morning_checkin",
                name="Morning Check-in",
                cron="daily",
                handler="moltbook.post_status",
                priority=TaskPriority.MEDIUM,
                metadata={"time": "09:00"},
            ),
            ScheduledTask(
                id="health_check",
                name="System Health Check",
                interval_seconds=300,
                handler="health_monitor.check_all_skills",
                priority=TaskPriority.HIGH,
            ),
        ]
        
        for task in default_tasks:
            self._tasks[task.id] = task
            self._calculate_next_run(task)
    
    def _calculate_next_run(self, task: ScheduledTask) -> None:
        """Calculate next run time for a task."""
        now = datetime.utcnow()
        
        if task.interval_seconds:
            if task.last_run:
                task.next_run = task.last_run + timedelta(seconds=task.interval_seconds)
            else:
                task.next_run = now
        elif task.cron == "daily":
            # Next day at specified time or midnight
            time_str = task.metadata.get("time", "00:00")
            hour, minute = map(int, time_str.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            task.next_run = next_run
        elif task.cron == "hourly":
            task.next_run = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        elif task.cron == "weekly":
            days_ahead = 7 - now.weekday()
            task.next_run = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a task handler function."""
        self._handlers[name] = handler
    
    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------
    
    async def add_task(
        self,
        task_id: str,
        name: str,
        handler: str,
        cron: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Add a new scheduled task."""
        if task_id in self._tasks:
            return SkillResult.fail(f"Task {task_id} already exists")
        
        task = ScheduledTask(
            id=task_id,
            name=name,
            cron=cron,
            interval_seconds=interval_seconds,
            handler=handler,
            priority=priority,
            metadata=metadata or {},
        )
        
        self._calculate_next_run(task)
        self._tasks[task_id] = task
        self._log_usage("add_task", True)
        
        return SkillResult.ok({
            "task_id": task_id,
            "next_run": task.next_run.isoformat() if task.next_run else None,
        })
    
    async def remove_task(self, task_id: str) -> SkillResult:
        """Remove a scheduled task."""
        if task_id not in self._tasks:
            return SkillResult.fail(f"Task {task_id} not found")
        
        del self._tasks[task_id]
        return SkillResult.ok({"removed": task_id})
    
    async def list_tasks(self) -> SkillResult:
        """List all scheduled tasks."""
        tasks = [
            {
                "id": t.id,
                "name": t.name,
                "enabled": t.enabled,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "run_count": t.run_count,
                "priority": t.priority.name,
            }
            for t in sorted(self._tasks.values(), key=lambda x: x.priority.value, reverse=True)
        ]
        return SkillResult.ok(tasks)
    
    async def run_task(self, task_id: str) -> SkillResult:
        """Manually run a task."""
        if task_id not in self._tasks:
            return SkillResult.fail(f"Task {task_id} not found")
        
        task = self._tasks[task_id]
        
        if task.handler not in self._handlers:
            return SkillResult.fail(f"Handler {task.handler} not registered")
        
        try:
            handler = self._handlers[task.handler]
            result = await handler() if asyncio.iscoroutinefunction(handler) else handler()
            
            task.last_run = datetime.utcnow()
            task.run_count += 1
            self._calculate_next_run(task)
            
            return SkillResult.ok({
                "task_id": task_id,
                "result": result,
                "next_run": task.next_run.isoformat() if task.next_run else None,
            })
            
        except Exception as e:
            task.failure_count += 1
            return SkillResult.fail(f"Task failed: {e}")
    
    # -------------------------------------------------------------------------
    # Goal Management
    # -------------------------------------------------------------------------
    
    async def add_goal(
        self,
        goal_id: str,
        title: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
    ) -> SkillResult:
        """Add a new goal."""
        if goal_id in self._goals:
            return SkillResult.fail(f"Goal {goal_id} already exists")
        
        goal = Goal(
            id=goal_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
        )
        
        self._goals[goal_id] = goal
        self._log_usage("add_goal", True)
        
        return SkillResult.ok({
            "goal_id": goal_id,
            "title": title,
        })
    
    async def update_goal_progress(
        self,
        goal_id: str,
        progress: float,
        status: Optional[TaskStatus] = None,
    ) -> SkillResult:
        """Update goal progress."""
        if goal_id not in self._goals:
            return SkillResult.fail(f"Goal {goal_id} not found")
        
        goal = self._goals[goal_id]
        goal.progress = min(100.0, max(0.0, progress))
        
        if status:
            goal.status = status
        elif goal.progress >= 100:
            goal.status = TaskStatus.COMPLETED
            goal.completed_at = datetime.utcnow()
        
        return SkillResult.ok({
            "goal_id": goal_id,
            "progress": goal.progress,
            "status": goal.status.value,
        })
    
    async def list_goals(self, status_filter: Optional[TaskStatus] = None) -> SkillResult:
        """List all goals."""
        goals = [
            {
                "id": g.id,
                "title": g.title,
                "progress": g.progress,
                "status": g.status.value,
                "priority": g.priority.name,
                "due_date": g.due_date.isoformat() if g.due_date else None,
            }
            for g in self._goals.values()
            if status_filter is None or g.status == status_filter
        ]
        return SkillResult.ok(goals)
    
    # -------------------------------------------------------------------------
    # Scheduler Loop
    # -------------------------------------------------------------------------
    
    async def start_scheduler(self) -> None:
        """Start the task scheduler loop."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("Scheduler started")
        
        while self._running:
            now = datetime.utcnow()
            
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                
                if task.next_run and task.next_run <= now:
                    self.logger.info(f"Running scheduled task: {task.name}")
                    await self.run_task(task.id)
            
            await asyncio.sleep(self._check_interval)
    
    async def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        self._running = False
        self.logger.info("Scheduler stopped")
