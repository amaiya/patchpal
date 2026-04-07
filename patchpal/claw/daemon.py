#!/usr/bin/env python
"""
PatchPal Daemon - Background job scheduler.

Runs scheduled jobs defined in ~/.patchpal/jobs/*.yaml
Jobs are checked every 60 seconds and executed when due.
"""

import argparse
import logging
import signal
import sys
import time

from patchpal.claw.scheduler import get_job_stats, get_pending_jobs, load_jobs, run_job
from patchpal.claw.telegram import is_configured as telegram_configured
from patchpal.claw.telegram import send_job_result

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Daemon:
    """PatchPal background job scheduler."""

    def __init__(self, check_interval: int = 60, agent_factory=None):
        """
        Initialize daemon.

        Args:
            check_interval: Seconds between job checks
            agent_factory: Optional factory function for creating agents
        """
        self.check_interval = check_interval
        self.agent_factory = agent_factory
        self.running = False
        self.jobs = []

    def start(self):
        """Start the daemon."""
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("PatchPal daemon starting...")

        # Load initial jobs
        self._reload_jobs()

        # Show status
        stats = get_job_stats()
        logger.info(f"Loaded {stats['total']} jobs ({stats['enabled']} enabled)")

        if telegram_configured():
            logger.info("Telegram notifications enabled")
        else:
            logger.info("Telegram notifications disabled (not configured)")

        logger.info(f"Checking for pending jobs every {self.check_interval}s")
        logger.info("Press Ctrl-C to stop")

        # Main loop
        while self.running:
            try:
                self._check_and_run_jobs()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(self.check_interval)

    def _reload_jobs(self):
        """Reload job definitions from disk."""
        try:
            self.jobs = load_jobs()
            logger.debug(f"Reloaded {len(self.jobs)} job definitions")
        except Exception as e:
            logger.error(f"Error loading jobs: {e}")

    def _check_and_run_jobs(self):
        """Check for pending jobs and execute them."""
        # Reload jobs to pick up changes
        self._reload_jobs()

        # Get jobs that should run now
        pending = get_pending_jobs(self.jobs)

        if not pending:
            logger.debug("No pending jobs")
            return

        logger.info(f"Found {len(pending)} pending jobs")

        # Execute each pending job
        for job in pending:
            try:
                logger.info(f"Executing job: {job.name}")
                result = run_job(job, self.agent_factory)

                # Send Telegram notification if configured and requested
                if job.notify and telegram_configured():
                    send_job_result(
                        job_name=job.name,
                        result=result.get("result", result.get("error", "")),
                        success=result["success"],
                        elapsed=result.get("elapsed"),
                    )

            except Exception as e:
                logger.error(f"Error executing job {job.name}: {e}", exc_info=True)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, stopping daemon...")
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PatchPal Daemon - Background job scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start daemon (checks every 60 seconds)
  patchpal-daemon

  # Check more frequently (every 30 seconds)
  patchpal-daemon --interval 30

  # Show current status
  patchpal-daemon --status

Job files are defined in: ~/.patchpal/jobs/*.yaml

Example job file (reddit-listening.yaml):
  schedule: "*/15 * * * *"  # Every 15 minutes
  model: "anthropic/claude-sonnet-4"
  notify: true
  prompt: |
    Run the Reddit search script and analyze results:

    run_shell python ~/.patchpal/scripts/reddit_search.py "AI agents"

    Analyze the top 3 posts and identify interesting discussions.

Setup Telegram notifications:
  export TELEGRAM_BOT_TOKEN="your-bot-token"
  export TELEGRAM_CHAT_ID="your-chat-id"

  See: python -c "from patchpal.claw.telegram import get_setup_instructions; print(get_setup_instructions())"
        """,
    )

    parser.add_argument(
        "--interval", type=int, default=60, help="Check interval in seconds (default: 60)"
    )

    parser.add_argument("--status", action="store_true", help="Show job status and exit")

    parser.add_argument("--list-jobs", action="store_true", help="List all jobs and exit")

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Show status
    if args.status:
        stats = get_job_stats()
        print("Job Statistics:")
        print(f"  Total jobs: {stats['total']}")
        print(f"  Enabled: {stats['enabled']}")
        print(f"  Disabled: {stats['disabled']}")
        print(f"  Pending: {stats['pending']}")
        print(f"  Total runs: {stats['total_runs']}")
        print(f"  Jobs directory: {stats['jobs_dir']}")

        if telegram_configured():
            print("  Telegram: Configured ✓")
        else:
            print("  Telegram: Not configured")

        return 0

    # List jobs
    if args.list_jobs:
        jobs = load_jobs()

        if not jobs:
            print("No jobs found in ~/.patchpal/jobs/")
            print("\nCreate a job file like:")
            print("  ~/.patchpal/jobs/my-job.yaml")
            return 0

        print(f"Jobs ({len(jobs)} total):\n")

        for job in jobs:
            status = "✓" if job.enabled else "✗"
            last_run = job.get_last_run()
            run_count = job.get_run_count()

            print(f"  [{status}] {job.name}")
            print(f"      Schedule: {job.schedule}")
            print(f"      Model: {job.model or 'default'}")
            print(f"      Notify: {job.notify}")
            print(f"      Runs: {run_count}")

            if last_run:
                print(f"      Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("      Last run: Never")

            print()

        return 0

    # Start daemon
    daemon = Daemon(check_interval=args.interval)

    try:
        daemon.start()
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
