"""Caching and content change detection example."""

import asyncio
from crawlerWhipAI import AsyncWebCrawler, CrawlerConfig, CacheStorage, ContentChangeDetector


async def main():
    """Demonstrate caching and change detection."""
    url = "https://example.com"

    # Initialize cache
    async with CacheStorage(".example_cache.db") as cache:
        # First crawl
        print("First crawl...")
        async with AsyncWebCrawler() as crawler:
            result1 = await crawler.arun(url)

        # Cache the result
        await cache.set(
            url,
            result1.markdown or "",
            metadata={
                "title": result1.title,
                "status_code": result1.status_code,
            },
            ttl_hours=24
        )
        print(f"Cached: {url}")

        # Retrieve from cache
        cached = await cache.get(url)
        if cached:
            print(f"Retrieved from cache (hash: {cached['content_hash'][:8]}...)")

        # Second crawl (simulated)
        print("\nSecond crawl (simulated)...")
        result2_markdown = result1.markdown + "\n\nNew content added!"

        # Detect changes
        detector = ContentChangeDetector(ignore_whitespace=False)
        diff = await detector.detect_changes(
            result2_markdown,
            result1.markdown or ""
        )

        print(f"Similarity: {diff.similarity_ratio*100:.1f}%")
        print(f"Added lines: {len(diff.added_lines)}")
        print(f"Removed lines: {len(diff.removed_lines)}")
        print(f"Percent changed: {(1 - diff.similarity_ratio)*100:.1f}%")

        # Update cache
        await cache.set(
            url,
            result2_markdown,
            metadata={
                "title": "Updated Title",
                "changed": True,
            },
            ttl_hours=24
        )

        # Cleanup expired
        await cache.cleanup_expired()


if __name__ == "__main__":
    asyncio.run(main())
