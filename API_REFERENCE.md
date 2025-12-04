# CrawlerWhipAI - API Reference

## Core Classes

### AsyncWebCrawler

Main crawler class for fetching web pages.

```python
from crawlerWhipAI import AsyncWebCrawler, CrawlerConfig

crawler = AsyncWebCrawler(
    browser_config=BrowserConfig(),
    crawler_config=CrawlerConfig()
)

# Single page
result = await crawler.arun(url, config)

# Multiple pages
results = await crawler.arun_many(urls, config, max_concurrent=5)

# Cleanup
await crawler.close()

# Context manager
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url)
```

**Returns**: `CrawlResult`

---

## Configuration

### BrowserConfig

```python
BrowserConfig(
    browser_type="chromium",        # chromium, firefox, webkit
    headless=True,
    disable_images=False,
    disable_css=False,
    user_agent=None,
    user_agent_mode="",             # "random" for random UAs
    enable_stealth=False,
    viewport_width=1920,
    viewport_height=1080,
    timezone_id=None,
    geolocation=None,
    locale=None
)
```

### CrawlerConfig

```python
CrawlerConfig(
    # Navigation
    wait_until=WaitUntil.DOMCONTENTLOADED,
    page_timeout=30000,             # milliseconds

    # Content loading
    wait_for=None,                  # CSS selector or JS condition
    wait_for_timeout=None,
    wait_for_images=False,
    delay_before_return_html=0.1,   # seconds

    # JavaScript
    js_code=None,                   # str or List[str]
    js_only=False,

    # Page interaction
    scan_full_page=False,
    scroll_delay=0.2,
    max_scroll_steps=None,
    process_iframes=False,
    remove_overlay_elements=False,
    adjust_viewport_to_content=False,
    override_navigator=False,
    simulate_user=False,

    # Content
    filter_content=False,
    exclude_external_links=False,
    exclude_social_media_links=False,

    # Media
    screenshot=False,
    pdf=False,
    capture_mhtml=False,

    # HTTP
    proxy=None,
    headers={},
    cookies=None,

    # Caching
    cache_mode="cached",            # CacheMode enum
    cache_ttl_hours=24,

    # Compliance
    check_robots_txt=False,

    # Deep crawling
    max_depth=0,
    max_pages=1
)
```

---

## Content Processing

### ContentScraper

```python
from crawlerWhipAI import ContentScraper

# Extract links
links = ContentScraper.extract_links(html)
# Returns: {"internal": [...], "external": [...]}

# Extract images
images = ContentScraper.extract_images(html)
# Returns: List[{src, alt, title, width, height}]

# Extract tables
tables = ContentScraper.extract_tables(html)
# Returns: List[{headers, rows, caption}]

# Extract text
text = ContentScraper.extract_text(html, preserve_structure=True)

# Extract metadata
metadata = ContentScraper.extract_metadata(html)
# Returns: {title, description, og, twitter, canonical}

# Clean HTML
clean_html = ContentScraper.clean_html(html)
```

### MarkdownConverter

```python
from crawlerWhipAI import MarkdownConverter

converter = MarkdownConverter(
    preserve_links=True,
    generate_citations=True
)

markdown, with_citations, references = converter.convert(html)
```

### Content Filtering

```python
from crawlerWhipAI import (
    PruningFilter,
    BM25Filter,
    LengthFilter,
    FilterChain
)

# Single filter
filter_obj = BM25Filter("search term", threshold=0.5)
filtered = filter_obj.filter(content)

# Multiple filters
chain = FilterChain([
    LengthFilter(min_length=100),
    BM25Filter("keyword"),
    PruningFilter()
])
result = chain.apply(content)
```

---

## Discovery & Crawling

### LinkMapper

```python
from crawlerWhipAI import LinkMapper, CrawlerConfig

mapper = LinkMapper(
    max_depth=2,
    max_pages=100,
    include_external=False
)

# Map links hierarchically
link_tree = await mapper.map_links(
    start_url="https://example.com",
    crawler_config=CrawlerConfig()
)

# Access structure
print(link_tree.title)
print(link_tree.children)
print(link_tree.count_nodes())

# Get URLs
all_urls = link_tree.get_all_urls(max_depth=2)

await mapper.close()
```

### URL Filters

```python
from crawlerWhipAI import (
    PatternFilter,
    DomainFilter,
    ExtensionFilter,
    DepthFilter,
    FilterChain
)

# Pattern matching
pattern_filter = PatternFilter(
    patterns=["*/blog/*", "*/docs/*"],
    regex=False  # glob-style
)

# Domain filtering
domain_filter = DomainFilter(
    allowed_domains=["example.com"],
    blocked_domains=["ads.example.com"]
)

# Extension filtering
ext_filter = ExtensionFilter(
    allowed_extensions=[".html"],
    skip_extensions=[".pdf", ".zip"]
)

# Depth limiting
depth_filter = DepthFilter(max_depth=5)

# Chain filters
chain = FilterChain([pattern_filter, domain_filter, ext_filter])
if chain.matches(url):
    # Process URL
    pass
```

### Robots.txt

```python
from crawlerWhipAI import RobotsParser

parser = RobotsParser(timeout_seconds=2.0)

can_fetch = await parser.can_fetch(
    url="https://example.com/page",
    user_agent="Mozilla/5.0..."
)

parser.clear_cache()
```

---

## Caching

### CacheStorage

```python
from crawlerWhipAI import CacheStorage

async with CacheStorage(".cache.db") as cache:
    # Set
    await cache.set(
        url="https://example.com",
        content="page content",
        metadata={"title": "Example"},
        ttl_hours=24
    )

    # Get
    cached = await cache.get(url)
    # Returns: {url, content, content_hash, metadata, created_at}

    # Delete
    await cache.delete(url)

    # Clear all
    await cache.clear()

    # Cleanup expired
    removed = await cache.cleanup_expired()
```

### ContentChangeDetector

```python
from crawlerWhipAI import ContentChangeDetector

detector = ContentChangeDetector(
    ignore_whitespace=True,
    min_change_percent=1.0
)

diff = await detector.detect_changes(
    current_content="new content",
    previous_content="old content"
)

# Access diff data
print(f"Similarity: {diff.similarity_ratio}")
print(f"Added: {len(diff.added_lines)}")
print(f"Removed: {len(diff.removed_lines)}")

# Get summary
summary = detector.get_diff_summary(diff)

# Get unified diff
unified = detector.get_unified_diff(current, previous, context_lines=3)
```

---

## Export

### Export Formats

```python
from crawlerWhipAI import (
    MarkdownExporter,
    JSONExporter,
    CSVExporter,
    ParquetExporter
)

# Markdown
md_exporter = MarkdownExporter(with_frontmatter=True)
count = await md_exporter.export(results, "./output_dir")

# JSON
json_exporter = JSONExporter(pretty=True)
count = await json_exporter.export(results, "./data.json")

# CSV
csv_exporter = CSVExporter(include_markdown=False)
count = await csv_exporter.export(results, "./data.csv")

# Parquet (requires pyarrow)
parquet_exporter = ParquetExporter()
count = await parquet_exporter.export(results, "./data.parquet")
```

### Export Pipeline

```python
from crawlerWhipAI import ExportPipeline

pipeline = ExportPipeline([
    MarkdownExporter(),
    JSONExporter(),
    CSVExporter()
])

result = await pipeline.export(
    results,
    destinations=["./md", "./data.json", "./data.csv"]
)

print(result.success)
print(result.details)
```

### Quick Export Functions

```python
from crawlerWhipAI import (
    quick_export_markdown,
    quick_export_json,
    quick_export_csv
)

# Quick markdown export
result = await quick_export_markdown(results, "./output")

# Quick JSON export
result = await quick_export_json(results, "./data.json")

# Quick CSV export
result = await quick_export_csv(results, "./data.csv")
```

---

## Data Models

### CrawlResult

```python
from crawlerWhipAI import CrawlResult

result.url              # str
result.success          # bool
result.status_code      # int
result.html             # str
result.cleaned_html     # str
result.markdown         # str
result.markdown_result  # MarkdownGenerationResult
result.title            # str
result.description      # str
result.meta_tags        # Dict[str, str]
result.links            # {"internal": [...], "external": [...]}
result.media            # {"images": [...], "videos": [...]}
result.screenshot       # base64 string
result.pdf              # bytes
result.mhtml            # str
result.crawled_at       # datetime
result.execution_time   # float
result.error            # str
result.depth            # int
result.parent_url       # str
result.headers          # Dict[str, str]
```

### LinkNode

```python
from crawlerWhipAI import LinkNode

node.url                # str
node.title              # str
node.description        # str
node.meta_tags          # Dict[str, str]
node.depth              # int
node.parent_url         # str
node.children           # List[LinkNode]
node.is_internal        # bool
node.score              # float
node.status_code        # int
node.crawled_at         # str
node.error              # str

# Methods
node.count_nodes()
node.get_all_urls(max_depth=None)
node.flatten(include_metadata=True)
node.to_markdown_frontmatter()
```

### ExportResult

```python
from crawlerWhipAI import ExportResult

result.export_format    # str
result.destination      # str
result.file_count       # int
result.total_size       # int
result.success          # bool
result.error            # str
result.details          # Dict[str, Any]
```

---

## Utility Functions

### Async Utilities

```python
from crawlerWhipAI.utils import (
    with_timeout,
    gather_with_limit,
    retry_async
)

# Timeout
result = await with_timeout(
    coro=async_func(),
    timeout_seconds=5.0,
    default=None
)

# Limit concurrency
results = await gather_with_limit(
    coros=[...],
    limit=5,
    return_exceptions=False
)

# Retry with backoff
result = await retry_async(
    coro_func=async_func,
    max_retries=3,
    delay_seconds=1.0,
    backoff_factor=2.0,
    param1="value"
)
```

### URL Utilities

```python
from crawlerWhipAI.utils import (
    normalize_url,
    get_base_domain,
    is_internal_url,
    get_url_path,
    validate_url,
    extract_domain_from_url
)

normalized = normalize_url("//example.com/page?b=2&a=1")
domain = get_base_domain("https://www.example.co.uk/page")
is_internal = is_internal_url("https://example.com/page", "example.com")
path = get_url_path("https://example.com/path/page?query=1")
valid = validate_url("https://example.com")
full_domain = extract_domain_from_url("https://sub.example.com:8080")
```

---

## Enumerations

### WaitUntil
```python
WaitUntil.DOMCONTENTLOADED  # DOM loaded
WaitUntil.LOAD              # Page load event
WaitUntil.NETWORKIDLE       # Network idle
```

### BrowserType
```python
BrowserType.CHROMIUM        # Chromium-based
BrowserType.FIREFOX         # Firefox
BrowserType.WEBKIT          # WebKit/Safari
```

### CacheMode
```python
CacheMode.BYPASS            # Don't use cache
CacheMode.CACHED            # Use and update cache
CacheMode.WRITE_ONLY        # Only write to cache
CacheMode.READ_ONLY         # Only read from cache
```

---

## Complete Example

```python
import asyncio
from crawlerWhipAI import (
    AsyncWebCrawler,
    CrawlerConfig,
    LinkMapper,
    ExportPipeline,
    MarkdownExporter,
    JSONExporter,
)

async def main():
    # 1. Map link hierarchy
    mapper = LinkMapper(max_depth=2, max_pages=50)
    link_tree = await mapper.map_links("https://example.com")
    print(f"Found {link_tree.count_nodes()} pages")

    # 2. Crawl all discovered URLs
    urls = link_tree.get_all_urls()
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, max_concurrent=5)

    # 3. Export to multiple formats
    pipeline = ExportPipeline([
        MarkdownExporter(with_frontmatter=True),
        JSONExporter(pretty=True),
    ])

    export_result = await pipeline.export(
        results,
        destinations=["./markdown", "./data.json"]
    )

    print(f"Export successful: {export_result.success}")

asyncio.run(main())
```

---

## Environment Variables

```bash
# Browser launch options
PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers

# Cache location
CRAWL_CACHE_PATH=./.cache

# Logging level
CRAWL_LOG_LEVEL=INFO
```

---

## Error Handling

```python
try:
    result = await crawler.arun(url)
    if not result.success:
        print(f"Crawl failed: {result.error}")
except Exception as e:
    print(f"Error: {e}")
finally:
    await crawler.close()
```

---

## Performance Notes

- Use `max_concurrent` wisely (3-10 recommended)
- Enable caching to avoid re-crawling
- Use `disable_images=True` for text-only crawling
- Monitor memory with `MemoryAdaptiveDispatcher`
- Use `robots.txt` checking for ethical crawling

---

For more details, see [GETTING_STARTED.md](GETTING_STARTED.md) and [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).
