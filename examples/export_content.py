"""Export crawled content example."""

import asyncio
from crawlerWhipAI import (
    AsyncWebCrawler,
    CrawlerConfig,
    ExportPipeline,
    MarkdownExporter,
    JSONExporter,
    CSVExporter,
)


async def main():
    """Crawl URLs and export to multiple formats."""
    urls = [
        "https://example.com",
        "https://example.com/page1",
        "https://example.com/page2",
    ]

    # Crawl all URLs
    print("Crawling URLs...")
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, max_concurrent=3)

    print(f"Crawled {len(results)} pages")

    # Setup exporters
    exporters = [
        MarkdownExporter(with_frontmatter=True),
        JSONExporter(pretty=True),
        CSVExporter(include_markdown=False),
    ]

    # Export to multiple formats
    pipeline = ExportPipeline(exporters)
    export_result = await pipeline.export(
        results,
        destinations=[
            "./export/markdown",
            "./export/data.json",
            "./export/data.csv",
        ]
    )

    print(f"\nExport Results:")
    print(f"  Format: {export_result.export_format}")
    print(f"  Destinations: {export_result.destination}")
    print(f"  Success: {export_result.success}")
    print(f"  Details: {export_result.details}")


if __name__ == "__main__":
    asyncio.run(main())
