# CrawlerWhipAI

A modern, asynchronous web crawler inspired by Crawl4AI with enhanced features for content archiving, SPA crawling, and intelligent caching.

## Features

### Core Crawling
- **Async-first design**: Built on Playwright and asyncio for high concurrency
- **Multiple browser support**: Chromium, Firefox, WebKit via Playwright
- **JavaScript rendering**: Full support for SPAs, lazy loading, virtual scrolling
- **Responsive DOM waits**: CSS selectors, JavaScript conditions, image loading

### Content Processing
- **HTML to Markdown**: Convert web pages to clean, readable markdown
- **Link extraction**: Automatic detection of internal and external links
- **Metadata extraction**: Title, meta descriptions, Open Graph tags
- **Media discovery**: Images, videos, audio extraction

### Link Discovery & Mapping
- **Hierarchical link mapping**: Build tree structures of discovered links
- **Depth-based crawling**: Control how deep to crawl with max_depth
- **Link metadata**: Title and description for each discovered page
- **Domain filtering**: Internal vs external link categorization

### Advanced Features
- **Smart caching**: Content hash-based invalidation with TTL
- **Change detection**: Track what changed since last crawl
- **Export pipelines**: Multiple format support (Markdown, JSON, CSV, Parquet)
- **Rate limiting**: Robots.txt compliance with domain-aware rate limiting
- **Robots.txt support**: Respectful crawling with SQLite caching

## Installation

```bash
pip install crawlerWhipAI
```

With optional dependencies:

```bash
# AWS S3 support
pip install crawlerWhipAI[aws]

# Database exports
pip install crawlerWhipAI[db]

# Parquet support
pip install crawlerWhipAI[parquet]

# Development
pip install crawlerWhipAI[dev]
```

## Quick Start

### Basic Crawling

```python
import asyncio
from crawlerWhipAI import AsyncWebCrawler, CrawlerConfig

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://example.com")
        print(result.markdown)

asyncio.run(main())
```

### Hierarchical Link Discovery

```python
from crawlerWhipAI.discovery import LinkMapper

async def main():
    mapper = LinkMapper(max_depth=2, max_pages=50)
    link_tree = await mapper.map_links("https://example.com")

    # Access hierarchical structure
    print(f"Root: {link_tree.title}")
    for child in link_tree.children:
        print(f"  - {child.title} ({child.url})")

asyncio.run(main())
```

### Configuration Options

```python
from crawlerWhipAI import CrawlerConfig, BrowserConfig, WaitUntil

config = CrawlerConfig(
    # Navigation
    wait_until=WaitUntil.NETWORKIDLE,
    page_timeout=60000,

    # Content loading
    wait_for="css:.content-loaded",
    scan_full_page=True,

    # Deep crawling
    max_depth=2,
    max_pages=100,

    # Compliance
    check_robots_txt=True,
)
```

## Architecture

```
crawlerWhipAI/
├── core/              # Main crawler components
├── browser/           # Browser management (Playwright)
├── content/           # Content processing pipeline
├── discovery/         # Link mapping and deep crawling
├── cache/             # Intelligent caching
├── export/            # Export pipelines
├── dispatch/          # Task dispatching
├── models/            # Data models
├── utils/             # Utility functions
└── ...
```

## Development

### Setup

```bash
git clone https://github.com/data-tamer/crawlerWhipAI.git
cd crawlerWhipAI
pip install -e ".[dev]"
```

### Testing

```bash
pytest tests/ -v --cov=crawlerWhipAI
```

### Code Quality

```bash
black crawlerWhipAI
ruff check crawlerWhipAI
mypy crawlerWhipAI
```

## Roadmap

### Phase 1: Foundation ✅
- [x] Project structure
- [x] Core AsyncWebCrawler
- [x] Browser management
- [x] Configuration models
- [x] Link discovery (LinkMapper)

### Phase 2: Content Processing
- [ ] Advanced markdown generation
- [ ] Content filtering strategies
- [ ] Table extraction
- [ ] JavaScript handling enhancements

### Phase 3: Caching & Storage
- [ ] Smart cache invalidation
- [ ] Content change detection
- [ ] Version tracking

### Phase 4: Export & Integration
- [ ] Export pipelines
- [ ] S3/Database writers
- [ ] Batch processing

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -am 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details

Copyright © 2024 DataTamer.ai. All rights reserved.

## Citation & Attribution

If you use CrawlerWhipAI in your projects, please mention it! We appreciate attribution:

### In a README
```markdown
This project uses [CrawlerWhipAI](https://datatamer.ai)
for web crawling and content processing.

Licensed under Apache License 2.0 - Copyright © 2024 DataTamer.ai
```

### In Code Comments
```python
# Using CrawlerWhipAI by DataTamer.ai for web crawling
# https://datatamer.ai
# Licensed under Apache License 2.0
from crawlerWhipAI import AsyncWebCrawler
```

### In Documentation
```
Built with CrawlerWhipAI - A modern async web crawler
by DataTamer.ai (https://datatamer.ai)
Apache License 2.0
```

### Share Your Use Case
We'd love to hear how you're using CrawlerWhipAI! Consider:
- Visiting [DataTamer.ai](https://datatamer.ai)
- Contributing improvements or bug fixes
- Sharing feedback and suggestions
- Letting us know about your use case

## Acknowledgments

- Inspired by [Crawl4AI](https://github.com/unclecode/crawl4ai)
- Built with [Playwright](https://playwright.dev/)
- Powered by [Pydantic](https://pydantic-ai.jina.ai/)
- Maintained by [DataTamer.ai](https://datatamer.ai)

## Support

- 🌐 [DataTamer.ai Website](https://datatamer.ai)
- 📚 [Documentation](https://datatamer.ai/docs/crawlerwhipai)
- 💬 [Discussions](https://github.com/data-tamer/crawlerWhipAI/discussions)
- 🐛 [Issues](https://github.com/data-tamer/crawlerWhipAI/issues)

## Privacy & Attribution

CrawlerWhipAI is developed and maintained by **DataTamer.ai**. When using this library, please respect robots.txt and website terms of service. Consider providing proper attribution when using CrawlerWhipAI in your projects.
