"""Export pipeline orchestration."""

import logging
import asyncio
from typing import List
from datetime import datetime

from .formats import Exporter
from ..models import CrawlResult, ExportResult

logger = logging.getLogger(__name__)


class ExportPipeline:
    """Orchestrates multiple export operations."""

    def __init__(self, exporters: List[Exporter]):
        """Initialize pipeline.

        Args:
            exporters: List of exporters to apply.
        """
        self.exporters = exporters

    async def export(
        self,
        results: List[CrawlResult],
        destinations: List[str] = None,
    ) -> ExportResult:
        """Execute export pipeline.

        Args:
            results: Crawl results to export.
            destinations: Export destinations (one per exporter).

        Returns:
            ExportResult with details.
        """
        if not destinations:
            destinations = ["export_" + datetime.now().strftime("%Y%m%d_%H%M%S")] * len(self.exporters)

        if len(destinations) != len(self.exporters):
            raise ValueError(
                f"Number of destinations ({len(destinations)}) must match "
                f"number of exporters ({len(self.exporters)})"
            )

        logger.info(f"Starting export pipeline with {len(self.exporters)} exporters")

        total_exported = 0
        errors = []

        try:
            # Execute exporters in parallel
            tasks = [
                exporter.export(results, dest)
                for exporter, dest in zip(self.exporters, destinations)
            ]

            export_counts = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, (exporter, dest, count) in enumerate(zip(self.exporters, destinations, export_counts)):
                if isinstance(count, Exception):
                    error_msg = f"Exporter {i} ({exporter.__class__.__name__}) failed: {str(count)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    total_exported += count
                    logger.info(f"Exported {count} items via {exporter.__class__.__name__} to {dest}")

            success = len(errors) == 0
            return ExportResult(
                export_format=",".join(e.__class__.__name__ for e in self.exporters),
                destination=",".join(destinations),
                file_count=len(self.exporters),
                total_size=0,  # Could calculate actual size
                success=success,
                error="; ".join(errors) if errors else None,
                details={
                    "exporters": len(self.exporters),
                    "results_exported": total_exported,
                    "errors": len(errors),
                },
            )

        except Exception as e:
            logger.error(f"Export pipeline failed: {str(e)}")
            return ExportResult(
                export_format="",
                destination="",
                file_count=0,
                total_size=0,
                success=False,
                error=str(e),
            )


async def quick_export_markdown(
    results: List[CrawlResult],
    output_dir: str = "./crawl_export",
    with_frontmatter: bool = True,
) -> ExportResult:
    """Quick export to markdown.

    Args:
        results: Crawl results.
        output_dir: Output directory.
        with_frontmatter: Whether to include YAML frontmatter.

    Returns:
        ExportResult.
    """
    from .formats import MarkdownExporter

    exporter = MarkdownExporter(with_frontmatter=with_frontmatter)
    pipeline = ExportPipeline([exporter])
    return await pipeline.export(results, [output_dir])


async def quick_export_json(
    results: List[CrawlResult],
    output_file: str = "./crawl_export.json",
    pretty: bool = True,
) -> ExportResult:
    """Quick export to JSON.

    Args:
        results: Crawl results.
        output_file: Output file path.
        pretty: Whether to pretty-print.

    Returns:
        ExportResult.
    """
    from .formats import JSONExporter

    exporter = JSONExporter(pretty=pretty)
    pipeline = ExportPipeline([exporter])
    return await pipeline.export(results, [output_file])


async def quick_export_csv(
    results: List[CrawlResult],
    output_file: str = "./crawl_export.csv",
    include_markdown: bool = False,
) -> ExportResult:
    """Quick export to CSV.

    Args:
        results: Crawl results.
        output_file: Output file path.
        include_markdown: Whether to include markdown content.

    Returns:
        ExportResult.
    """
    from .formats import CSVExporter

    exporter = CSVExporter(include_markdown=include_markdown)
    pipeline = ExportPipeline([exporter])
    return await pipeline.export(results, [output_file])
