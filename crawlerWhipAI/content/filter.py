"""Content filtering strategies."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict
from rank_bm25 import BM25Okapi
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)


class ContentFilter(ABC):
    """Base class for content filtering."""

    @abstractmethod
    def filter(self, content: str) -> str:
        """Filter content.

        Args:
            content: Content to filter.

        Returns:
            Filtered content.
        """
        pass


class PruningFilter(ContentFilter):
    """Removes irrelevant sections from content."""

    # Tags/patterns to remove
    REMOVE_PATTERNS = [
        r"(?i)cookie|consent|advertisement|ad|sponsored",
        r"(?i)related posts?|similar articles?",
        r"(?i)leave a reply|comment|disqus",
    ]

    # Sections to prune
    PRUNE_KEYWORDS = {
        "footer": ["copyright", "terms", "privacy", "contact"],
        "navigation": ["menu", "nav", "sidebar"],
        "ads": ["advertisement", "ad", "sponsored"],
    }

    def filter(self, content: str) -> str:
        """Remove irrelevant sections.

        Args:
            content: Content to filter.

        Returns:
            Filtered content.
        """
        # Remove lines with ad/promo keywords
        lines = content.split("\n")
        filtered_lines = []

        for line in lines:
            # Check if line contains promotional content
            if self._is_promotional(line):
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _is_promotional(self, line: str) -> bool:
        """Check if line is promotional.

        Args:
            line: Line to check.

        Returns:
            True if promotional.
        """
        line_lower = line.lower()
        promo_keywords = ["ad", "sponsored", "advertisement", "promotional"]
        return any(keyword in line_lower for keyword in promo_keywords)


class BM25Filter(ContentFilter):
    """Filters content using BM25 ranking."""

    def __init__(self, query: str, threshold: float = 0.5):
        """Initialize BM25 filter.

        Args:
            query: Query to rank relevance against.
            threshold: Relevance threshold (0.0 to 1.0).
        """
        self.query = query
        self.threshold = threshold
        self.tokenizer = None

    def filter(self, content: str, keep_threshold: bool = True) -> str:
        """Filter content by relevance.

        Args:
            content: Content to filter.
            keep_threshold: Whether to keep sentences above threshold.

        Returns:
            Filtered content.
        """
        sentences = self._split_sentences(content)
        if not sentences:
            return content

        # Create BM25 index
        try:
            tokenized_sentences = [
                self._tokenize(sentence) for sentence in sentences
            ]
            bm25 = BM25Okapi(tokenized_sentences)
            query_tokens = self._tokenize(self.query)

            # Score sentences
            scores = bm25.get_scores(query_tokens)

            # Keep high-scoring sentences
            filtered_sentences = []
            for i, (sentence, score) in enumerate(zip(sentences, scores)):
                if keep_threshold:
                    if score >= self.threshold:
                        filtered_sentences.append(sentence)
                else:
                    filtered_sentences.append((sentence, score))

            if keep_threshold:
                return " ".join(filtered_sentences)
            else:
                return filtered_sentences
        except Exception as e:
            logger.warning(f"BM25 filtering failed: {str(e)}")
            return content

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences.

        Args:
            text: Text to split.

        Returns:
            List of sentences.
        """
        # Simple sentence splitting
        sentences = []
        current = ""

        for char in text:
            current += char
            if char in ".!?\n":
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text.

        Args:
            text: Text to tokenize.

        Returns:
            List of tokens.
        """
        try:
            tokens = word_tokenize(text.lower())
            # Remove stopwords
            stop_words = set(stopwords.words('english'))
            tokens = [t for t in tokens if t.isalnum() and t not in stop_words]
            return tokens
        except Exception:
            # Fallback to simple split
            return text.lower().split()


class LengthFilter(ContentFilter):
    """Filters content by length."""

    def __init__(self, min_length: int = 100, max_length: int = None):
        """Initialize length filter.

        Args:
            min_length: Minimum content length.
            max_length: Maximum content length (None for no limit).
        """
        self.min_length = min_length
        self.max_length = max_length

    def filter(self, content: str) -> str:
        """Filter by length.

        Args:
            content: Content to filter.

        Returns:
            Original or empty based on length.
        """
        length = len(content)

        if length < self.min_length:
            return ""

        if self.max_length and length > self.max_length:
            return content[:self.max_length]

        return content


class FilterChain:
    """Applies multiple filters in sequence."""

    def __init__(self, filters: List[ContentFilter]):
        """Initialize filter chain.

        Args:
            filters: List of filters to apply.
        """
        self.filters = filters

    def apply(self, content: str) -> str:
        """Apply all filters.

        Args:
            content: Content to filter.

        Returns:
            Filtered content.
        """
        for filter_obj in self.filters:
            content = filter_obj.filter(content)
            if not content:
                return ""

        return content
