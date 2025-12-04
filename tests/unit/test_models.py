"""Tests for data models."""

import pytest
from crawlerWhipAI.models import LinkNode, CrawlResult


def test_link_node_basic():
    """Test basic LinkNode creation."""
    node = LinkNode(
        url="https://example.com",
        title="Example",
        description="Example site",
        depth=0,
    )
    assert node.url == "https://example.com"
    assert node.title == "Example"
    assert node.depth == 0
    assert node.children == []


def test_link_node_hierarchy():
    """Test LinkNode hierarchy."""
    root = LinkNode(url="https://example.com", depth=0)
    child1 = LinkNode(url="https://example.com/page1", depth=1, parent_url=root.url)
    child2 = LinkNode(url="https://example.com/page2", depth=1, parent_url=root.url)

    root.children = [child1, child2]

    assert len(root.children) == 2
    assert root.count_nodes() == 3
    assert len(root.get_all_urls()) == 3


def test_link_node_flatten():
    """Test LinkNode flatten method."""
    root = LinkNode(url="https://example.com", title="Root", depth=0)
    child = LinkNode(url="https://example.com/page", title="Page", depth=1)
    root.children = [child]

    flattened = root.flatten()
    assert len(flattened) == 2
    assert flattened[0]["url"] == root.url
    assert flattened[1]["url"] == child.url


def test_crawl_result_basic():
    """Test basic CrawlResult creation."""
    result = CrawlResult(
        url="https://example.com",
        status_code=200,
        html="<html><body>Hello</body></html>",
    )
    assert result.url == "https://example.com"
    assert result.status_code == 200
    assert result.success is True


def test_crawl_result_error():
    """Test CrawlResult with error."""
    result = CrawlResult(
        url="https://example.com",
        success=False,
        error="Connection timeout",
        error_type="TimeoutError",
    )
    assert result.success is False
    assert result.error == "Connection timeout"
