"""Export format implementations."""

import logging
import json
import csv
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from ..models import CrawlResult

logger = logging.getLogger(__name__)


class Exporter(ABC):
    """Base class for exporters."""

    @abstractmethod
    async def export(self, results: List[CrawlResult], destination: str) -> int:
        """Export results.

        Args:
            results: Crawl results to export.
            destination: Export destination (path or URL).

        Returns:
            Number of items exported.
        """
        pass


class MarkdownExporter(Exporter):
    """Exports results to Markdown files."""

    def __init__(self, with_frontmatter: bool = True):
        """Initialize exporter.

        Args:
            with_frontmatter: Whether to include YAML frontmatter.
        """
        self.with_frontmatter = with_frontmatter

    async def export(self, results: List[CrawlResult], destination: str) -> int:
        """Export to markdown files.

        Args:
            results: Crawl results.
            destination: Output directory.

        Returns:
            Number of files exported.
        """
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)

        count = 0
        for result in results:
            if not result.markdown:
                continue

            # Generate filename from URL
            filename = self._generate_filename(result.url)
            filepath = dest_path / filename

            # Build content
            content = result.markdown

            # Add frontmatter if requested
            if self.with_frontmatter:
                content = self._add_frontmatter(result) + content

            # Write file
            filepath.write_text(content, encoding="utf-8")
            logger.debug(f"Exported: {filepath}")
            count += 1

        logger.info(f"Exported {count} markdown files to {destination}")
        return count

    def _generate_filename(self, url: str) -> str:
        """Generate filename from URL.

        Args:
            url: URL to convert to filename.

        Returns:
            Safe filename.
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        name = parsed.netloc + parsed.path
        name = name.replace("//", "/").strip("/")
        name = name.replace("/", "_")
        name = "".join(c for c in name if c.isalnum() or c in "._-")[:100]
        return (name or "index") + ".md"

    def _add_frontmatter(self, result: CrawlResult) -> str:
        """Add YAML frontmatter to markdown.

        Args:
            result: Crawl result.

        Returns:
            Frontmatter string.
        """
        frontmatter = "---\n"
        frontmatter += f"title: {result.title or 'Untitled'}\n"
        frontmatter += f"url: {result.url}\n"
        frontmatter += f"status_code: {result.status_code or 'N/A'}\n"
        frontmatter += f"crawled_at: {result.crawled_at.isoformat() if result.crawled_at else 'N/A'}\n"

        if result.description:
            frontmatter += f"description: {result.description}\n"

        frontmatter += "---\n\n"
        return frontmatter


class JSONExporter(Exporter):
    """Exports results to JSON."""

    def __init__(self, pretty: bool = True):
        """Initialize exporter.

        Args:
            pretty: Whether to pretty-print JSON.
        """
        self.pretty = pretty

    async def export(self, results: List[CrawlResult], destination: str) -> int:
        """Export to JSON file.

        Args:
            results: Crawl results.
            destination: Output file path.

        Returns:
            Number of items exported.
        """
        # Prepare destination
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert results to dicts
        data = []
        for result in results:
            item = {
                "url": result.url,
                "status_code": result.status_code,
                "title": result.title,
                "description": result.description,
                "markdown": result.markdown,
                "crawled_at": result.crawled_at.isoformat() if result.crawled_at else None,
                "execution_time": result.execution_time,
                "links": result.links,
                "meta_tags": result.meta_tags,
            }
            data.append(item)

        # Write JSON
        with open(dest_path, "w", encoding="utf-8") as f:
            if self.pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"Exported {len(data)} items to JSON: {destination}")
        return len(data)


class CSVExporter(Exporter):
    """Exports results to CSV."""

    def __init__(self, include_markdown: bool = False):
        """Initialize exporter.

        Args:
            include_markdown: Whether to include markdown content in CSV.
        """
        self.include_markdown = include_markdown

    async def export(self, results: List[CrawlResult], destination: str) -> int:
        """Export to CSV file.

        Args:
            results: Crawl results.
            destination: Output file path.

        Returns:
            Number of items exported.
        """
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "url",
            "status_code",
            "title",
            "description",
            "crawled_at",
            "execution_time",
            "internal_links_count",
            "external_links_count",
        ]

        if self.include_markdown:
            fieldnames.append("markdown")

        with open(dest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = {
                    "url": result.url,
                    "status_code": result.status_code or "",
                    "title": result.title or "",
                    "description": result.description or "",
                    "crawled_at": result.crawled_at.isoformat() if result.crawled_at else "",
                    "execution_time": result.execution_time,
                    "internal_links_count": len(result.links.get("internal", [])),
                    "external_links_count": len(result.links.get("external", [])),
                }

                if self.include_markdown:
                    row["markdown"] = result.markdown or ""

                writer.writerow(row)

        logger.info(f"Exported {len(results)} items to CSV: {destination}")
        return len(results)


class ParquetExporter(Exporter):
    """Exports results to Parquet format."""

    async def export(self, results: List[CrawlResult], destination: str) -> int:
        """Export to Parquet file.

        Args:
            results: Crawl results.
            destination: Output file path.

        Returns:
            Number of items exported.
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            logger.error("PyArrow not installed. Install with: pip install pyarrow")
            return 0

        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data
        data = {
            "url": [],
            "status_code": [],
            "title": [],
            "description": [],
            "markdown": [],
            "crawled_at": [],
            "execution_time": [],
        }

        for result in results:
            data["url"].append(result.url)
            data["status_code"].append(result.status_code or -1)
            data["title"].append(result.title or "")
            data["description"].append(result.description or "")
            data["markdown"].append(result.markdown or "")
            data["crawled_at"].append(result.crawled_at.isoformat() if result.crawled_at else "")
            data["execution_time"].append(result.execution_time)

        # Create table
        table = pa.table(data)

        # Write parquet
        pq.write_table(table, str(dest_path))

        logger.info(f"Exported {len(results)} items to Parquet: {destination}")
        return len(results)
