"""Data models for CrawlerWhipAI."""

from .links import LinkNode
from .results import (
    MarkdownGenerationResult,
    CrawlResult,
    CrawlBatchResult,
    ExportResult,
)

__all__ = [
    "LinkNode",
    "MarkdownGenerationResult",
    "CrawlResult",
    "CrawlBatchResult",
    "ExportResult",
]
