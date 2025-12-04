"""Basic crawling example."""

import asyncio
from crawlerWhipAI import AsyncWebCrawler, CrawlerConfig


async def main():
    """Crawl a single URL."""
    config = CrawlerConfig(
        wait_until="domcontentloaded",
        page_timeout=30000,
    )

    async with AsyncWebCrawler() as crawler:
        # Crawl a single page
        result = await crawler.arun(
            "https://example.com",
            config=config
        )

        print(f"URL: {result.url}")
        print(f"Status: {result.status_code}")
        print(f"Title: {result.title}")
        print(f"Markdown length: {len(result.markdown) if result.markdown else 0}")
        print(f"Internal links: {len(result.links.get('internal', []))}")
        print(f"External links: {len(result.links.get('external', []))}")


if __name__ == "__main__":
    asyncio.run(main())
