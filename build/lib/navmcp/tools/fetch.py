import urllib.parse
import os

# Persistent blacklist file
_BLACKLIST_FILE = os.path.join(os.path.dirname(__file__), "blocked_domains.txt")
_blocked_bot_domains = set()

def get_root_domain(url: str) -> str:
    """Extract root domain from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        parts = host.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return host
    except Exception:
        return url

def load_blocked_domains():
    """Load blocked domains from disk."""
    if os.path.exists(_BLACKLIST_FILE):
        try:
            with open(_BLACKLIST_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    domain = line.strip()
                    if domain:
                        _blocked_bot_domains.add(domain)
        except Exception as e:
            print(f"Failed to load blocked domains: {e}")

def save_blocked_domains():
    """Save blocked domains to disk."""
    try:
        with open(_BLACKLIST_FILE, "w", encoding="utf-8") as f:
            for domain in sorted(_blocked_bot_domains):
                f.write(domain + "\n")
    except Exception as e:
        print(f"Failed to save blocked domains: {e}")

def is_domain_blocked(url: str) -> bool:
    domain = get_root_domain(url)
    return domain in _blocked_bot_domains

def block_domain(url: str):
    domain = get_root_domain(url)
    if domain not in _blocked_bot_domains:
        _blocked_bot_domains.add(domain)
        save_blocked_domains()

# Load blacklist on module import
load_blocked_domains()
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

from navmcp.utils.net import validate_url_security, normalize_url
from navmcp.utils.parsing import clean_text_content, truncate_text


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

        # Check if domain is blocked due to bot protection
        if is_domain_blocked(url):
            logger.warning(f"Skipping fetch for blocked domain: {get_root_domain(url)} (bot protection previously failed)")
            return FetchUrlOutput(
                final_url=url,
                title="",
                html="",
                status="error",
                error=f"Bot protection previously failed for domain: {get_root_domain(url)}"
            )

        # Normalize URL
        normalized_url = normalize_url(url)

        # Get browser manager
        if get_browser_manager is None:
            from navmcp.app import get_browser_manager as default_browser_manager
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

        # If bot protection failed, block domain
        if result.status == "error" and result.error and "Bot protection detected" in result.error:
            block_domain(url)

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

    @mcp.tool(name="fetch_url")
    async def fetch_url_mcp(
        url: Annotated[str, Field(
            description="The complete URL to fetch and navigate to (must include http:// or https://)",
            examples=["https://www.example.com", "https://www.google.com/search?q=python"],
            min_length=1,
            max_length=2048
        )]
    ) -> FetchUrlOutput:
        return await fetch_url(url, get_browser_manager)

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
        bot_attempts = 0
        max_bot_attempts = 2
        while True:
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
            # Bot protection detection
            bot_protection_signatures = [
                "Just a moment...",
                "Verifying you are human",
                "Cloudflare",
                "cloudflare",
                "needs to review the security of your connection"
            ]
            bot_protection_detected = any(sig in html for sig in bot_protection_signatures)
            # Check for main content if bot protection detected
            if bot_protection_detected:
                try:
                    article_loaded = driver.execute_script(
                        """
                        const el = document.querySelector('article, main, .article-content, #article-details, .content, #content, .post, .entry, .body, .page-content');
                        if (el && el.innerText && el.innerText.trim().length > 200) return true;
                        const bodyText = document.body && document.body.innerText ? document.body.innerText.trim() : '';
                        if (bodyText.length > 200) return true;
                        if (/abstract/i.test(bodyText)) return 'wait_for_abstract';
                        return false;
                        """
                    )
                    if article_loaded == 'wait_for_abstract':
                        logger.info("'abstract' found in page text, waiting 3 more seconds for dynamic content...")
                        await asyncio.sleep(3)
                        article_loaded = True
                except Exception as e:
                    logger.warning(f"Error checking for article content: {e}")
                # If main content is present, ignore bot protection and return success
                if article_loaded:
                    return FetchUrlOutput(
                        final_url=final_url,
                        title=title,
                        html=html,
                        status="ok",
                        metadata=metadata
                    )
                # Otherwise, proceed with bot protection handling
                bot_attempts += 1
                if bot_attempts > max_bot_attempts:
                    logger.warning(f"Bot protection detected after {max_bot_attempts} attempts. Aborting.")
                    return FetchUrlOutput(
                        final_url=final_url,
                        title=title,
                        html=html,
                        status="error",
                        error=f"Bot protection detected after {max_bot_attempts} attempts. Aborting.",
                        metadata=metadata
                    )
                # Switch to non-headless mode and restart browser for manual intervention
                await browser_manager.set_headless(False)
                # Re-fetch the page in headed mode
                driver = await browser_manager.get_driver()
                driver.get(url)
                await _wait_for_page_load(driver)
                # Wait for user to manually click and page to refresh
                logger.info("Waiting up to 60 seconds for manual user interaction and page refresh...")
                max_wait = 20
                check_interval = 5
                for i in range(0, max_wait, check_interval):
                    await asyncio.sleep(check_interval)
                    html = driver.page_source or ""
                    # If bot protection keywords are gone, break
                    if not any(sig in html for sig in bot_protection_signatures):
                        logger.info("Bot protection passed, real content loaded.")
                        break
                    else:
                        logger.info(f"Bot protection still detected after {i+check_interval}s.")
                # Optionally, check for main article content loaded
                try:
                    article_loaded = driver.execute_script(
                        """
                        const el = document.querySelector('article, main, .article-content, #article-details, .content, #content, .post, .entry, .body, .page-content');
                        if (el && el.innerText && el.innerText.trim().length > 200) return true;
                        const bodyText = document.body && document.body.innerText ? document.body.innerText.trim() : '';
                        if (bodyText.length > 200) return true;
                        if (/abstract/i.test(bodyText)) return 'wait_for_abstract';
                        return false;
                        """
                    )
                    if article_loaded == 'wait_for_abstract':
                        logger.info("'abstract' found in page text, waiting 3 more seconds for dynamic content...")
                        await asyncio.sleep(3)
                        article_loaded = True
                    if not article_loaded:
                        logger.warning("Main article content not detected after manual click.")
                except Exception as e:
                    logger.warning(f"Error checking for article content: {e}")
                title = driver.title or ""
                final_url = driver.current_url
                metadata["manual_intervention"] = True
                # If bot protection keywords are still present, retry or abort
                if any(sig in html for sig in bot_protection_signatures):
                    continue  # Will retry if attempts < max_bot_attempts
                # Otherwise, return success
                return FetchUrlOutput(
                    final_url=final_url,
                    title=title,
                    html=html,
                    status="ok",
                    metadata=metadata
                )
            else:
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
        error_msg = str(e).lower()
        # Retry with new session if invalid session id
        if "invalid session id" in error_msg:
            logger.info("Detected invalid session id, restarting browser and retrying fetch once.")
            await browser_manager.restart_driver()
            try:
                driver = await browser_manager.get_driver()
                driver.get(url)
                await _wait_for_page_load(driver)
                final_url = driver.current_url
                title = ""
                try:
                    title = driver.title or ""
                    title = clean_text_content(title)
                except Exception as e2:
                    logger.warning(f"Could not get page title after restart: {e2}")
                html = ""
                try:
                    html = driver.page_source or ""
                except Exception as e2:
                    logger.warning(f"Could not get page source after restart: {e2}")
                    html = ""
                metadata = {
                    "redirected": final_url != url,
                    "title_length": len(title),
                    "html_length": len(html),
                    "restarted_session": True,
                }
                return FetchUrlOutput(
                    final_url=final_url,
                    title=title,
                    html=html,
                    status="ok",
                    metadata=metadata
                )
            except Exception as e2:
                logger.error(f"Failed to recover from invalid session id: {e2}")
                return FetchUrlOutput(
                    final_url=url,
                    title="",
                    html="",
                    status="error",
                    error=f"Browser error after restart: {str(e2)}"
                )
        # Check if it's a recoverable error
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


async def _wait_for_page_load(driver, max_wait: int = 30, extra_wait: float = 3.0) -> None:
    """
    Wait for page to load completely using document.readyState, then wait extra seconds.
    Args:
        driver: Selenium WebDriver instance
        max_wait: Maximum seconds to wait for document.readyState == "complete"
        extra_wait: Additional seconds to wait after readyState is "complete" (default 3.0)
    """
    end_time = time.time() + max_wait
    ready = False
    while time.time() < end_time:
        try:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state == "complete":
                ready = True
                logger.debug("document.readyState is complete.")
                break
        except Exception as e:
            logger.debug(f"Error checking ready state: {e}")
        await asyncio.sleep(0.1)
    if not ready:
        logger.warning(f"Page load wait timeout ({max_wait}s)")
        return
    # Extra wait for dynamic content
    logger.debug(f"Waiting extra {extra_wait} seconds for dynamic content.")
    await asyncio.sleep(extra_wait)


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
