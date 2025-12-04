"""Content change detection and diffing."""

import logging
from typing import Dict, List, Optional
from difflib import unified_diff, SequenceMatcher

logger = logging.getLogger(__name__)


class ContentDiff:
    """Represents differences between two content versions."""

    def __init__(self):
        """Initialize ContentDiff."""
        self.added_lines: List[str] = []
        self.removed_lines: List[str] = []
        self.modified_lines: List[tuple] = []
        self.similarity_ratio: float = 1.0

    def to_dict(self) -> Dict:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "added_count": len(self.added_lines),
            "removed_count": len(self.removed_lines),
            "modified_count": len(self.modified_lines),
            "similarity_ratio": self.similarity_ratio,
            "percent_changed": (1 - self.similarity_ratio) * 100,
        }


class ContentChangeDetector:
    """Detects and analyzes content changes."""

    def __init__(self, ignore_whitespace: bool = True, min_change_percent: float = 1.0):
        """Initialize detector.

        Args:
            ignore_whitespace: Whether to ignore whitespace changes.
            min_change_percent: Minimum change percentage to report (0-100).
        """
        self.ignore_whitespace = ignore_whitespace
        self.min_change_percent = min_change_percent

    async def detect_changes(
        self,
        current_content: str,
        previous_content: str,
    ) -> ContentDiff:
        """Detect changes between two versions.

        Args:
            current_content: Current version.
            previous_content: Previous version.

        Returns:
            ContentDiff with change information.
        """
        diff = ContentDiff()

        # Split into lines
        current_lines = current_content.split("\n")
        previous_lines = previous_content.split("\n")

        if self.ignore_whitespace:
            current_lines = [line.strip() for line in current_lines]
            previous_lines = [line.strip() for line in previous_lines]

        # Calculate similarity
        matcher = SequenceMatcher(None, previous_lines, current_lines)
        diff.similarity_ratio = matcher.ratio()

        # Detect added/removed lines
        diff.added_lines = [line for line in current_lines if line not in previous_lines]
        diff.removed_lines = [line for line in previous_lines if line not in current_lines]

        # Check if change exceeds threshold
        percent_changed = (1 - diff.similarity_ratio) * 100
        if percent_changed >= self.min_change_percent:
            logger.info(f"Content changed: {percent_changed:.1f}%")
        else:
            logger.debug(f"Content changed less than {self.min_change_percent}%: {percent_changed:.1f}%")

        return diff

    def get_diff_summary(self, diff: ContentDiff) -> str:
        """Get human-readable summary of changes.

        Args:
            diff: ContentDiff object.

        Returns:
            Summary text.
        """
        summary = []
        summary.append(f"Similarity: {diff.similarity_ratio*100:.1f}%")
        summary.append(f"Added: {len(diff.added_lines)} lines")
        summary.append(f"Removed: {len(diff.removed_lines)} lines")
        summary.append(f"Modified: {len(diff.modified_lines)} lines")

        return "\n".join(summary)

    def get_unified_diff(
        self,
        current_content: str,
        previous_content: str,
        context_lines: int = 3,
    ) -> str:
        """Generate unified diff.

        Args:
            current_content: Current version.
            previous_content: Previous version.
            context_lines: Context lines to show.

        Returns:
            Unified diff string.
        """
        current_lines = current_content.split("\n")
        previous_lines = previous_content.split("\n")

        diff = unified_diff(
            previous_lines,
            current_lines,
            lineterm="",
            n=context_lines,
        )

        return "\n".join(diff)
