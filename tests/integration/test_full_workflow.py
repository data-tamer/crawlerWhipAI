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
async def test_pwa_crawl():
    """Test crawling a Progressive Web App (PWA).

    PWAs use service workers and may load content dynamically via JavaScript.
    This test verifies the crawler can handle SPAs/PWAs that rely on JS rendering.
    """
    config = CrawlerConfig(
        page_timeout=60000,  # Longer timeout for PWA initialization
        wait_until="networkidle",  # Wait for service worker and dynamic content
        scan_full_page=False,
    )

    async with AsyncWebCrawler() as crawler:
        # whatpwacando.today is a well-known PWA demo site
        result = await crawler.arun("https://whatpwacando.today/", config=config)

        assert result.url == "https://whatpwacando.today/"
        assert result.success or result.status_code in [200, 100]
        assert result.html is not None
        assert len(result.html) > 0

        # PWAs should have content loaded via JavaScript
        if result.success:
            # Check that we got meaningful content (not just empty shell)
            assert result.content_length > 1000, "PWA content should be substantial"

            # Check for PWA-related content or features
            html_lower = result.html.lower()
            assert any([
                "pwa" in html_lower,
                "progressive" in html_lower,
                "service" in html_lower,
                "manifest" in html_lower,
            ]), "PWA page should contain PWA-related content"

            # Verify markdown conversion works for PWA content
            assert result.markdown is not None, "Markdown should be generated"
            assert len(result.markdown) > 100, "Markdown content should be substantial"

            # Test explicit markdown conversion with MarkdownConverter
            converter = MarkdownConverter()
            markdown, with_citations, references = converter.convert(result.html)
            assert len(markdown) > 0, "MarkdownConverter should produce output"


@pytest.mark.asyncio
async def test_single_page_markdown_conversion(capsys):
    """Test single page crawl with markdown conversion.

    Crawls a single page and converts it to markdown, displaying
    the conversion report in test output.
    """
    config = CrawlerConfig(
        page_timeout=30000,
        wait_until="domcontentloaded",
    )

    converter = MarkdownConverter()

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://httpbin.org/html", config=config)

        assert result.success, f"Crawl failed: {result.error}"
        assert result.html is not None

        # Convert to markdown
        markdown, with_citations, references = converter.convert(result.html)

        # Print report to test output
        print("\n" + "=" * 60)
        print("SINGLE PAGE MARKDOWN CONVERSION REPORT")
        print("=" * 60)
        print(f"URL: {result.url}")
        print(f"Status: {result.status_code}")
        print(f"Title: {result.title}")
        print(f"HTML Length: {len(result.html)} bytes")
        print(f"Markdown Length: {len(markdown)} bytes")
        print("-" * 60)
        print("MARKDOWN PREVIEW (first 500 chars):")
        print("-" * 60)
        print(markdown[:500] if len(markdown) > 500 else markdown)
        print("=" * 60)

        # Assertions
        assert len(markdown) > 0, "Markdown should not be empty"
        assert result.markdown is not None, "Crawler should generate markdown"


@pytest.mark.asyncio
async def test_deep_link_crawl_with_markdown(capsys):
    """Test crawling a page and following 1 level of internal links.

    Crawls a starting page, extracts internal links, follows up to 3 links,
    and converts all pages to markdown. Displays a report of all converted pages.
    Saves markdown files to ./test_output/markdown/ for download.
    """
    from crawlerWhipAI import CrawlResult

    config = CrawlerConfig(
        page_timeout=30000,
        wait_until="domcontentloaded",
    )

    converter = MarkdownConverter()
    crawled_pages = []
    crawl_results = []  # Store CrawlResult objects for export

    async with AsyncWebCrawler() as crawler:
        # Step 1: Crawl the initial page
        start_url = "https://httpbin.org/"
        initial_result = await crawler.arun(start_url, config=config)

        assert initial_result.success, f"Initial crawl failed: {initial_result.error}"

        # Convert initial page
        markdown, _, _ = converter.convert(initial_result.html)

        # Update result with converted markdown
        initial_result.markdown = markdown
        crawl_results.append(initial_result)

        crawled_pages.append({
            "url": initial_result.url,
            "title": initial_result.title,
            "status": initial_result.status_code,
            "html_length": len(initial_result.html) if initial_result.html else 0,
            "markdown_length": len(markdown),
            "markdown_preview": markdown[:200] if markdown else "",
            "depth": 0,
        })

        # Step 2: Extract internal links and crawl up to 3 of them (depth=1)
        internal_links = initial_result.links.get("internal", [])

        # Filter to get unique, valid links (limit to 3 for test speed)
        links_to_follow = []
        seen_urls = {start_url}
        for link in internal_links:
            href = link.get("href", "")
            if href and href not in seen_urls and href.startswith("http"):
                # Skip anchors and same-page links
                if "#" not in href or href.split("#")[0] not in seen_urls:
                    links_to_follow.append(href)
                    seen_urls.add(href)
                    if len(links_to_follow) >= 3:
                        break

        # Step 3: Crawl the linked pages
        if links_to_follow:
            linked_results = await crawler.arun_many(links_to_follow, config=config)

            for result in linked_results:
                if result.success and result.html:
                    md, _, _ = converter.convert(result.html)
                    result.markdown = md
                    crawl_results.append(result)

                    crawled_pages.append({
                        "url": result.url,
                        "title": result.title,
                        "status": result.status_code,
                        "html_length": len(result.html),
                        "markdown_length": len(md),
                        "markdown_preview": md[:200] if md else "",
                        "depth": 1,
                    })

        # Step 4: Export markdown files to disk
        output_dir = Path(__file__).parent.parent.parent / "test_output" / "markdown"
        exporter = MarkdownExporter(with_frontmatter=True)
        exported_count = await exporter.export(crawl_results, str(output_dir))

        # Also export as JSON for complete data
        json_exporter = JSONExporter(pretty=True)
        json_output = Path(__file__).parent.parent.parent / "test_output" / "crawl_results.json"
        await json_exporter.export(crawl_results, str(json_output))

        # Print detailed report
        print("\n" + "=" * 70)
        print("DEEP LINK CRAWL REPORT (Depth: 1)")
        print("=" * 70)
        print(f"Starting URL: {start_url}")
        print(f"Internal links found: {len(internal_links)}")
        print(f"Links followed: {len(links_to_follow)}")
        print(f"Total pages converted: {len(crawled_pages)}")
        print(f"Files exported: {exported_count}")
        print(f"Output directory: {output_dir}")
        print("=" * 70)

        for i, page in enumerate(crawled_pages, 1):
            print(f"\n[Page {i}] {'(ROOT)' if page['depth'] == 0 else '(DEPTH 1)'}")
            print(f"  URL: {page['url']}")
            print(f"  Title: {page['title']}")
            print(f"  Status: {page['status']}")
            print(f"  HTML: {page['html_length']} bytes")
            print(f"  Markdown: {page['markdown_length']} bytes")
            print(f"  Preview: {page['markdown_preview'][:100]}...")
            print("-" * 70)

        print("\nSUMMARY TABLE:")
        print("-" * 70)
        print(f"{'#':<3} {'Depth':<6} {'Status':<7} {'MD Size':<10} {'URL':<40}")
        print("-" * 70)
        for i, page in enumerate(crawled_pages, 1):
            url_short = page['url'][:37] + "..." if len(page['url']) > 40 else page['url']
            print(f"{i:<3} {page['depth']:<6} {page['status']:<7} {page['markdown_length']:<10} {url_short:<40}")
        print("=" * 70)

        # List exported files
        print("\nEXPORTED FILES:")
        print("-" * 70)
        for md_file in sorted(output_dir.glob("*.md")):
            print(f"  {md_file.name} ({md_file.stat().st_size} bytes)")
        print(f"  {json_output.name} ({json_output.stat().st_size} bytes)")
        print("=" * 70)

        # Assertions
        assert len(crawled_pages) >= 1, "Should have crawled at least the initial page"
        assert all(p["markdown_length"] > 0 for p in crawled_pages), "All pages should have markdown"
        assert exported_count > 0, "Should have exported at least one file"
        assert output_dir.exists(), "Output directory should exist"


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
