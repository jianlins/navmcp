"""
Parse tools for MCP Browser Tools

Provides the find_elements tool for parsing web pages and extracting element information.
"""

import time
from typing import Callable, Dict, List, Any, Optional, Annotated

from pydantic import BaseModel, Field
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

from navmcp.utils.net import validate_url_security, normalize_url
from navmcp.utils.parsing import (
    normalize_selector, detect_selector_type, extract_element_attributes,
    extract_element_text, get_element_outer_html, is_visible_element
)


class FindElementsInput(BaseModel):
    """Input schema for find_elements tool."""
    selector: str = Field(
        description="CSS selector or XPath expression to find elements on the page",
        examples=[
            "div.content", 
            "a[href*='github']", 
            "//button[@class='submit']", 
            "input[type='email']",
            "#main-content h2"
        ],
        min_length=1,
        max_length=512
    )
    by: str = Field(
        default="css", 
        description="Selector type to use for finding elements",
        examples=["css", "xpath"],
        pattern="^(css|xpath)$"
    )
    url: Optional[str] = Field(
        None, 
        description="Optional URL to navigate to before finding elements (if not provided, searches current page)",
        examples=["https://www.example.com", "https://github.com/search?q=python"],
        max_length=2048
    )
    max: Optional[int] = Field(
        10, 
        description="Maximum number of elements to return (capped at 100 for performance)",
        ge=1,
        le=100,
        examples=[5, 10, 20]
    )
    visible_only: bool = Field(
        True, 
        description="If true, only return elements that are visible on the page (not hidden by CSS)",
        examples=[True, False]
    )


class ElementInfo(BaseModel):
    """Information about a single element."""
    text: str = Field(description="Element text content")
    attrs: Dict[str, str] = Field(description="Element attributes")
    outer_html: str = Field(description="Element outer HTML")
    tag_name: str = Field(description="Element tag name")
    is_displayed: bool = Field(description="Whether element is displayed")


class FindElementsOutput(BaseModel):
    """Output schema for find_elements tool."""
    count: int = Field(description="Number of elements found")
    elements: List[ElementInfo] = Field(description="List of found elements")
    url: str = Field(description="Current page URL")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def setup_parse_tools(mcp, get_browser_manager: Callable):
    """Setup parse-related MCP tools."""
    
    @mcp.tool()
    async def find_elements(
        selector: Annotated[str, Field(
            description="CSS selector or XPath expression to find elements on the page",
            examples=[
                "div.content", 
                "a[href*='github']", 
                "//button[@class='submit']", 
                "input[type='email']",
                "#main-content h2"
            ],
            min_length=1,
            max_length=512
        )],
        by: Annotated[str, Field(
            default="css", 
            description="Selector type to use for finding elements",
            examples=["css", "xpath"],
            pattern="^(css|xpath)$"
        )] = "css",
        url: Annotated[Optional[str], Field(
            description="Optional URL to navigate to before finding elements (if not provided, searches current page)",
            examples=["https://www.example.com", "https://github.com/search?q=python"],
            max_length=2048
        )] = None,
        max: Annotated[int, Field(
            description="Maximum number of elements to return (capped at 100 for performance)",
            ge=1,
            le=100,
            examples=[5, 10, 20]
        )] = 10,
        visible_only: Annotated[bool, Field(
            description="If true, only return elements that are visible on the page (not hidden by CSS)",
            examples=[True, False]
        )] = True
    ) -> FindElementsOutput:
        """
        Find and extract information from elements on a web page using CSS selectors or XPath.
        
        This powerful tool searches for elements on the current page or optionally navigates 
        to a URL first, then finds all elements matching the specified selector. Returns detailed
        information about each found element including text content, attributes, HTML, and visibility.
        
        Key features:
        - Supports both CSS selectors and XPath expressions
        - Auto-detects selector type if not specified
        - Filters for visible elements only (configurable)
        - Extracts comprehensive element information
        - Handles dynamic content and JavaScript-rendered pages
        - Performance-optimized with configurable limits
        
        Selector examples:
        - CSS: "div.content", "a[href*='github']", "#main-content h2", "input[type='email']"
        - XPath: "//button[@class='submit']", "//div[contains(text(), 'Login')]"
        
        Use cases:
        - Extracting data from web pages (scraping)
        - Finding specific UI elements for interaction
        - Analyzing page structure and content
        - Locating elements before clicking or typing
        - Gathering links, images, or form elements
        
        Example usage:
        - input: {"selector": "a", "max": 5} - Find first 5 links on current page
        - input: {"selector": "div.product", "url": "https://shop.example.com"} - Find products after navigating
        - input: {"selector": "//button[text()='Submit']", "by": "xpath"} - Find submit button using XPath
        
        Args:
            selector: CSS selector or XPath expression to find elements
            by: Selector type ('css' or 'xpath')
            url: Optional URL to navigate to first
            max: Maximum number of elements to return
            visible_only: Whether to return only visible elements
            
        Returns:
            FindElementsOutput with found elements, count, and metadata
        """
        selector = selector.strip()
        by = by.lower()
        url = url.strip() if url else None
        max_elements = min(max or 10, 100)  # Cap at 100 for safety
        
        start_time = time.time()
        
        logger.info(f"Finding elements with selector '{selector}' (type: {by})")
        if url:
            logger.info(f"Will navigate to URL first: {url}")
        
        try:
            # Get browser manager
            browser_manager = await get_browser_manager()
            if not browser_manager:
                return FindElementsOutput(
                    count=0,
                    elements=[],
                    url="",
                    status="error",
                    error="Browser manager not available"
                )
            
            # Get the WebDriver
            driver = await browser_manager.get_driver()
            
            # Navigate to URL if provided
            if url:
                # Validate URL security
                is_valid, error_msg = validate_url_security(url, allow_private=False)
                if not is_valid:
                    logger.warning(f"URL validation failed for {url}: {error_msg}")
                    return FindElementsOutput(
                        count=0,
                        elements=[],
                        url=url,
                        status="error",
                        error=f"URL validation failed: {error_msg}"
                    )
                
                # Navigate to the URL
                normalized_url = normalize_url(url)
                logger.debug(f"Navigating to: {normalized_url}")
                driver.get(normalized_url)
                
                # Wait for page to load
                await _wait_for_page_ready(driver)
            
            # Get current URL
            current_url = driver.current_url
            
            # Auto-detect selector type if not specified or invalid
            if by not in ["css", "xpath"]:
                by = detect_selector_type(selector)
                logger.debug(f"Auto-detected selector type: {by}")
            
            # Normalize selector
            try:
                normalized_selector, selenium_by = normalize_selector(selector, by)
            except ValueError as e:
                return FindElementsOutput(
                    count=0,
                    elements=[],
                    url=current_url,
                    status="error",
                    error=f"Invalid selector: {str(e)}"
                )
            
            # Find elements
            found_elements = []
            try:
                logger.debug(f"Searching with normalized selector: {normalized_selector}")
                selenium_elements = driver.find_elements(selenium_by, normalized_selector)
                
                logger.info(f"Found {len(selenium_elements)} elements")
                
                # Process elements
                processed_count = 0
                for element in selenium_elements:
                    if processed_count >= max_elements:
                        break
                    
                    try:
                        # Check visibility if requested
                        if visible_only and not is_visible_element(element):
                            continue
                        
                        # Extract element information
                        element_info = await _extract_element_info(element, current_url)
                        found_elements.append(element_info)
                        processed_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Error processing element: {e}")
                        continue
                
            except NoSuchElementException:
                logger.info("No elements found matching selector")
            except WebDriverException as e:
                logger.warning(f"WebDriver error finding elements: {e}")
                return FindElementsOutput(
                    count=0,
                    elements=[],
                    url=current_url,
                    status="error",
                    error=f"Search error: {str(e)}"
                )
            
            # Prepare metadata
            duration = time.time() - start_time
            metadata = {
                "duration_seconds": round(duration, 2),
                "selector_type": by,
                "normalized_selector": normalized_selector,
                "visible_only": visible_only,
                "max_requested": max_elements,
                "timestamp": time.time()
            }
            
            result = FindElementsOutput(
                count=len(found_elements),
                elements=found_elements,
                url=current_url,
                status="ok",
                metadata=metadata
            )
            
            logger.info(f"Found {len(found_elements)} elements in {duration:.2f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error finding elements: {error_msg}")
            
            return FindElementsOutput(
                count=0,
                elements=[],
                url=url or "",
                status="error",
                error=f"Unexpected error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )


async def _extract_element_info(element, base_url: str) -> ElementInfo:
    """
    Extract comprehensive information from a web element.
    
    Args:
        element: Selenium WebElement
        base_url: Base URL for resolving relative links
        
    Returns:
        ElementInfo with element details
    """
    # Extract text content
    text = extract_element_text(element)
    
    # Extract attributes
    attrs = extract_element_attributes(element, base_url)
    
    # Get outer HTML (truncated for safety)
    outer_html = get_element_outer_html(element, max_length=2000)
    
    # Get tag name
    tag_name = ""
    try:
        tag_name = element.tag_name.lower()
    except Exception as e:
        logger.warning(f"Could not get tag name: {e}")
    
    # Check if displayed
    is_displayed = False
    try:
        is_displayed = element.is_displayed()
    except Exception as e:
        logger.debug(f"Could not check element display status: {e}")
    
    return ElementInfo(
        text=text,
        attrs=attrs,
        outer_html=outer_html,
        tag_name=tag_name,
        is_displayed=is_displayed
    )


async def _wait_for_page_ready(driver, max_wait: int = 10) -> None:
    """
    Wait for page to be ready for element searching.
    
    Args:
        driver: Selenium WebDriver instance
        max_wait: Maximum seconds to wait
    """
    try:
        wait = WebDriverWait(driver, max_wait)
        # Wait for document ready state
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    except Exception as e:
        logger.debug(f"Page ready wait completed with exception: {e}")


# Additional utility functions
def _get_selector_info(selector: str, by: str) -> Dict[str, Any]:
    """Get information about a selector for debugging."""
    return {
        "original_selector": selector,
        "selector_type": by,
        "auto_detected_type": detect_selector_type(selector),
        "length": len(selector)
    }
