"""
Parsing utilities for MCP Browser Tools

Provides CSS/XPath selector normalization and parsing helper functions.
"""

import re
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag, NavigableString
from selenium.webdriver.common.by import By
from loguru import logger


def normalize_selector(selector: str, selector_type: str = "css") -> tuple[str, str]:
    """
    Normalize a CSS or XPath selector.
    
    Args:
        selector: The selector string to normalize
        selector_type: Type of selector ("css" or "xpath")
        
    Returns:
        Tuple of (normalized_selector, selenium_by_type)
    """
    if not selector or not isinstance(selector, str):
        raise ValueError("Selector must be a non-empty string")
    
    selector = selector.strip()
    selector_type = selector_type.lower()
    
    if selector_type == "xpath":
        # Normalize XPath
        if not selector.startswith(('/', '(', './/', './')):
            # Assume it's a relative XPath, make it absolute
            selector = f"//{selector}"
        return selector, By.XPATH
    
    elif selector_type == "css":
        # Normalize CSS selector
        # Remove extra whitespace
        selector = re.sub(r'\s+', ' ', selector)
        return selector, By.CSS_SELECTOR
    
    else:
        raise ValueError(f"Unknown selector type: {selector_type}")


def detect_selector_type(selector: str) -> str:
    """
    Auto-detect if a selector is CSS or XPath.
    
    Args:
        selector: Selector string to analyze
        
    Returns:
        "css" or "xpath"
    """
    if not selector:
        return "css"
    
    selector = selector.strip()
    
    # XPath indicators
    xpath_indicators = [
        selector.startswith('/'),           # /html/body
        selector.startswith('//'),          # //div
        selector.startswith('./'),          # ./div
        selector.startswith('('),           # (//div)[1]
        '@' in selector,                    # div[@class="test"]
        'text()' in selector,              # //div[text()="test"]
        'contains(' in selector,           # //div[contains(@class, "test")]
        'following-sibling::' in selector, # //div/following-sibling::span
        'parent::' in selector,            # //div/parent::*
        'ancestor::' in selector,          # //div/ancestor::body
    ]
    
    if any(xpath_indicators):
        return "xpath"
    
    return "css"


def extract_element_attributes(element, base_url: Optional[str] = None) -> Dict[str, str]:
    """
    Extract relevant attributes from a web element.
    
    Args:
        element: Selenium WebElement or BeautifulSoup Tag
        base_url: Base URL for resolving relative URLs
        
    Returns:
        Dictionary of element attributes
    """
    attrs = {}
    
    try:
        # Handle Selenium WebElement
        if hasattr(element, 'get_attribute'):
            # Common attributes to extract
            attr_names = [
                'id', 'class', 'name', 'value', 'href', 'src', 'alt', 'title',
                'placeholder', 'type', 'role', 'aria-label', 'aria-describedby',
                'data-testid', 'data-id', 'onclick', 'target'
            ]
            
            for attr_name in attr_names:
                attr_value = element.get_attribute(attr_name)
                if attr_value:
                    attrs[attr_name] = attr_value
        
        # Handle BeautifulSoup Tag
        elif isinstance(element, Tag):
            attrs = dict(element.attrs)
            
        # Resolve relative URLs if base_url provided
        if base_url:
            for attr_name in ['href', 'src']:
                if attr_name in attrs and attrs[attr_name]:
                    try:
                        attrs[attr_name] = urljoin(base_url, attrs[attr_name])
                    except Exception as e:
                        logger.warning(f"Failed to resolve URL for {attr_name}: {e}")
                        
    except Exception as e:
        logger.warning(f"Error extracting attributes: {e}")
    
    return attrs


def extract_element_text(element) -> str:
    """
    Extract text content from a web element.
    
    Args:
        element: Selenium WebElement or BeautifulSoup element
        
    Returns:
        Cleaned text content
    """
    try:
        # Handle Selenium WebElement
        if hasattr(element, 'text'):
            return element.text.strip()
        
        # Handle BeautifulSoup element
        elif hasattr(element, 'get_text'):
            return element.get_text(strip=True)
        
        # Handle string content
        elif isinstance(element, (str, NavigableString)):
            return str(element).strip()
            
    except Exception as e:
        logger.warning(f"Error extracting text: {e}")
    
    return ""


def get_element_outer_html(element, max_length: int = 1000) -> str:
    """
    Get the outer HTML of an element.
    
    Args:
        element: Selenium WebElement or BeautifulSoup element
        max_length: Maximum length of HTML to return
        
    Returns:
        Outer HTML string
    """
    try:
        # Handle Selenium WebElement
        if hasattr(element, 'get_attribute'):
            outer_html = element.get_attribute('outerHTML')
            if outer_html:
                if len(outer_html) > max_length:
                    outer_html = outer_html[:max_length] + "..."
                return outer_html
        
        # Handle BeautifulSoup element
        elif isinstance(element, Tag):
            outer_html = str(element)
            if len(outer_html) > max_length:
                outer_html = outer_html[:max_length] + "..."
            return outer_html
            
    except Exception as e:
        logger.warning(f"Error getting outer HTML: {e}")
    
    return ""


def parse_html_with_soup(html: str, base_url: Optional[str] = None) -> BeautifulSoup:
    """
    Parse HTML content with BeautifulSoup using optimal parser.
    
    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        BeautifulSoup object
    """
    try:
        # Use lxml parser if available, fall back to html.parser
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            # Return empty soup as fallback
            soup = BeautifulSoup("", 'html.parser')
    
    # Resolve relative URLs if base_url provided
    if base_url:
        try:
            resolve_relative_urls(soup, base_url)
        except Exception as e:
            logger.warning(f"Failed to resolve relative URLs: {e}")
    
    return soup


def resolve_relative_urls(soup: BeautifulSoup, base_url: str) -> None:
    """
    Resolve relative URLs in a BeautifulSoup document.
    
    Args:
        soup: BeautifulSoup document to modify
        base_url: Base URL for resolution
    """
    # Resolve href attributes
    for element in soup.find_all(attrs={'href': True}):
        try:
            element['href'] = urljoin(base_url, element['href'])
        except Exception:
            pass
    
    # Resolve src attributes
    for element in soup.find_all(attrs={'src': True}):
        try:
            element['src'] = urljoin(base_url, element['src'])
        except Exception:
            pass


def extract_links(soup: BeautifulSoup, filter_extensions: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    Extract all links from a BeautifulSoup document.
    
    Args:
        soup: BeautifulSoup document
        filter_extensions: List of file extensions to filter for (e.g., ['.pdf', '.doc'])
        
    Returns:
        List of link dictionaries with 'url', 'text', and 'title' keys
    """
    links = []
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = extract_element_text(link)
        title = link.get('title', '')
        
        # Apply extension filter if specified
        if filter_extensions:
            href_lower = href.lower()
            if not any(href_lower.endswith(ext.lower()) for ext in filter_extensions):
                continue
        
        links.append({
            'url': href,
            'text': text,
            'title': title
        })
    
    return links


def clean_text_content(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text content
        
    Returns:
        Cleaned text content
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common unwanted characters
    text = text.strip()
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    truncate_at = max_length - len(suffix)
    if truncate_at <= 0:
        return suffix[:max_length]
    
    return text[:truncate_at] + suffix


def is_visible_element(element) -> bool:
    """
    Check if an element is likely visible (basic heuristics).
    
    Args:
        element: Selenium WebElement
        
    Returns:
        True if element appears visible
    """
    try:
        # For Selenium WebElements
        if hasattr(element, 'is_displayed'):
            return element.is_displayed()
        
        # For BeautifulSoup elements, check basic visibility indicators
        elif isinstance(element, Tag):
            style = element.get('style', '').lower()
            if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
                return False
            
            # Check for hidden class (common pattern)
            classes = element.get('class', [])
            if isinstance(classes, list):
                hidden_classes = {'hidden', 'invisible', 'hide', 'd-none'}
                if any(cls.lower() in hidden_classes for cls in classes):
                    return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Error checking element visibility: {e}")
        return True  # Assume visible if we can't determine