"""
Interaction tools for MCP Browser Tools

Provides click_element and run_js_interaction tools for browser interaction.
"""

import asyncio
import time
import json
from typing import Callable, Dict, List, Any, Optional, Union, Annotated

from pydantic import BaseModel, Field
from selenium.common.exceptions import (
    WebDriverException, NoSuchElementException, ElementClickInterceptedException,
    TimeoutException, ElementNotInteractableException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from loguru import logger

from navmcp.utils.net import validate_url_security, normalize_url
from navmcp.utils.parsing import (
    normalize_selector, detect_selector_type, extract_element_text,
    get_element_outer_html
)


class ClickElementInput(BaseModel):
    """Input schema for click_element tool."""
    selector: str = Field(
        description="CSS selector or XPath expression for the element to click",
        examples=[
            "button.submit", 
            "#login-button", 
            "a[href='/signup']", 
            "//button[text()='Continue']",
            "input[type='submit']"
        ],
        min_length=1,
        max_length=512
    )
    by: str = Field(
        default="css", 
        description="Selector type to use for finding the element to click",
        examples=["css", "xpath"],
        pattern="^(css|xpath)$"
    )
    url: Optional[str] = Field(
        None, 
        description="Optional URL to navigate to before clicking the element",
        examples=["https://www.example.com/login", "https://app.example.com/dashboard"],
        max_length=2048
    )
    wait_for: Optional[str] = Field(
        None, 
        description="Optional CSS selector or XPath to wait for after clicking (useful for dynamic content)",
        examples=[".success-message", "#modal-dialog", "//div[@class='loading']"],
        max_length=512
    )
    timeout_s: Optional[int] = Field(
        10, 
        description="Maximum time in seconds to wait for operations (navigation, element finding, post-click waits)",
        ge=1,
        le=60,
        examples=[5, 10, 30]
    )


class RunJsInteractionInput(BaseModel):
    """Input schema for run_js_interaction tool."""
    script: str = Field(
        description="JavaScript code to execute in the browser context (should return JSON-serializable values)",
        examples=[
            "return document.title;",
            "return window.location.href;",
            "return document.querySelectorAll('a').length;",
            "document.getElementById('username').value = arguments[0]; return 'success';",
            "return Array.from(document.querySelectorAll('h2')).map(h => h.textContent);"
        ],
        min_length=1,
        max_length=8192
    )
    args: List[Any] = Field(
        default_factory=list, 
        description="Arguments to pass to the JavaScript script (accessible as arguments[0], arguments[1], etc.)",
        examples=[["username123"], [42, "test"], [{"key": "value"}]],
        max_length=10
    )
    url: Optional[str] = Field(
        None, 
        description="Optional URL to navigate to before executing the JavaScript",
        examples=["https://www.example.com", "https://app.example.com/page"],
        max_length=2048
    )
    timeout_s: Optional[int] = Field(
        30, 
        description="Maximum time in seconds to wait for script execution to complete",
        ge=1,
        le=120,
        examples=[10, 30, 60]
    )


class ClickElementOutput(BaseModel):
    """Output schema for click_element tool."""
    url: str = Field(description="Current page URL after click")
    html: str = Field(description="Updated page HTML")
    title: str = Field(description="Page title after click")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RunJsInteractionOutput(BaseModel):
    """Output schema for run_js_interaction tool."""
    result: Any = Field(description="Result returned by the JavaScript")
    logs: Optional[List[str]] = Field(None, description="Console logs captured during execution")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def setup_interact_tools(mcp, get_browser_manager: Callable):
    """Setup interaction-related MCP tools."""
    
    @mcp.tool()
    async def click_element(
        selector: Annotated[str, Field(
            description="CSS selector or XPath expression for the element to click",
            examples=[
                "button.submit", 
                "#login-button", 
                "a[href='/signup']", 
                "//button[text()='Continue']",
                "input[type='submit']"
            ],
            min_length=1,
            max_length=512
        )],
        by: Annotated[str, Field(
            description="Selector type to use for finding the element to click",
            examples=["css", "xpath"],
            pattern="^(css|xpath)$"
        )] = "css",
        url: Annotated[Optional[str], Field(
            description="Optional URL to navigate to before clicking the element",
            examples=["https://www.example.com/login", "https://app.example.com/dashboard"],
            max_length=2048
        )] = None,
        wait_for: Annotated[Optional[str], Field(
            description="Optional CSS selector or XPath to wait for after clicking (useful for dynamic content)",
            examples=[".success-message", "#modal-dialog", "//div[@class='loading']"],
            max_length=512
        )] = None,
        timeout_s: Annotated[int, Field(
            description="Maximum time in seconds to wait for operations (navigation, element finding, post-click waits)",
            ge=1,
            le=60,
            examples=[5, 10, 30]
        )] = 10
    ) -> ClickElementOutput:
        """
        Click an element on a web page using CSS selectors or XPath.
        
        This tool finds a specific element on the current page or after navigating to a URL,
        then performs a click action on it. It handles various click scenarios including buttons,
        links, form elements, and interactive components. Can wait for post-click changes.
        
        Key features:
        - Supports both CSS selectors and XPath expressions
        - Auto-detects selector type if not specified
        - Handles JavaScript-triggered interactions
        - Can wait for elements to appear after clicking
        - Provides updated page content after interaction
        - Includes comprehensive error handling
        
        Common click targets:
        - Buttons: "button.submit", "#save-btn", "//button[text()='Submit']"
        - Links: "a[href='/login']", ".nav-link", "//a[contains(text(), 'Sign up')]"
        - Form elements: "input[type='submit']", ".checkbox", "//input[@value='Continue']"
        - Interactive elements: ".dropdown-toggle", "#menu-icon", "//div[@role='button']"
        
        Use cases:
        - Submitting forms and triggering actions
        - Navigating through multi-page workflows
        - Interacting with dynamic UI components
        - Testing user interface functionality
        - Automating repetitive clicking tasks
        
        Example usage:
        - input: {"selector": "#login-button"} - Click login button on current page
        - input: {"selector": "a.signup", "url": "https://example.com"} - Navigate then click signup link
        - input: {"selector": "button.submit", "wait_for": ".success-message"} - Click and wait for success
        
        Args:
            selector: CSS selector or XPath expression for element to click
            by: Selector type ('css' or 'xpath')
            url: Optional URL to navigate to first
            wait_for: Optional selector to wait for after clicking
            timeout_s: Maximum time to wait for operations
            
        Returns:
            ClickElementOutput with updated page state and metadata
        """
        selector = selector.strip()
        by = by.lower()
        url = url.strip() if url else None
        wait_for = wait_for.strip() if wait_for else None
        timeout_s = timeout_s or 10
        
        start_time = time.time()
        
        logger.info(f"Clicking element with selector '{selector}' (type: {by})")
        if url:
            logger.info(f"Will navigate to URL first: {url}")
        if wait_for:
            logger.info(f"Will wait for element: {wait_for}")
        
        try:
            # Get browser manager
            browser_manager = await get_browser_manager()
            if not browser_manager:
                return ClickElementOutput(
                    url="",
                    html="",
                    title="",
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
                    return ClickElementOutput(
                        url=url,
                        html="",
                        title="",
                        status="error",
                        error=f"URL validation failed: {error_msg}"
                    )
                
                # Navigate to the URL
                normalized_url = normalize_url(url)
                logger.debug(f"Navigating to: {normalized_url}")
                driver.get(normalized_url)
                
                # Wait for page to load
                await _wait_for_page_ready(driver)
            
            # Auto-detect selector type if not specified or invalid
            if by not in ["css", "xpath"]:
                by = detect_selector_type(selector)
                logger.debug(f"Auto-detected selector type: {by}")
            
            # Normalize selector
            try:
                normalized_selector, selenium_by = normalize_selector(selector, by)
            except ValueError as e:
                current_url = driver.current_url
                return ClickElementOutput(
                    url=current_url,
                    html="",
                    title="",
                    status="error",
                    error=f"Invalid selector: {str(e)}"
                )
            
            # Find and click the element
            try:
                # Wait for element to be clickable
                wait = WebDriverWait(driver, timeout_s)
                element = wait.until(EC.element_to_be_clickable((selenium_by, normalized_selector)))
                
                logger.debug(f"Found clickable element: {get_element_outer_html(element, 200)}")
                
                # Try to click the element with different strategies
                click_success = await _click_element_safely(driver, element)
                
                if not click_success:
                    current_url = driver.current_url
                    return ClickElementOutput(
                        url=current_url,
                        html="",
                        title="",
                        status="error",
                        error="Failed to click element after multiple attempts"
                    )
                
                logger.info("Element clicked successfully")
                
                # Wait for any specified element after click
                if wait_for:
                    try:
                        wait_selector_type = detect_selector_type(wait_for)
                        wait_normalized, wait_selenium_by = normalize_selector(wait_for, wait_selector_type)
                        
                        logger.debug(f"Waiting for element: {wait_normalized}")
                        wait.until(EC.presence_of_element_located((wait_selenium_by, wait_normalized)))
                        logger.info("Wait condition satisfied")
                        
                    except TimeoutException:
                        logger.warning(f"Timeout waiting for element: {wait_for}")
                    except Exception as e:
                        logger.warning(f"Error in wait condition: {e}")
                
                # Small delay for any JavaScript effects
                await asyncio.sleep(0.5)
                
            except TimeoutException:
                current_url = driver.current_url
                return ClickElementOutput(
                    url=current_url,
                    html="",
                    title="",
                    status="error",
                    error=f"Timeout waiting for clickable element: {selector}"
                )
            except NoSuchElementException:
                current_url = driver.current_url
                return ClickElementOutput(
                    url=current_url,
                    html="",
                    title="",
                    status="error",
                    error=f"Element not found: {selector}"
                )
            except WebDriverException as e:
                current_url = driver.current_url
                return ClickElementOutput(
                    url=current_url,
                    html="",
                    title="",
                    status="error",
                    error=f"Click error: {str(e)}"
                )
            
            # Get updated page state
            current_url = driver.current_url
            title = driver.title or ""
            html = driver.page_source or ""
            
            # Prepare metadata
            duration = time.time() - start_time
            metadata = {
                "duration_seconds": round(duration, 2),
                "selector_type": by,
                "normalized_selector": normalized_selector,
                "had_wait_condition": bool(wait_for),
                "timestamp": time.time()
            }
            
            result = ClickElementOutput(
                url=current_url,
                html=html,
                title=title,
                status="ok",
                metadata=metadata
            )
            
            logger.info(f"Click completed in {duration:.2f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error clicking element: {error_msg}")
            
            return ClickElementOutput(
                url=url or "",
                html="",
                title="",
                status="error",
                error=f"Unexpected error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )
    
    @mcp.tool()
    async def run_js_interaction(
        script: Annotated[str, Field(
            description="JavaScript code to execute in the browser context (should return JSON-serializable values)",
            examples=[
                "return document.title;",
                "return window.location.href;",
                "return document.querySelectorAll('a').length;",
                "document.getElementById('username').value = arguments[0]; return 'success';",
                "return Array.from(document.querySelectorAll('h2')).map(h => h.textContent);"
            ],
            min_length=1,
            max_length=8192
        )],
        args: Annotated[List[Any], Field(
            description="Arguments to pass to the JavaScript script (accessible as arguments[0], arguments[1], etc.)",
            examples=[["username123"], [42, "test"], [{"key": "value"}]],
            max_length=10
        )] = None,
        url: Annotated[Optional[str], Field(
            description="Optional URL to navigate to before executing the JavaScript",
            examples=["https://www.example.com", "https://app.example.com/page"],
            max_length=2048
        )] = None,
        timeout_s: Annotated[int, Field(
            description="Maximum time in seconds to wait for script execution to complete",
            ge=1,
            le=120,
            examples=[10, 30, 60]
        )] = 30
    ) -> RunJsInteractionOutput:
        """
        Execute custom JavaScript code in the browser context with full DOM access.
        
        This powerful tool runs arbitrary JavaScript code within the current page context,
        providing full access to the DOM, window object, and all page resources. It can
        read data, modify content, trigger events, and perform complex interactions that
        go beyond simple clicking or form filling.
        
        Key features:
        - Full JavaScript execution environment
        - Access to DOM, window, and page objects
        - Support for arguments passing
        - JSON-serializable return values
        - Configurable execution timeout
        - Comprehensive error handling
        
        Common JavaScript patterns:
        - Data extraction: "return document.querySelectorAll('a').length"
        - Content modification: "document.getElementById('field').value = arguments[0]"
        - Event triggering: "document.querySelector('button').click()"
        - Information gathering: "return {title: document.title, url: location.href}"
        - Complex queries: "return Array.from(document.querySelectorAll('h2')).map(h => h.textContent)"
        
        Use cases:
        - Extracting complex data not accessible via simple selectors
        - Filling forms with dynamic validation
        - Triggering JavaScript events and interactions
        - Gathering detailed page information and metrics
        - Performing multi-step operations in a single execution
        - Interacting with single-page applications (SPAs)
        
        Example usage:
        - input: {"script": "return document.title"} - Get page title
        - input: {"script": "document.getElementById('username').value = arguments[0]; return 'set'", "args": ["john123"]} - Set form field
        - input: {"script": "return window.getComputedStyle(document.body).backgroundColor"} - Get CSS properties
        
        Security note: This tool executes arbitrary JavaScript - use with trusted code only.
        
        Args:
            script: JavaScript code to execute in browser context
            args: Arguments to pass to the script (optional)
            url: Optional URL to navigate to first
            timeout_s: Maximum time to wait for script execution
            
        Returns:
            RunJsInteractionOutput with execution result and metadata
        """
        script = script.strip()
        args = args or []
        url = url.strip() if url else None
        timeout_s = timeout_s or 30
        
        start_time = time.time()
        
        logger.info(f"Executing JavaScript (length: {len(script)} chars)")
        if url:
            logger.info(f"Will navigate to URL first: {url}")
        
        try:
            # Get browser manager
            browser_manager = await get_browser_manager()
            if not browser_manager:
                return RunJsInteractionOutput(
                    result=None,
                    status="error",
                    error="Browser manager not available"
                )
            
            # Get the WebDriver
            driver = await browser_manager.get_driver()
            
            # Set script timeout
            driver.set_script_timeout(timeout_s)
            
            # Navigate to URL if provided
            if url:
                # Validate URL security
                is_valid, error_msg = validate_url_security(url, allow_private=False)
                if not is_valid:
                    logger.warning(f"URL validation failed for {url}: {error_msg}")
                    return RunJsInteractionOutput(
                        result=None,
                        status="error",
                        error=f"URL validation failed: {error_msg}"
                    )
                
                # Navigate to the URL
                normalized_url = normalize_url(url)
                logger.debug(f"Navigating to: {normalized_url}")
                driver.get(normalized_url)
                
                # Wait for page to load
                await _wait_for_page_ready(driver)
            
            # Execute the JavaScript
            try:
                logger.debug(f"Executing script with {len(args)} arguments")
                
                # Execute the script
                if args:
                    result = driver.execute_script(script, *args)
                else:
                    result = driver.execute_script(script)
                
                logger.info("JavaScript executed successfully")
                
                # Try to make result JSON-serializable
                serializable_result = _make_json_serializable(result)
                
            except WebDriverException as e:
                error_msg = str(e)
                logger.warning(f"JavaScript execution error: {error_msg}")
                
                return RunJsInteractionOutput(
                    result=None,
                    status="error",
                    error=f"Script execution error: {error_msg}"
                )
            
            # Prepare metadata
            duration = time.time() - start_time
            metadata = {
                "duration_seconds": round(duration, 2),
                "script_length": len(script),
                "args_count": len(args),
                "result_type": type(serializable_result).__name__,
                "timestamp": time.time()
            }
            
            result_output = RunJsInteractionOutput(
                result=serializable_result,
                status="ok",
                metadata=metadata
            )
            
            logger.info(f"JavaScript execution completed in {duration:.2f}s")
            return result_output
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error executing JavaScript: {error_msg}")
            
            return RunJsInteractionOutput(
                result=None,
                status="error",
                error=f"Unexpected error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )


async def _click_element_safely(driver, element) -> bool:
    """
    Try to click an element using multiple strategies.
    
    Args:
        driver: Selenium WebDriver instance
        element: Element to click
        
    Returns:
        True if click was successful
    """
    strategies = [
        # Strategy 1: Simple click
        lambda: element.click(),
        
        # Strategy 2: JavaScript click
        lambda: driver.execute_script("arguments[0].click();", element),
        
        # Strategy 3: Action chains click
        lambda: ActionChains(driver).click(element).perform(),
        
        # Strategy 4: Scroll into view then click
        lambda: _scroll_and_click(driver, element)
    ]
    
    for i, strategy in enumerate(strategies, 1):
        try:
            logger.debug(f"Attempting click strategy {i}")
            strategy()
            return True
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            logger.debug(f"Click strategy {i} failed: {e}")
            if i < len(strategies):
                await asyncio.sleep(0.2)  # Brief pause between attempts
            continue
        except Exception as e:
            logger.warning(f"Click strategy {i} failed with unexpected error: {e}")
            continue
    
    return False


def _scroll_and_click(driver, element):
    """Scroll element into view and click it."""
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
    time.sleep(0.3)  # Wait for scroll
    element.click()


async def _wait_for_page_ready(driver, max_wait: int = 10) -> None:
    """Wait for page to be ready for interaction."""
    try:
        wait = WebDriverWait(driver, max_wait)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    except Exception as e:
        logger.debug(f"Page ready wait completed with exception: {e}")


def _make_json_serializable(obj) -> Any:
    """
    Convert an object to be JSON-serializable.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    else:
        # For other types, try to convert to string
        try:
            return str(obj)
        except Exception:
            return f"<{type(obj).__name__} object>"
