"""Content scraping and HTML processing."""

import logging
from typing import Dict, List, Any
from lxml import html as lxml_html
from html import unescape

logger = logging.getLogger(__name__)


class ContentScraper:
    """Scrapes content from HTML."""

    # Tags to remove for cleaning
    REMOVE_TAGS = {"script", "style", "meta", "noscript", "iframe", "object"}

    # Tags to extract text from
    TEXT_TAGS = {"p", "div", "span", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}

    @staticmethod
    def clean_html(html: str) -> str:
        """Remove unwanted tags from HTML.

        Args:
            html: HTML content.

        Returns:
            Cleaned HTML.
        """
        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML: {str(e)}")
            return html

        # Remove unwanted tags
        for tag in ContentScraper.REMOVE_TAGS:
            for element in tree.xpath(f".//{tag}"):
                element.getparent().remove(element)

        return lxml_html.tostring(tree, encoding="unicode", method="html")

    @staticmethod
    def extract_links(html: str) -> Dict[str, List[Dict[str, str]]]:
        """Extract links from HTML.

        Args:
            html: HTML content.

        Returns:
            Dictionary with 'internal' and 'external' link lists.
        """
        links = {"internal": [], "external": []}

        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML for links: {str(e)}")
            return links

        for link in tree.xpath(".//a[@href]"):
            try:
                href = link.get("href", "").strip()
                text = link.text_content().strip()

                if not href:
                    continue

                link_data = {
                    "href": unescape(href),
                    "text": unescape(text) if text else "",
                    "title": link.get("title", ""),
                }

                # Categorize (simple heuristic)
                if href.startswith(("http://", "https://", "www.")):
                    links["external"].append(link_data)
                else:
                    links["internal"].append(link_data)
            except Exception as e:
                logger.debug(f"Error extracting link: {str(e)}")

        return links

    @staticmethod
    def extract_images(html: str) -> List[Dict[str, str]]:
        """Extract images from HTML.

        Args:
            html: HTML content.

        Returns:
            List of image data.
        """
        images = []

        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML for images: {str(e)}")
            return images

        for img in tree.xpath(".//img"):
            try:
                src = img.get("src", "").strip()
                if src:
                    images.append({
                        "src": src,
                        "alt": img.get("alt", ""),
                        "title": img.get("title", ""),
                        "width": img.get("width", ""),
                        "height": img.get("height", ""),
                    })
            except Exception as e:
                logger.debug(f"Error extracting image: {str(e)}")

        return images

    @staticmethod
    def extract_tables(html: str) -> List[Dict[str, Any]]:
        """Extract tables from HTML.

        Args:
            html: HTML content.

        Returns:
            List of table data.
        """
        tables = []

        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML for tables: {str(e)}")
            return tables

        for table in tree.xpath(".//table"):
            try:
                table_data = {
                    "headers": [],
                    "rows": [],
                    "caption": "",
                }

                # Extract caption
                caption = table.xpath(".//caption/text()")
                if caption:
                    table_data["caption"] = caption[0].strip()

                # Extract headers
                for th in table.xpath(".//th"):
                    table_data["headers"].append(th.text_content().strip())

                # Extract rows
                for tr in table.xpath(".//tr"):
                    row = []
                    for td in tr.xpath(".//td"):
                        row.append(td.text_content().strip())
                    if row:
                        table_data["rows"].append(row)

                if table_data["headers"] or table_data["rows"]:
                    tables.append(table_data)
            except Exception as e:
                logger.debug(f"Error extracting table: {str(e)}")

        return tables

    @staticmethod
    def extract_text(html: str, preserve_structure: bool = True) -> str:
        """Extract text from HTML.

        Args:
            html: HTML content.
            preserve_structure: Whether to preserve HTML structure (headings, etc).

        Returns:
            Extracted text.
        """
        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML for text: {str(e)}")
            return html

        # Remove unwanted tags
        for tag in ContentScraper.REMOVE_TAGS:
            for element in tree.xpath(f".//{tag}"):
                element.getparent().remove(element)

        if preserve_structure:
            # Keep some formatting
            text = tree.text_content()
        else:
            text = tree.text_content()

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)

        return unescape(text)

    @staticmethod
    def extract_metadata(html: str) -> Dict[str, Any]:
        """Extract metadata from HTML.

        Args:
            html: HTML content.

        Returns:
            Metadata dictionary.
        """
        metadata = {}

        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML for metadata: {str(e)}")
            return metadata

        # Title
        title = tree.xpath(".//title/text()")
        if title:
            metadata["title"] = title[0].strip()

        # Meta description
        desc = tree.xpath(".//meta[@name='description']/@content")
        if desc:
            metadata["description"] = desc[0].strip()

        # Open Graph tags
        og_tags = {}
        for meta in tree.xpath(".//meta[@property]"):
            prop = meta.get("property", "")
            content = meta.get("content", "")
            if prop.startswith("og:"):
                og_tags[prop] = content
        if og_tags:
            metadata["og"] = og_tags

        # Twitter Card
        twitter_tags = {}
        for meta in tree.xpath(".//meta[@name]"):
            name = meta.get("name", "")
            content = meta.get("content", "")
            if name.startswith("twitter:"):
                twitter_tags[name] = content
        if twitter_tags:
            metadata["twitter"] = twitter_tags

        # Canonical
        canonical = tree.xpath(".//link[@rel='canonical']/@href")
        if canonical:
            metadata["canonical"] = canonical[0]

        return metadata
