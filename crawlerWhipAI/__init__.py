"""CrawlerWhipAI - Modern async web crawler for content archiving and LLM processing.

Copyright © 2024 DataTamer.ai
Licensed under Apache License 2.0

If you use CrawlerWhipAI in your projects, please mention it and attribute to DataTamer.ai.
Visit https://datatamer.ai for more information.
"""

from .version import __version__

# Core components
from .core import (
    AsyncWebCrawler,
    BrowserConfig,
    BrowserType,
    CacheMode,
    CrawlerConfig,
    WaitUntil,
    VirtualScrollConfig,
)

# Content Processing
from .content import (
    ContentScraper,
    MarkdownConverter,
    PruningFilter,
    BM25Filter,
    LengthFilter,
    FilterChain,
)

# Discovery
from .discovery import (
    LinkMapper,
    LightweightLinkMapper,
    SitemapParser,
    PatternFilter,
    DomainFilter,
    ExtensionFilter,
    DepthFilter,
    RobotsParser,
)

# Cache
from .cache import (
    CacheStorage,
    ContentChangeDetector,
    ContentDiff,
)

# Export
from .export import (
    ExportPipeline,
    MarkdownExporter,
    JSONExporter,
    CSVExporter,
    ParquetExporter,
    quick_export_markdown,
    quick_export_json,
    quick_export_csv,
)

# Models
from .models import (
    LinkNode,
    MarkdownGenerationResult,
    CrawlResult,
    CrawlBatchResult,
    ExportResult,
)

# Utils (browser management)
from .utils import (
    check_browser_installed,
    ensure_browser_installed,
    get_browser_info,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "AsyncWebCrawler",
    "BrowserConfig",
    "BrowserType",
    "CacheMode",
    "CrawlerConfig",
    "WaitUntil",
    "VirtualScrollConfig",
    # Content
    "ContentScraper",
    "MarkdownConverter",
    "PruningFilter",
    "BM25Filter",
    "LengthFilter",
    "FilterChain",
    # Discovery
    "LinkMapper",
    "LightweightLinkMapper",
    "SitemapParser",
    "PatternFilter",
    "DomainFilter",
    "ExtensionFilter",
    "DepthFilter",
    "RobotsParser",
    # Cache
    "CacheStorage",
    "ContentChangeDetector",
    "ContentDiff",
    # Export
    "ExportPipeline",
    "MarkdownExporter",
    "JSONExporter",
    "CSVExporter",
    "ParquetExporter",
    "quick_export_markdown",
    "quick_export_json",
    "quick_export_csv",
    # Models
    "LinkNode",
    "MarkdownGenerationResult",
    "CrawlResult",
    "CrawlBatchResult",
    "ExportResult",
    # Utils
    "check_browser_installed",
    "ensure_browser_installed",
    "get_browser_info",
]
