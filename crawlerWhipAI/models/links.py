"""Link and node models for hierarchical link discovery."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class LinkNode(BaseModel):
    """Represents a link node in the hierarchical crawl structure.

    Used by LinkMapper to build a tree of discovered links with metadata.
    """

    url: str = Field(..., description="The URL of the link")
    title: str = Field(default="", description="Page title from <title> tag")
    description: str = Field(default="", description="Meta description content")
    meta_tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional meta tags (og:image, twitter:card, etc.)"
    )
    depth: int = Field(default=0, description="Depth level in the crawl tree")
    parent_url: Optional[str] = Field(default=None, description="Parent URL if nested")
    children: List["LinkNode"] = Field(
        default_factory=list,
        description="Child links discovered from this page"
    )
    is_internal: bool = Field(default=True, description="Whether link is internal to domain")
    score: Optional[float] = Field(
        default=None,
        description="Optional relevance/ranking score"
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP status code from crawling"
    )
    crawled_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when this page was crawled"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if crawling failed"
    )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def to_markdown_frontmatter(self) -> str:
        """Convert to markdown with YAML frontmatter.

        Returns:
            Markdown string with YAML frontmatter containing metadata.
        """
        frontmatter = f"""---
title: {self.title or 'Untitled'}
url: {self.url}
depth: {self.depth}
parent_url: {self.parent_url or 'N/A'}
is_internal: {self.is_internal}
status_code: {self.status_code or 'N/A'}
crawled_at: {self.crawled_at or 'N/A'}
"""
        if self.meta_tags:
            frontmatter += "meta_tags:\n"
            for key, value in self.meta_tags.items():
                frontmatter += f"  {key}: {value}\n"

        frontmatter += "---\n"
        return frontmatter

    def flatten(self, include_metadata: bool = True) -> List[Dict]:
        """Flatten the tree into a list of link dictionaries.

        Args:
            include_metadata: Whether to include metadata fields.

        Returns:
            List of flattened link dictionaries.
        """
        result = []

        def _flatten_recursive(node: "LinkNode", path: str = ""):
            item = {
                "url": node.url,
                "title": node.title,
                "description": node.description,
                "depth": node.depth,
                "is_internal": node.is_internal,
                "path": path,
            }

            if include_metadata:
                item.update({
                    "meta_tags": node.meta_tags,
                    "score": node.score,
                    "status_code": node.status_code,
                    "crawled_at": node.crawled_at,
                    "error": node.error,
                })

            result.append(item)

            for child in node.children:
                child_path = f"{path}/{child.url.split('/')[-1]}" if path else child.url
                _flatten_recursive(child, child_path)

        _flatten_recursive(self)
        return result

    def get_all_urls(self, max_depth: Optional[int] = None) -> List[str]:
        """Get all URLs in the tree up to optional max depth.

        Args:
            max_depth: Maximum depth to traverse, None for unlimited.

        Returns:
            List of all URLs in the tree.
        """
        urls = []

        def _traverse(node: "LinkNode"):
            if max_depth is not None and node.depth > max_depth:
                return
            urls.append(node.url)
            for child in node.children:
                _traverse(child)

        _traverse(self)
        return urls

    def count_nodes(self, max_depth: Optional[int] = None) -> int:
        """Count total nodes in tree.

        Args:
            max_depth: Maximum depth to count, None for unlimited.

        Returns:
            Total node count.
        """
        count = 1
        for child in self.children:
            if max_depth is None or child.depth <= max_depth:
                count += child.count_nodes(max_depth)
        return count


LinkNode.model_rebuild()
