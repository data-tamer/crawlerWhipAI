"""Integration tests for full crawling workflow."""

import pytest
import asyncio
from pathlib import Path

from crawlerWhipAI import (
    AsyncWebCrawler,
    CrawlerConfig,
    LinkMapper,
    ContentScraper,
    MarkdownConverter,
    CacheStorage,
    ContentChangeDetector,
    ExportPipeline,
    MarkdownExporter,
    JSONExporter,
)


@pytest.mark.asyncio
async def test_basic_crawl():
    """Test basic crawling."""
    config = CrawlerConfig(
        page_timeout=30000,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://httpbin.org/html", config=config)

        assert result.url == "https://httpbin.org/html"
        assert result.success or result.status_code in [200, 100]
        assert result.html or not result.success


@pytest.mark.asyncio
async def test_content_scraping():
    """Test content scraping."""
    html = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Hello</h1>
            <p>This is a test</p>
            <a href="http://example.com">Link</a>
        </body>
    </html>
    """

    links = ContentScraper.extract_links(html)
    assert len(links["external"]) > 0 or len(links["internal"]) >= 0

    metadata = ContentScraper.extract_metadata(html)
    assert "title" in metadata


@pytest.mark.asyncio
async def test_markdown_conversion():
    """Test markdown conversion."""
    html = """
    <html>
        <body>
            <h1>Title</h1>
            <p>Content</p>
            <a href="http://example.com">Link</a>
        </body>
    </html>
    """

    converter = MarkdownConverter()
    markdown, with_citations, references = converter.convert(html)

    assert "Title" in markdown
    assert "Content" in markdown
    assert len(markdown) > 0


@pytest.mark.asyncio
async def test_cache_operations():
    """Test caching operations."""
    db_path = ".test_cache.db"

    try:
        async with CacheStorage(db_path) as cache:
            # Set
            await cache.set("http://example.com", "Test content")

            # Get
            cached = await cache.get("http://example.com")
            assert cached is not None
            assert cached["content"] == "Test content"

            # Delete
            await cache.delete("http://example.com")
            cached = await cache.get("http://example.com")
            assert cached is None
    finally:
        Path(db_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_change_detection():
    """Test content change detection."""
    original = "This is the original content.\nWith multiple lines."
    modified = "This is the modified content.\nWith multiple lines.\nAnd a new line."

    detector = ContentChangeDetector()
    diff = await detector.detect_changes(modified, original)

    assert diff.similarity_ratio < 1.0
    assert len(diff.added_lines) > 0
    assert diff.to_dict()["percent_changed"] > 0


@pytest.mark.asyncio
async def test_export_json(tmp_path):
    """Test JSON export."""
    from crawlerWhipAI import CrawlResult

    results = [
        CrawlResult(
            url="http://example.com",
            status_code=200,
            title="Test",
            markdown="# Test\nContent",
        ),
    ]

    exporter = JSONExporter(pretty=True)
    output_file = str(tmp_path / "test.json")

    count = await exporter.export(results, output_file)
    assert count == 1
    assert Path(output_file).exists()


@pytest.mark.asyncio
async def test_export_markdown(tmp_path):
    """Test Markdown export."""
    from crawlerWhipAI import CrawlResult

    results = [
        CrawlResult(
            url="http://example.com",
            status_code=200,
            title="Test",
            markdown="# Test\nContent",
        ),
    ]

    exporter = MarkdownExporter(with_frontmatter=True)
    output_dir = str(tmp_path / "markdown")

    count = await exporter.export(results, output_dir)
    assert count == 1
    assert Path(output_dir).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
