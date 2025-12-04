"""Markdown generation from HTML."""

import logging
import re
from typing import Dict, List, Tuple
from html import unescape
from lxml import html as lxml_html

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """Converts HTML to Markdown format."""

    def __init__(self, preserve_links: bool = True, generate_citations: bool = True):
        """Initialize converter.

        Args:
            preserve_links: Whether to preserve links in output.
            generate_citations: Whether to generate citations for links.
        """
        self.preserve_links = preserve_links
        self.generate_citations = generate_citations
        self.links: Dict[int, str] = {}
        self.link_counter = 0

    def convert(self, html: str) -> Tuple[str, str, str]:
        """Convert HTML to markdown.

        Args:
            html: HTML content.

        Returns:
            Tuple of (markdown, markdown_with_citations, references).
        """
        # Reset state
        self.links = {}
        self.link_counter = 0

        try:
            tree = lxml_html.fromstring(html)
        except Exception as e:
            logger.warning(f"Failed to parse HTML: {str(e)}")
            return html, html, ""

        # Remove script and style
        for tag in ["script", "style"]:
            for element in tree.xpath(f".//{tag}"):
                element.getparent().remove(element)

        # Convert to markdown
        markdown = self._element_to_markdown(tree)

        # Generate references if citations enabled
        markdown_with_citations = markdown
        references = ""

        if self.generate_citations and self.links:
            markdown_with_citations = self._add_citations(markdown)
            references = self._generate_references()

        return markdown, markdown_with_citations, references

    def _element_to_markdown(self, element) -> str:
        """Convert element to markdown.

        Args:
            element: lxml element.

        Returns:
            Markdown string.
        """
        if element.tag in ["script", "style"]:
            return ""

        # Heading tags
        if element.tag == "h1":
            return f"# {self._get_text(element)}\n\n"
        if element.tag == "h2":
            return f"## {self._get_text(element)}\n\n"
        if element.tag == "h3":
            return f"### {self._get_text(element)}\n\n"
        if element.tag == "h4":
            return f"#### {self._get_text(element)}\n\n"
        if element.tag == "h5":
            return f"##### {self._get_text(element)}\n\n"
        if element.tag == "h6":
            return f"###### {self._get_text(element)}\n\n"

        # Block elements
        if element.tag == "p":
            text = self._convert_inline(element)
            return f"{text}\n\n"
        if element.tag in ["div", "section", "article"]:
            result = ""
            for child in element:
                result += self._element_to_markdown(child)
            if element.text and element.text.strip():
                result = element.text.strip() + "\n\n" + result
            return result

        # List elements
        if element.tag == "ul":
            return self._convert_list(element, ordered=False)
        if element.tag == "ol":
            return self._convert_list(element, ordered=True)

        # Table
        if element.tag == "table":
            return self._convert_table(element)

        # Blockquote
        if element.tag == "blockquote":
            text = self._get_text(element).strip()
            lines = text.split("\n")
            quoted = "\n".join(f"> {line}" for line in lines)
            return f"{quoted}\n\n"

        # Code
        if element.tag == "pre":
            code = self._get_text(element)
            return f"```\n{code}\n```\n\n"
        if element.tag == "code":
            return f"`{self._get_text(element)}`"

        # Inline or text node
        result = ""
        if element.text:
            result += self._convert_inline(element) if element.tag in ["span", "a", "strong", "em", "b", "i"] else element.text

        for child in element:
            result += self._element_to_markdown(child)
            if child.tail:
                result += child.tail

        return result

    def _convert_inline(self, element) -> str:
        """Convert inline elements.

        Args:
            element: lxml element.

        Returns:
            Converted text with formatting.
        """
        result = ""

        if element.tag == "a" and self.preserve_links:
            href = element.get("href", "")
            text = self._get_text(element)
            if href:
                self.link_counter += 1
                self.links[self.link_counter] = href
                if self.generate_citations:
                    result += f"{text}[{self.link_counter}]"
                else:
                    result += f"[{text}]({href})"
            else:
                result += text
        elif element.tag in ["strong", "b"]:
            result += f"**{self._get_text(element)}**"
        elif element.tag in ["em", "i"]:
            result += f"*{self._get_text(element)}*"
        elif element.tag == "u":
            result += self._get_text(element)  # Markdown doesn't support underline
        elif element.tag == "code":
            result += f"`{self._get_text(element)}`"
        else:
            result += self._get_text(element)

        return result

    def _convert_list(self, element, ordered: bool = False) -> str:
        """Convert list to markdown.

        Args:
            element: lxml element.
            ordered: Whether it's an ordered list.

        Returns:
            Markdown list.
        """
        result = ""
        counter = 1

        for li in element.xpath(".//li"):
            text = self._get_text(li).strip()
            if ordered:
                result += f"{counter}. {text}\n"
                counter += 1
            else:
                result += f"- {text}\n"

        return result + "\n"

    def _convert_table(self, element) -> str:
        """Convert table to markdown.

        Args:
            element: Table element.

        Returns:
            Markdown table.
        """
        result = ""

        # Get headers
        headers = []
        for th in element.xpath(".//thead//th | .//tr[1]//th"):
            headers.append(self._get_text(th).strip())

        if headers:
            result += "| " + " | ".join(headers) + " |\n"
            result += "|" + "|".join(["---"] * len(headers)) + "|\n"

        # Get rows
        for tr in element.xpath(".//tbody//tr | .//tr"):
            cells = []
            for td in tr.xpath(".//td"):
                cells.append(self._get_text(td).strip())
            if cells and len(cells) == len(headers):
                result += "| " + " | ".join(cells) + " |\n"

        return result + "\n"

    def _add_citations(self, markdown: str) -> str:
        """Add citation markers to markdown.

        Args:
            markdown: Markdown text.

        Returns:
            Markdown with citations.
        """
        return markdown

    def _generate_references(self) -> str:
        """Generate references section.

        Returns:
            References markdown.
        """
        if not self.links:
            return ""

        result = "\n## References\n\n"
        for num, url in sorted(self.links.items()):
            result += f"[{num}]: {url}\n"

        return result

    def _get_text(self, element) -> str:
        """Get all text from element.

        Args:
            element: lxml element.

        Returns:
            Text content.
        """
        text = element.text_content()
        return unescape(text).strip()
