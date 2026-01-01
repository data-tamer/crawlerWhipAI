"""Configuration models for CrawlerWhipAI."""

from typing import Optional, List, Dict, Union, Any
from enum import Enum
from pydantic import BaseModel, Field


class CacheMode(str, Enum):
    """Cache operation modes."""

    BYPASS = "bypass"  # Don't use cache
    CACHED = "cached"  # Use cache, update if needed
    WRITE_ONLY = "write_only"  # Only write to cache, don't read
    READ_ONLY = "read_only"  # Only read from cache


class BrowserType(str, Enum):
    """Browser engine types."""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class WaitUntil(str, Enum):
    """Page load wait conditions."""

    COMMIT = "commit"  # Fastest - when navigation is committed
    DOMCONTENTLOADED = "domcontentloaded"  # Fast - DOM is ready
    LOAD = "load"  # Medium - all resources loaded
    NETWORKIDLE = "networkidle"  # Slowest - no network activity


class BrowserConfig(BaseModel):
    """Browser-specific configuration."""

    browser_type: BrowserType = Field(
        default=BrowserType.CHROMIUM,
        description="Browser engine to use"
    )
    headless: bool = Field(
        default=True,
        description="Run browser in headless mode"
    )
    disable_images: bool = Field(
        default=False,
        description="Disable image loading for faster crawling"
    )
    disable_css: bool = Field(
        default=False,
        description="Disable CSS loading"
    )
    disable_javascript: bool = Field(
        default=False,
        description="Disable JavaScript execution for faster crawling"
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="Custom user agent string"
    )
    user_agent_mode: str = Field(
        default="",
        description="'random' for random user agents"
    )
    enable_stealth: bool = Field(
        default=False,
        description="Use stealth mode to avoid bot detection"
    )
    viewport_width: int = Field(
        default=1920,
        description="Viewport width in pixels"
    )
    viewport_height: int = Field(
        default=1080,
        description="Viewport height in pixels"
    )
    timezone_id: Optional[str] = Field(
        default=None,
        description="Timezone (e.g., 'America/New_York')"
    )
    geolocation: Optional[Dict[str, float]] = Field(
        default=None,
        description="Geolocation with 'latitude', 'longitude', 'accuracy'"
    )
    locale: Optional[str] = Field(
        default=None,
        description="Locale (e.g., 'en-US')"
    )
    proxy: Optional[str] = Field(
        default=None,
        description="Proxy URL (http://user:pass@host:port)"
    )
    cookies: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Cookies to set in browser context"
    )


class CrawlerConfig(BaseModel):
    """Main crawler configuration."""

    # Navigation
    wait_until: WaitUntil = Field(
        default=WaitUntil.DOMCONTENTLOADED,
        description="When to consider page loaded"
    )
    page_timeout: int = Field(
        default=30000,
        description="Page load timeout in milliseconds"
    )

    # Content loading
    wait_for: Optional[str] = Field(
        default=None,
        description="CSS selector or JS condition to wait for"
    )
    wait_for_timeout: Optional[int] = Field(
        default=None,
        description="Timeout for wait condition in milliseconds"
    )
    wait_for_images: bool = Field(
        default=False,
        description="Wait for all images to load"
    )
    delay_before_return_html: float = Field(
        default=0.1,
        description="Delay before returning HTML in seconds"
    )

    # JavaScript execution
    js_code: Union[str, List[str], None] = Field(
        default=None,
        description="JavaScript code to execute on page"
    )
    js_only: bool = Field(
        default=False,
        description="Only execute JS, don't navigate"
    )

    # Page interaction
    scan_full_page: bool = Field(
        default=False,
        description="Scroll to bottom to load all content"
    )
    scroll_delay: float = Field(
        default=0.2,
        description="Delay between scrolls in seconds"
    )
    max_scroll_steps: Optional[int] = Field(
        default=None,
        description="Maximum scroll iterations"
    )
    process_iframes: bool = Field(
        default=False,
        description="Extract content from iframes"
    )
    remove_overlay_elements: bool = Field(
        default=False,
        description="Remove popup overlays"
    )
    adjust_viewport_to_content: bool = Field(
        default=False,
        description="Resize viewport to content size"
    )
    override_navigator: bool = Field(
        default=False,
        description="Override navigator properties"
    )
    simulate_user: bool = Field(
        default=False,
        description="Simulate user interactions"
    )

    # Content filtering
    filter_content: bool = Field(
        default=False,
        description="Apply content filtering"
    )
    exclude_external_links: bool = Field(
        default=False,
        description="Exclude external links from extraction"
    )
    exclude_social_media_links: bool = Field(
        default=False,
        description="Exclude social media links"
    )

    # Markdown generation
    markdown_generator: Optional[str] = Field(
        default=None,
        description="Custom markdown generator strategy"
    )

    # Media
    screenshot: bool = Field(
        default=False,
        description="Capture screenshot"
    )
    pdf: bool = Field(
        default=False,
        description="Export as PDF"
    )
    capture_mhtml: bool = Field(
        default=False,
        description="Capture MHTML snapshot"
    )

    # HTTP
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom HTTP headers"
    )
    cookies: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Cookies to set"
    )

    # Caching
    cache_mode: CacheMode = Field(
        default=CacheMode.CACHED,
        description="Cache operation mode"
    )
    cache_ttl_hours: int = Field(
        default=24,
        description="Cache time-to-live in hours"
    )

    # Robots.txt compliance
    check_robots_txt: bool = Field(
        default=False,
        description="Check robots.txt before crawling"
    )

    # Deep crawling
    max_depth: int = Field(
        default=0,
        description="Maximum crawl depth (0 = single page only)"
    )
    max_pages: int = Field(
        default=1,
        description="Maximum pages to crawl"
    )

    # PWA/SPA support
    preserve_url_fragment: bool = Field(
        default=False,
        description="Preserve URL fragments (#) for PWA/SPA with hash-based routing"
    )

    # Performance optimization
    http_first: bool = Field(
        default=False,
        description="Try lightweight HTTP fetch first, fallback to browser if JS needed"
    )
    http_timeout: float = Field(
        default=10.0,
        description="Timeout for HTTP-first fetch in seconds"
    )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class VirtualScrollConfig(BaseModel):
    """Configuration for virtual scroll handling."""

    container_selector: str = Field(
        ..., description="CSS selector of scrollable container"
    )
    scroll_count: int = Field(
        default=10, description="Number of scroll operations"
    )
    scroll_by: Union[str, int] = Field(
        default="container_height",
        description="Scroll amount (container_height, page_height, or pixels)"
    )
    wait_after_scroll: float = Field(
        default=0.5, description="Wait time after each scroll in seconds"
    )
    detection_type: str = Field(
        default="auto",
        description="Detection type (auto, append, replace)"
    )
