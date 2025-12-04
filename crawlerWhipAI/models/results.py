"""Result models for crawl operations."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class MarkdownGenerationResult(BaseModel):
    """Result of markdown generation from HTML."""

    raw_markdown: str = Field(..., description="Plain markdown without citations")
    markdown_with_citations: str = Field(
        ..., description="Markdown with numbered link citations"
    )
    references_markdown: str = Field(
        ..., description="Numbered references list"
    )
    fit_markdown: Optional[str] = Field(
        default=None, description="Optimized markdown for LLM processing"
    )
    fit_html: Optional[str] = Field(
        default=None, description="Optimized HTML for LLM processing"
    )


class CrawlResult(BaseModel):
    """Result of a single page crawl operation."""

    url: str = Field(..., description="The URL that was crawled")
    success: bool = Field(default=True, description="Whether crawl succeeded")
    status_code: Optional[int] = Field(
        default=None, description="HTTP status code"
    )
    html: str = Field(default="", description="Raw HTML content")
    cleaned_html: Optional[str] = Field(
        default=None, description="Cleaned HTML (irrelevant tags removed)"
    )
    markdown: Optional[str] = Field(
        default=None, description="Converted markdown content"
    )
    markdown_result: Optional[MarkdownGenerationResult] = Field(
        default=None, description="Detailed markdown generation result"
    )
    title: Optional[str] = Field(default=None, description="Page title")
    description: Optional[str] = Field(
        default=None, description="Meta description"
    )
    meta_tags: Dict[str, str] = Field(
        default_factory=dict, description="Meta tags (og:*, twitter:*, etc.)"
    )
    links: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=lambda: {"internal": [], "external": []},
        description="Discovered links organized by type"
    )
    media: Dict[str, List[Dict[str, str]]] = Field(
        default_factory=lambda: {"images": [], "videos": [], "audio": []},
        description="Discovered media items"
    )
    screenshot: Optional[str] = Field(
        default=None, description="Base64-encoded screenshot"
    )
    pdf: Optional[bytes] = Field(default=None, description="PDF export")
    mhtml: Optional[str] = Field(default=None, description="MHTML snapshot")

    # Execution metadata
    crawled_at: datetime = Field(
        default_factory=datetime.utcnow, description="When page was crawled"
    )
    execution_time: float = Field(
        default=0.0, description="Time to crawl in seconds"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_type: Optional[str] = Field(default=None, description="Type of error")

    # Additional metadata
    content_length: int = Field(default=0, description="Length of content in bytes")
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Response headers"
    )
    user_agent: Optional[str] = Field(
        default=None, description="User-Agent used for crawl"
    )
    depth: int = Field(
        default=0, description="Depth in crawl tree (for deep crawling)"
    )
    parent_url: Optional[str] = Field(
        default=None, description="Parent URL (for deep crawling)"
    )

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            bytes: lambda v: v.hex() if v else None,
        }


class CrawlBatchResult(BaseModel):
    """Result of crawling multiple URLs."""

    results: List[CrawlResult] = Field(..., description="Individual crawl results")
    total_count: int = Field(..., description="Total URLs crawled")
    success_count: int = Field(..., description="Successful crawls")
    failure_count: int = Field(..., description="Failed crawls")
    execution_time: float = Field(..., description="Total execution time in seconds")
    errors: List[Dict[str, str]] = Field(
        default_factory=list, description="Summary of errors"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100


class ExportResult(BaseModel):
    """Result of exporting crawl results."""

    export_format: str = Field(..., description="Format exported to (json, csv, md, etc.)")
    destination: str = Field(..., description="Where data was exported")
    file_count: int = Field(..., description="Number of files created")
    total_size: int = Field(..., description="Total size in bytes")
    exported_at: datetime = Field(
        default_factory=datetime.utcnow, description="When export completed"
    )
    success: bool = Field(default=True, description="Whether export succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Format-specific details"
    )
