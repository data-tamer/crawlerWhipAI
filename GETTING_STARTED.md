# CrawlerWhipAI - Getting Started Guide

Welcome to CrawlerWhipAI! This guide will help you get started with the crawler in minutes.

## Installation

```bash
# Basic installation
pip install crawlerWhipAI

# With all features
pip install crawlerWhipAI[aws,db,parquet,dev]
```

## Basic Usage

### Simple Single-Page Crawl

```python
import asyncio
from crawlerWhipAI import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://example.com")

        print(f"Title: {result.title}")
        print(f"Status: {result.status_code}")
        print(f"Markdown:\n{result.markdown}")

asyncio.run(main())
```

### Crawl Multiple URLs

```python
async with AsyncWebCrawler() as crawler:
    urls = [
        "https://example.com",
        "https://example.com/page1",
        "https://example.com/page2",
    ]

    results = await crawler.arun_many(
        urls,
        max_concurrent=5
    )

    for result in results:
        print(f"{result.url}: {result.title}")
```

## Advanced Features

### Hierarchical Link Discovery

Map the structure of a website with title and description for each page:

```python
from crawlerWhipAI import LinkMapper, CrawlerConfig

mapper = LinkMapper(
    max_depth=2,      # How deep to crawl
    max_pages=50,     # Total pages limit
    include_external=False  # Only internal links
)

link_tree = await mapper.map_links("https://example.com")

print(f"Root: {link_tree.title}")
for child in link_tree.children:
    print(f"  - {child.title} ({child.url})")
    for grandchild in child.children:
        print(f"    - {grandchild.title}")
```

### Content Filtering and Processing

```python
from crawlerWhipAI import (
    ContentScraper,
    MarkdownConverter,
    BM25Filter,
    FilterChain,
)

# Extract content from HTML
html = "<html>...</html>"
links = ContentScraper.extract_links(html)
images = ContentScraper.extract_images(html)
tables = ContentScraper.extract_tables(html)
metadata = ContentScraper.extract_metadata(html)

# Convert to Markdown
converter = MarkdownConverter()
markdown, markdown_with_citations, references = converter.convert(html)

# Filter content by relevance
filter_chain = FilterChain([
    BM25Filter("your search query", threshold=0.5),
])
filtered_text = filter_chain.apply(markdown)
```

### Smart Caching with Change Detection

```python
from crawlerWhipAI import CacheStorage, ContentChangeDetector

async with CacheStorage(".cache.db") as cache:
    # Cache page content
    await cache.set("https://example.com", markdown_content)

    # Retrieve from cache
    cached = await cache.get("https://example.com")

    # Detect changes
    detector = ContentChangeDetector()
    diff = await detector.detect_changes(new_content, cached["content"])

    print(f"Similarity: {diff.similarity_ratio * 100:.1f}%")
    print(f"Changed: {(1 - diff.similarity_ratio) * 100:.1f}%")
```

### Export to Multiple Formats

```python
from crawlerWhipAI import (
    ExportPipeline,
    MarkdownExporter,
    JSONExporter,
    CSVExporter,
)

exporters = [
    MarkdownExporter(with_frontmatter=True),
    JSONExporter(pretty=True),
    CSVExporter(include_markdown=False),
]

pipeline = ExportPipeline(exporters)
result = await pipeline.export(
    crawl_results,
    destinations=[
        "./markdown_output",
        "./data.json",
        "./data.csv",
    ]
)

print(f"Exported successfully: {result.success}")
```

## Configuration Options

### Browser Configuration

```python
from crawlerWhipAI import BrowserConfig

browser_config = BrowserConfig(
    browser_type="chromium",  # or firefox, webkit
    headless=True,
    disable_images=False,
    user_agent="Custom User Agent",
    viewport_width=1920,
    viewport_height=1080,
)
```

### Crawler Configuration

```python
from crawlerWhipAI import CrawlerConfig, WaitUntil

config = CrawlerConfig(
    # Navigation
    wait_until=WaitUntil.NETWORKIDLE,
    page_timeout=60000,

    # Content loading
    wait_for="css:.content-loaded",  # Wait for specific selector
    scan_full_page=True,  # Scroll to load all content
    scroll_delay=0.2,

    # JavaScript
    js_code="console.log('page loaded')",

    # Caching
    cache_mode="cached",
    cache_ttl_hours=24,

    # Compliance
    check_robots_txt=True,  # Respect robots.txt
)
```

## URL Filtering

Control which URLs to crawl:

```python
from crawlerWhipAI import (
    PatternFilter,
    DomainFilter,
    ExtensionFilter,
    FilterChain,
)

filters = FilterChain([
    # Only .html files
    ExtensionFilter(allowed_extensions=[".html"]),

    # Only specific domains
    DomainFilter(allowed_domains=["example.com"]),

    # Avoid specific URL patterns
    PatternFilter(patterns=["*/admin/*", "*/api/*"], regex=True),
])

# Use with LinkMapper
mapper = LinkMapper()
# Filters can be applied during crawling
```

## Robots.txt Compliance

```python
from crawlerWhipAI import RobotsParser

parser = RobotsParser()

# Check if URL is allowed
can_crawl = await parser.can_fetch(
    url="https://example.com/page",
    user_agent="Mozilla/5.0..."
)

if can_crawl:
    # Proceed with crawl
    pass
```

## Examples

Check the `examples/` directory for complete working examples:

- `basic_crawl.py` - Simple single-page crawl
- `link_hierarchy.py` - Map site structure
- `export_content.py` - Export to multiple formats
- `caching_and_change_detection.py` - Track content changes

## Performance Tips

1. **Use concurrency limits**: `max_concurrent=5` prevents overwhelming servers
2. **Enable caching**: Avoid re-crawling unchanged content
3. **Set appropriate timeouts**: Balance between reliability and speed
4. **Use content filters**: Only process relevant content
5. **Batch operations**: Crawl multiple URLs at once

## Troubleshooting

### Browser launch fails
```bash
# Install browser binaries
playwright install
```

### Slow performance
- Reduce `max_concurrent` if getting timeouts
- Enable `cache_mode="cached"` to reuse results
- Use `disable_images=True` for text-only crawling

### Memory usage
Use `MemoryAdaptiveDispatcher` to automatically throttle based on system memory:
```python
from crawlerWhipAI.dispatch import MemoryAdaptiveDispatcher

dispatcher = MemoryAdaptiveDispatcher(memory_threshold_percent=70.0)
```

## Next Steps

- Read the [API Documentation](https://docs.example.com)
- Explore [advanced examples](./examples/)
- Check [GitHub Discussions](https://github.com/yourusername/crawlerWhipAI/discussions) for help
- Report [issues](https://github.com/yourusername/crawlerWhipAI/issues)

## License

MIT License - see LICENSE file for details.
