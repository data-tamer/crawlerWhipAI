"""LLM Prompt Templates for content processing."""

# System prompts for different tasks


EXTRACTION_SYSTEM_PROMPT = """You are an expert data extraction specialist. Your task is to extract
structured information from web content following the provided schema. Return only valid JSON."""


CONTENT_FILTER_SYSTEM_PROMPT = """You are a content relevance evaluator. Analyze whether the given content
is relevant to the search query or topic. Respond with a relevance score (0-100) and brief explanation."""


SUMMARIZATION_SYSTEM_PROMPT = """You are an expert content summarizer. Create a concise, informative
summary of the given content. Preserve key facts and important details."""


CLASSIFICATION_SYSTEM_PROMPT = """You are a content classifier. Analyze the given content and classify it
into one or more appropriate categories. Return categories as a JSON array."""


EXTRACTION_FIELD_SYSTEM_PROMPT = """You are a field extraction specialist. Extract specific information
fields from content. Return results as valid JSON with the requested field names."""


LINK_ANALYSIS_SYSTEM_PROMPT = """You are a link analysis expert. Analyze links and their context to
determine relevance, authority, and importance. Return analysis as JSON."""


# User prompt templates


EXTRACTION_USER_TEMPLATE = """Extract information from the following content according to this schema:
{schema}

Content:
{content}

Return only valid JSON matching the schema."""


CONTENT_FILTER_USER_TEMPLATE = """Evaluate the relevance of this content to the query/topic:
Query/Topic: {query}

Content:
{content}

Respond with JSON: {{"relevance_score": 0-100, "explanation": "reason"}}"""


SUMMARIZATION_USER_TEMPLATE = """Summarize the following content in 2-3 sentences:

{content}

Summary:"""


CLASSIFICATION_USER_TEMPLATE = """Classify this content into relevant categories:

Content:
{content}

Available categories: {categories}

Return as JSON: {{"categories": ["cat1", "cat2"]}}"""


FIELD_EXTRACTION_USER_TEMPLATE = """Extract the following fields from the content:
{fields}

Content:
{content}

Return as JSON with the requested field names."""


LINK_ANALYSIS_USER_TEMPLATE = """Analyze this link and its context:
URL: {url}
Link text: {link_text}
Context: {context}

Return JSON analysis with: relevance, authority, importance, description"""


TITLE_GENERATION_USER_TEMPLATE = """Generate a concise, descriptive title for this content:

{content}

Title:"""


METADATA_EXTRACTION_USER_TEMPLATE = """Extract metadata from this content:

{content}

Return JSON with: title, description, keywords, author, publish_date"""


# LLM Configuration templates


class PromptTemplate:
    """Base class for prompt templates."""

    def __init__(self, name: str, system: str, user: str):
        """Initialize template.

        Args:
            name: Template name.
            system: System prompt.
            user: User prompt template with {placeholders}.
        """
        self.name = name
        self.system = system
        self.user = user

    def format(self, **kwargs) -> tuple:
        """Format prompts with variables.

        Args:
            **kwargs: Template variables.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        return (
            self.system,
            self.user.format(**kwargs)
        )


# Template registry


TEMPLATES = {
    "extraction": PromptTemplate(
        name="extraction",
        system=EXTRACTION_SYSTEM_PROMPT,
        user=EXTRACTION_USER_TEMPLATE
    ),
    "content_filter": PromptTemplate(
        name="content_filter",
        system=CONTENT_FILTER_SYSTEM_PROMPT,
        user=CONTENT_FILTER_USER_TEMPLATE
    ),
    "summarization": PromptTemplate(
        name="summarization",
        system=SUMMARIZATION_SYSTEM_PROMPT,
        user=SUMMARIZATION_USER_TEMPLATE
    ),
    "classification": PromptTemplate(
        name="classification",
        system=CLASSIFICATION_SYSTEM_PROMPT,
        user=CLASSIFICATION_USER_TEMPLATE
    ),
    "field_extraction": PromptTemplate(
        name="field_extraction",
        system=EXTRACTION_FIELD_SYSTEM_PROMPT,
        user=FIELD_EXTRACTION_USER_TEMPLATE
    ),
    "link_analysis": PromptTemplate(
        name="link_analysis",
        system=LINK_ANALYSIS_SYSTEM_PROMPT,
        user=LINK_ANALYSIS_USER_TEMPLATE
    ),
    "title_generation": PromptTemplate(
        name="title_generation",
        system="Generate concise, descriptive titles.",
        user=TITLE_GENERATION_USER_TEMPLATE
    ),
    "metadata_extraction": PromptTemplate(
        name="metadata_extraction",
        system="Extract structured metadata from content.",
        user=METADATA_EXTRACTION_USER_TEMPLATE
    ),
}


def get_template(name: str) -> PromptTemplate:
    """Get a template by name.

    Args:
        name: Template name.

    Returns:
        PromptTemplate instance.

    Raises:
        ValueError: If template not found.
    """
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Template '{name}' not found. Available: {available}")
    return TEMPLATES[name]


def list_templates() -> list:
    """Get list of available templates.

    Returns:
        List of template names.
    """
    return list(TEMPLATES.keys())


# Utility functions for prompt management


def create_custom_template(
    name: str,
    system: str,
    user: str,
    override: bool = False
) -> PromptTemplate:
    """Create a custom template.

    Args:
        name: Template name.
        system: System prompt.
        user: User prompt with {placeholders}.
        override: Whether to override existing template.

    Returns:
        PromptTemplate instance.

    Raises:
        ValueError: If template exists and override=False.
    """
    if name in TEMPLATES and not override:
        raise ValueError(f"Template '{name}' already exists. Set override=True to replace.")

    template = PromptTemplate(name, system, user)
    TEMPLATES[name] = template
    return template


def validate_template(name: str, **kwargs) -> bool:
    """Validate that template can be formatted with given kwargs.

    Args:
        name: Template name.
        **kwargs: Template variables.

    Returns:
        True if template can be formatted.
    """
    try:
        template = get_template(name)
        template.format(**kwargs)
        return True
    except KeyError:
        return False
