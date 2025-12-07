"""Fast crawling example with performance optimizations."""

import asyncio
from crawlerWhipAI import LinkMapper, AsyncWebCrawler, BrowserConfig, CrawlerConfig, WaitUntil


async def fast_crawl_example():
    """Demonstrate fast crawling with optimizations.

    This example shows how to configure the crawler for maximum speed
    when crawling documentation sites, blogs, or content-focused websites
    where you primarily need text content.
    """

    # Performance-optimized browser configuration
    browser_config = BrowserConfig(
        # Block unnecessary resources for faster page loads
        disable_images=True,      # Don't load images
        disable_css=True,         # Don't load CSS files
        # disable_javascript=True,  # Uncomment for non-JS sites (fastest)

        # Use headless mode for better performance
        headless=True,
    )

    # Performance-optimized crawler configuration
    crawler_config = CrawlerConfig(
        # Use fastest wait condition - only wait for navigation to commit
        # Options (fastest to slowest):
        # - COMMIT: Navigation committed (fastest, may miss dynamic content)
        # - DOMCONTENTLOADED: DOM ready (fast, good for most sites)
        # - LOAD: All resources loaded (medium)
        # - NETWORKIDLE: No network activity (slowest)
        wait_until=WaitUntil.DOMCONTENTLOADED,

        # Reduce timeouts for faster failure handling
        page_timeout=15000,  # 15 seconds instead of default 30

        # Don't scroll full page unless needed (saves time)
        scan_full_page=False,
    )

    # Create mapper with concurrent crawling
    mapper = LinkMapper(
        max_depth=2,
        max_pages=50,
        include_external=False,
        max_concurrent=10,  # Crawl up to 10 pages concurrently per depth
    )

    # Create crawler with optimized config
    crawler = AsyncWebCrawler(
        browser_config=browser_config,
        crawler_config=crawler_config
    )

    try:
        await crawler.start()

        print("Starting fast crawl with optimizations enabled...")
        print(f"- Images: {'Disabled' if browser_config.disable_images else 'Enabled'}")
        print(f"- CSS: {'Disabled' if browser_config.disable_css else 'Enabled'}")
        print(f"- JavaScript: {'Disabled' if browser_config.disable_javascript else 'Enabled'}")
        print(f"- Wait condition: {crawler_config.wait_until.value}")
        print(f"- Concurrent requests: {mapper.max_concurrent}")
        print()

        # Map links with concurrent crawling
        link_tree = await mapper.map_links(
            start_url="https://docling-project.github.io/docling/reference/document_converter/",
            crawler_config=crawler_config,
        )

        print(f"\n✓ Crawl complete!")
        print(f"  Total pages crawled: {mapper.pages_crawled}")
        print(f"  Total nodes discovered: {link_tree.count_nodes()}")
        print(f"\nRoot page: {link_tree.title}")
        print(f"URL: {link_tree.url}")

        # Show discovered links by depth
        urls_by_depth = mapper.get_urls_by_depth(link_tree)
        print(f"\nDiscovered URLs by depth:")
        for depth, urls in sorted(urls_by_depth.items()):
            print(f"  Depth {depth}: {len(urls)} URLs")

    finally:
        await crawler.close()
        await mapper.close()


async def pwa_optimized_crawl():
    """Optimized crawling for PWA/JavaScript-heavy sites.

    For PWAs and JavaScript-heavy sites, we need JS enabled but can still
    optimize by blocking resources and using concurrent crawling.
    """

    browser_config = BrowserConfig(
        disable_images=True,       # Block images
        disable_css=True,          # Block CSS
        disable_javascript=False,  # Keep JS enabled for PWAs
        headless=True,
    )

    crawler_config = CrawlerConfig(
        # Use DOMCONTENTLOADED for PWAs (good balance)
        wait_until=WaitUntil.DOMCONTENTLOADED,

        # May need longer timeout for JS-heavy sites
        page_timeout=20000,

        # Optional: Wait for specific content to load
        # wait_for="css:.main-content",
        # wait_for_timeout=5000,
    )

    mapper = LinkMapper(
        max_depth=1,
        max_pages=20,
        max_concurrent=5,  # Lower concurrency for JS-heavy sites
    )

    crawler = AsyncWebCrawler(
        browser_config=browser_config,
        crawler_config=crawler_config
    )

    try:
        await crawler.start()

        print("\nPWA-optimized crawl configuration:")
        print(f"- JavaScript: Enabled (required for PWAs)")
        print(f"- Images/CSS: Disabled (speed optimization)")
        print(f"- Concurrent requests: {mapper.max_concurrent}")

        link_tree = await mapper.map_links(
            start_url="https://example.com",  # Replace with PWA URL
            crawler_config=crawler_config,
        )

        print(f"\n✓ PWA crawl complete: {mapper.pages_crawled} pages")

    finally:
        await crawler.close()
        await mapper.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Fast Crawling Performance Example")
    print("=" * 60)

    # Run the fast crawl example
    asyncio.run(fast_crawl_example())

    # Uncomment to run PWA example
    # asyncio.run(pwa_optimized_crawl())
