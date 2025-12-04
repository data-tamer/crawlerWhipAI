"""Task monitoring and statistics tracking."""

import logging
import time
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class TaskStats:
    """Statistics for a task or group of tasks."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    total_bytes_processed: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    errors: Dict[str, int] = field(default_factory=dict)

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def throughput(self) -> float:
        """Get tasks per second."""
        elapsed = self.elapsed_time
        if elapsed == 0:
            return 0.0
        return self.completed_tasks / elapsed

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["elapsed_time"] = self.elapsed_time
        data["success_rate"] = self.success_rate
        data["throughput"] = self.throughput
        return data

    def __str__(self) -> str:
        """Get human-readable summary."""
        return (
            f"Tasks: {self.completed_tasks}/{self.total_tasks} completed "
            f"({self.success_rate:.1f}%), "
            f"Failed: {self.failed_tasks}, "
            f"Time: {self.elapsed_time:.1f}s, "
            f"Throughput: {self.throughput:.2f} tasks/s"
        )


class CrawlerMonitor:
    """Monitors crawler task execution and statistics."""

    def __init__(self, name: str = "Crawler"):
        """Initialize monitor.

        Args:
            name: Name of the crawl job.
        """
        self.name = name
        self.stats = TaskStats()
        self.per_domain_stats: Dict[str, TaskStats] = {}

    def start(self) -> None:
        """Start monitoring."""
        self.stats.start_time = time.time()
        logger.info(f"Monitor started: {self.name}")

    def end(self) -> None:
        """End monitoring."""
        self.stats.end_time = time.time()
        logger.info(f"Monitor ended: {self.name}")

    def add_task(self, domain: str = "unknown") -> None:
        """Register a new task.

        Args:
            domain: Domain being crawled.
        """
        self.stats.total_tasks += 1

        if domain not in self.per_domain_stats:
            self.per_domain_stats[domain] = TaskStats()
        self.per_domain_stats[domain].total_tasks += 1

    def task_completed(self, domain: str = "unknown", bytes_processed: int = 0) -> None:
        """Record task completion.

        Args:
            domain: Domain that was crawled.
            bytes_processed: Bytes downloaded.
        """
        self.stats.completed_tasks += 1
        self.stats.total_bytes_processed += bytes_processed

        if domain in self.per_domain_stats:
            self.per_domain_stats[domain].completed_tasks += 1
            self.per_domain_stats[domain].total_bytes_processed += bytes_processed

    def task_failed(self, domain: str = "unknown", error_type: str = "unknown") -> None:
        """Record task failure.

        Args:
            domain: Domain that failed.
            error_type: Type of error.
        """
        self.stats.failed_tasks += 1

        # Track error type
        self.stats.errors[error_type] = self.stats.errors.get(error_type, 0) + 1

        if domain in self.per_domain_stats:
            self.per_domain_stats[domain].failed_tasks += 1
            if error_type not in self.per_domain_stats[domain].errors:
                self.per_domain_stats[domain].errors[error_type] = 0
            self.per_domain_stats[domain].errors[error_type] += 1

    def task_skipped(self, domain: str = "unknown") -> None:
        """Record task skipped.

        Args:
            domain: Domain that was skipped.
        """
        self.stats.skipped_tasks += 1

        if domain in self.per_domain_stats:
            self.per_domain_stats[domain].skipped_tasks += 1

    def get_summary(self) -> str:
        """Get summary of monitoring data.

        Returns:
            Human-readable summary.
        """
        summary = [
            f"\n{'='*60}",
            f"Crawl Summary: {self.name}",
            f"{'='*60}",
            str(self.stats),
            f"\nBytes Processed: {self.format_bytes(self.stats.total_bytes_processed)}",
            f"Errors: {sum(self.stats.errors.values())}",
        ]

        if self.stats.errors:
            summary.append("\nError Breakdown:")
            for error_type, count in sorted(
                self.stats.errors.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                summary.append(f"  {error_type}: {count}")

        if self.per_domain_stats:
            summary.append("\nPer-Domain Stats:")
            for domain in sorted(self.per_domain_stats.keys()):
                stats = self.per_domain_stats[domain]
                summary.append(
                    f"  {domain}: {stats.completed_tasks}/{stats.total_tasks} "
                    f"({stats.success_rate:.1f}%)"
                )

        summary.append(f"{'='*60}\n")
        return "\n".join(summary)

    def get_stats_dict(self) -> Dict:
        """Get all statistics as dictionary.

        Returns:
            Dictionary with complete stats.
        """
        return {
            "overall": self.stats.to_dict(),
            "per_domain": {
                domain: stats.to_dict()
                for domain, stats in self.per_domain_stats.items()
            }
        }

    @staticmethod
    def format_bytes(bytes_count: int) -> str:
        """Format bytes to human-readable size.

        Args:
            bytes_count: Number of bytes.

        Returns:
            Formatted string.
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_count < 1024:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024
        return f"{bytes_count:.2f} TB"

    def log_summary(self, level: int = logging.INFO) -> None:
        """Log summary to logger.

        Args:
            level: Logging level.
        """
        logger.log(level, self.get_summary())
