"""Link mapping hierarchy example."""

import asyncio
from crawlerWhipAI import LinkMapper, CrawlerConfig


async def main():
    """Map links hierarchically."""
    mapper = LinkMapper(
        max_depth=2,
        max_pages=50,
        include_external=False,
    )

    try:
        # Map links starting from a URL
        link_tree = await mapper.map_links(
            start_url="https://example.com",
            crawler_config=CrawlerConfig()
        )

        print(f"Root: {link_tree.title}")
        print(f"URL: {link_tree.url}")
        print(f"Depth: {link_tree.depth}")
        print(f"\nChildren ({len(link_tree.children)}):")

        for i, child in enumerate(link_tree.children, 1):
            print(f"  {i}. {child.title or 'Untitled'}")
            print(f"     URL: {child.url}")
            print(f"     Depth: {child.depth}")

            if child.children:
                for j, grandchild in enumerate(child.children, 1):
                    print(f"     {j}. {grandchild.title or 'Untitled'}")

        # Get all URLs organized by depth
        print(f"\nTotal nodes: {link_tree.count_nodes()}")

        urls_by_depth = mapper._get_urls_by_depth(link_tree)
        for depth, urls in sorted(urls_by_depth.items()):
            print(f"Depth {depth}: {len(urls)} URLs")

    finally:
        await mapper.close()


def _get_urls_by_depth(self, root):
    """Get URLs by depth."""
    result = {}

    def traverse(node):
        if node.depth not in result:
            result[node.depth] = []
        result[node.depth].append(node.url)
        for child in node.children:
            traverse(child)

    traverse(root)
    return result


# Add method to mapper for demo
LinkMapper._get_urls_by_depth = _get_urls_by_depth


if __name__ == "__main__":
    asyncio.run(main())
