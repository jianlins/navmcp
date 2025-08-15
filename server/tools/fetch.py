"""
Fetch tool for MCP Browser Tools

Provides the fetch_url tool for navigating to web pages and retrieving content.
"""

import asyncio
import time
from typing import Callable, Dict, Any, Optional, Annotated

from pydantic import BaseModel, Field
from selenium.common.exceptions import WebDriverException, TimeoutException
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from server.utils.net import validate_url_security, normalize_url
from server.utils.parsing import clean_text_content, truncate_text


class FetchUrlInput(BaseModel):
    """Input schema for fetch_url tool."""
    url: str = Field(
        description="The complete URL to fetch and navigate to (must include http:// or https://)",
        examples=["https://www.example.com", "https://www.google.com/search?q=python"],
        min_length=1,
        max_length=2048
    )


class FetchUrlOutput(BaseModel):
    """Output schema for fetch_url tool."""
    final_url: str = Field(description="Final URL after redirects")
    title: str = Field(description="Page title")
    html: str = Field(description="Page HTML content")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


async def fetch_url(
    url: str,
    get_browser_manager: Callable = None
) -> FetchUrlOutput:
    """
    Navigate to a URL and fetch its complete content using a browser.

    This tool uses a real browser (Chrome) to navigate to the specified URL,
    waits for the page to fully load, and returns comprehensive information
    including the final URL (after redirects), page title, and complete HTML content.

    Args:
        url: The complete URL to fetch (must include http:// or https://)
        get_browser_manager: Optional callable to get browser manager

    Returns:
        FetchUrlOutput with page content, metadata, and status information
    """
    url = url.strip()
    start_time = time.time()

    logger.info(f"Fetching URL: {url}")

    try:
        # Validate URL security
        is_valid, error_msg = validate_url_security(url, allow_private=False)
        if not is_valid:
            logger.warning(f"URL validation failed for {url}: {error_msg}")
            return FetchUrlOutput(
                final_url=url,
                title="",
                html="",
                status="error",
                error=f"URL validation failed: {error_msg}"
            )

        # Normalize URL
        normalized_url = normalize_url(url)

        # Get browser manager
        if get_browser_manager is None:
            from server.app import get_browser_manager as default_browser_manager
            browser_manager = await default_browser_manager()
        else:
            browser_manager = await get_browser_manager()
        if not browser_manager:
            return FetchUrlOutput(
                final_url=url,
                title="",
                html="",
                status="error",
                error="Browser manager not available"
            )

        # Perform the fetch with retry logic
        result = await _fetch_page_with_retry(browser_manager, normalized_url)

        # Add timing metadata
        duration = time.time() - start_time
        result.metadata["duration_seconds"] = round(duration, 2)
        result.metadata["timestamp"] = time.time()

        logger.info(f"Fetch completed for {url} in {duration:.2f}s - Status: {result.status}")
        return result

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Unexpected error fetching {url}: {error_msg}")

        return FetchUrlOutput(
            final_url=url,
            title="",
            html="",
            status="error",
            error=f"Unexpected error: {error_msg}",
            metadata={"duration_seconds": round(duration, 2)}
        )

def setup_fetch_tools(mcp, get_browser_manager: Callable):
    """Setup fetch-related MCP tools."""

    @mcp.tool()
    async def fetch_url_tool(
        url: Annotated[str, Field(
            description="The complete URL to fetch and navigate to (must include http:// or https://)",
            examples=["https://www.example.com", "https://www.google.com/search?q=python"],
            min_length=1,
            max_length=2048
        )]
    ) -> FetchUrlOutput:
        return await fetch_url(url, get_browser_manager)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def _fetch_page_with_retry(browser_manager, url: str) -> FetchUrlOutput:
    """
    Fetch a page with retry logic for transient failures.
    
    Args:
        browser_manager: Browser manager instance
        url: URL to fetch
        
    Returns:
        FetchUrlOutput with the page content
        
    Raises:
        Exception: If all retry attempts fail
    """
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Navigate to the URL
        logger.debug(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for basic page load (check if document is ready)
        await _wait_for_page_load(driver)
        
        # Get final URL after redirects
        final_url = driver.current_url
        
        # Get page title
        title = ""
        try:
            title = driver.title or ""
            title = clean_text_content(title)
        except Exception as e:
            logger.warning(f"Could not get page title: {e}")
        
        # Get page source
        html = ""
        try:
            html = driver.page_source or ""
        except Exception as e:
            logger.warning(f"Could not get page source: {e}")
            html = ""
        
        # Basic metadata
        metadata = {
            "redirected": final_url != url,
            "title_length": len(title),
            "html_length": len(html),
        }
        
        return FetchUrlOutput(
            final_url=final_url,
            title=title,
            html=html,
            status="ok",
            metadata=metadata
        )
        
    except TimeoutException as e:
        logger.warning(f"Page load timeout for {url}: {e}")
        return FetchUrlOutput(
            final_url=url,
            title="",
            html="",
            status="error",
            error=f"Page load timeout: {str(e)}"
        )
        
    except WebDriverException as e:
        logger.warning(f"WebDriver error for {url}: {e}")
        
        # Check if it's a recoverable error
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['net::', 'dns', 'connection', 'timeout']):
            # Network-related error, might be worth retrying
            raise
        
        return FetchUrlOutput(
            final_url=url,
            title="",
            html="",
            status="error",
            error=f"Browser error: {str(e)}"
        )


async def _wait_for_page_load(driver, max_wait: int = 30) -> None:
    """
    Wait for page to load completely using JavaScript ready state.
    
    Args:
        driver: Selenium WebDriver instance
        max_wait: Maximum seconds to wait
    """
    end_time = time.time() + max_wait
    
    while time.time() < end_time:
        try:
            # Check if document ready state is complete
            ready_state = driver.execute_script("return document.readyState")
            if ready_state == "complete":
                # Give a small additional wait for dynamic content
                await asyncio.sleep(0.5)
                return
        except Exception as e:
            logger.debug(f"Error checking ready state: {e}")
        
        await asyncio.sleep(0.1)
    
    logger.warning(f"Page load wait timeout ({max_wait}s)")


# Additional helper for debugging
async def _get_page_info(driver) -> Dict[str, Any]:
    """
    Get additional page information for debugging.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        Dictionary with page information
    """
    info = {}
    
    try:
        info["ready_state"] = driver.execute_script("return document.readyState")
        info["url"] = driver.current_url
        info["title"] = driver.title
        
        # Check for common loading indicators
        try:
            loading_elements = driver.find_elements("css selector", "[class*='loading'], [class*='spinner']")
            info["loading_elements_count"] = len(loading_elements)
        except Exception:
            info["loading_elements_count"] = 0
        
    except Exception as e:
        info["error"] = str(e)
    
    return info
