"""
Job scheduling system for background automation.

Provides cron-style scheduling for PatchPal agents.
Jobs are defined in YAML files in ~/.patchpal/jobs/
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from croniter import croniter

logger = logging.getLogger(__name__)


class Job:
    """Represents a scheduled job."""

    def __init__(
        self,
        name: str,
        schedule: str,
        prompt: str,
        model: Optional[str] = None,
        enabled: bool = True,
        notify: bool = False,
        metadata: Optional[Dict] = None,
    ):
        """
        Initialize a job.

        Args:
            name: Job name (from filename)
            schedule: Cron expression (e.g., "*/15 * * * *")
            prompt: Prompt to execute
            model: Model to use (optional, uses default if not specified)
            enabled: Whether job is enabled
            notify: Whether to send notifications (Telegram)
            metadata: Additional metadata from YAML
        """
        self.name = name
        self.schedule = schedule
        self.prompt = prompt
        self.model = model
        self.enabled = enabled
        self.notify = notify
        self.metadata = metadata or {}

        # Validate cron expression
        try:
            croniter(schedule)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{schedule}': {e}")

    def should_run(self, now: Optional[datetime] = None) -> bool:
        """Check if job should run at the given time."""
        if not self.enabled:
            return False

        if now is None:
            now = datetime.now()

        # Get last run time
        last_run = self.get_last_run()

        # Calculate next scheduled run
        if last_run:
            cron = croniter(self.schedule, last_run)
            next_run = cron.get_next(datetime)
        else:
            # First run - check if current time matches schedule
            cron = croniter(self.schedule, now)
            next_run = cron.get_prev(datetime)

        # Should run if current time is past next scheduled time
        return now >= next_run

    def get_last_run(self) -> Optional[datetime]:
        """Get timestamp of last run."""
        state_file = _get_state_file(self.name)
        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text())
            timestamp = data.get("last_run")
            if timestamp:
                return datetime.fromtimestamp(timestamp)
        except (json.JSONDecodeError, OSError):
            pass

        return None

    def mark_run(
        self, success: bool = True, error: Optional[str] = None, result: Optional[str] = None
    ) -> None:
        """Mark job as run."""
        state_file = _get_state_file(self.name)

        data = {
            "last_run": time.time(),
            "success": success,
            "error": error,
            "result_preview": result[:500] if result else None,
            "run_count": self.get_run_count() + 1,
        }

        state_file.write_text(json.dumps(data, indent=2))

    def get_run_count(self) -> int:
        """Get total number of runs."""
        state_file = _get_state_file(self.name)
        if not state_file.exists():
            return 0

        try:
            data = json.loads(state_file.read_text())
            return data.get("run_count", 0)
        except (json.JSONDecodeError, OSError):
            return 0

    def __repr__(self) -> str:
        return f"Job(name='{self.name}', schedule='{self.schedule}', enabled={self.enabled})"


def _get_jobs_dir() -> Path:
    """Get the jobs directory."""
    jobs_dir = Path.home() / ".patchpal" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def _get_state_dir() -> Path:
    """Get the job state directory."""
    state_dir = Path.home() / ".patchpal" / "job_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _get_state_file(job_name: str) -> Path:
    """Get the state file for a job."""
    return _get_state_dir() / f"{job_name}.json"


def load_jobs() -> List[Job]:
    """
    Load all job definitions from ~/.patchpal/jobs/*.yaml

    Returns:
        List of Job objects

    Example:
        >>> from patchpal.scheduler import load_jobs
        >>> jobs = load_jobs()
        >>> for job in jobs:
        ...     print(f"{job.name}: {job.schedule}")
    """
    jobs = []
    jobs_dir = _get_jobs_dir()

    for job_file in jobs_dir.glob("*.yaml"):
        try:
            config = yaml.safe_load(job_file.read_text())

            if not config:
                logger.warning(f"Empty job file: {job_file.name}")
                continue

            # Required fields
            if "schedule" not in config:
                logger.error(f"Job {job_file.name} missing 'schedule' field")
                continue

            if "prompt" not in config:
                logger.error(f"Job {job_file.name} missing 'prompt' field")
                continue

            job = Job(
                name=job_file.stem,
                schedule=config["schedule"],
                prompt=config["prompt"],
                model=config.get("model"),
                enabled=config.get("enabled", True),
                notify=config.get("notify", False),
                metadata=config,
            )

            jobs.append(job)
            logger.info(f"Loaded job: {job.name} ({job.schedule})")

        except Exception as e:
            logger.error(f"Error loading job {job_file.name}: {e}")

    return jobs


def get_pending_jobs(jobs: Optional[List[Job]] = None) -> List[Job]:
    """
    Get jobs that should run now.

    Args:
        jobs: List of jobs to check, or None to load from disk

    Returns:
        List of jobs that should run

    Example:
        >>> from patchpal.scheduler import get_pending_jobs
        >>> pending = get_pending_jobs()
        >>> for job in pending:
        ...     print(f"Running: {job.name}")
    """
    if jobs is None:
        jobs = load_jobs()

    now = datetime.now()
    return [job for job in jobs if job.should_run(now)]


def run_job(job: Job, agent_factory: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Execute a job.

    Args:
        job: Job to execute
        agent_factory: Optional factory function that returns an agent
                      Default: creates agent with job.model if specified

    Returns:
        Dictionary with execution results

    Example:
        >>> from patchpal.scheduler import load_jobs, run_job
        >>> from patchpal import create_agent
        >>>
        >>> jobs = load_jobs()
        >>> job = jobs[0]
        >>> result = run_job(job, lambda: create_agent(model='anthropic/claude-sonnet-4'))
    """
    logger.info(f"Running job: {job.name}")
    start_time = time.time()

    try:
        # Create agent
        if agent_factory:
            agent = agent_factory()
        else:
            from patchpal import create_agent

            kwargs = {}
            if job.model:
                kwargs["model"] = job.model
            agent = create_agent(**kwargs)

        # Run prompt
        result = agent.run(job.prompt)

        # Mark success
        job.mark_run(success=True, result=result)

        elapsed = time.time() - start_time
        logger.info(f"Job {job.name} completed in {elapsed:.1f}s")

        return {"success": True, "result": result, "elapsed": elapsed, "job_name": job.name}

    except Exception as e:
        logger.error(f"Job {job.name} failed: {e}")
        job.mark_run(success=False, error=str(e))

        return {"success": False, "error": str(e), "job_name": job.name}


def get_job_stats() -> Dict[str, Any]:
    """
    Get statistics for all jobs.

    Returns:
        Dictionary with job statistics

    Example:
        >>> from patchpal.scheduler import get_job_stats
        >>> stats = get_job_stats()
        >>> print(f"Total jobs: {stats['total']}")
    """
    jobs = load_jobs()

    total = len(jobs)
    enabled = sum(1 for j in jobs if j.enabled)
    pending = len(get_pending_jobs(jobs))

    total_runs = sum(j.get_run_count() for j in jobs)

    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "pending": pending,
        "total_runs": total_runs,
        "jobs_dir": str(_get_jobs_dir()),
    }
