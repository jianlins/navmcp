"""
Search tools for MCP Browser Tools

Provides the web_search tool for performing web searches.
"""

import time
import re
from typing import Callable, Dict, List, Any, Optional, Annotated
from urllib.parse import quote_plus, urljoin

from pydantic import BaseModel, Field
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from loguru import logger

from server.utils.parsing import (
    parse_html_with_soup, extract_element_text, clean_text_content, truncate_text
)


class WebSearchInput(BaseModel):
    """Input schema for web_search tool."""
    query: str = Field(
        description="Search query string to find relevant web pages",
        examples=[
            "Python web scraping tutorial",
            "machine learning best practices",
            "JavaScript async await examples",
            "React component lifecycle",
            "how to install Docker"
        ],
        min_length=1,
        max_length=512
    )
    engine: str = Field(
        default="google_scholar", 
        description="Search engine to use for the web search",
        examples=["google_scholar", "pubmed", "ieee", "arxiv", "medrxiv", "biorxiv"],
        pattern="^(google_scholar|pubmed|ieee|arxiv|medrxiv|biorxiv)$"
    )
    num_results: int = Field(
        default=10, 
        description="Maximum number of search results to return (capped at 20 for performance)",
        ge=1,
        le=20,
        examples=[5, 10, 15, 20]
    )


class SearchResult(BaseModel):
    """Information about a single search result."""
    title: str = Field(description="Result title")
    url: str = Field(description="Result URL")
    snippet: str = Field(description="Result snippet/description")


class WebSearchOutput(BaseModel):
    """Output schema for web_search tool."""
    results: List[SearchResult] = Field(description="List of search results")
    query: str = Field(description="Original search query")
    engine: str = Field(description="Search engine used")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def setup_search_tools(mcp, get_browser_manager: Callable):
    """Setup search-related MCP tools."""
    
    @mcp.tool()
    async def web_search(input_data: WebSearchInput) -> WebSearchOutput:
        """
        Perform comprehensive web searches and return structured results with titles, URLs, and snippets.
        
        This powerful tool performs web searches using privacy-focused search engines to find relevant
        web pages, articles, documentation, and resources. It returns clean, structured results that
        are perfect for research, fact-checking, and information gathering tasks.
        
        Key features:
        - Academic and specialized search engines (Google Scholar, PubMed, IEEE, arXiv, medRxiv, bioRxiv)
        - Clean, structured result format with titles, URLs, and descriptions
        - Configurable number of results (up to 20)
        - Intelligent result parsing and cleaning
        - Fast execution with comprehensive error handling
        - Rich metadata about search performance
        
        Search capabilities:
        - General web search for any topic or question
        - Technical documentation and tutorials
        - News and current events
        - Academic and research content
        - Product information and reviews
        - Troubleshooting and how-to guides
        
        Use cases:
        - Research and fact-checking for content creation
        - Finding relevant documentation and tutorials
        - Discovering tools and resources for projects
        - Gathering information for decision making
        - Competitive analysis and market research
        - Academic research and literature reviews
        
        Example usage:
        - input: {"query": "Python web scraping tutorial"} - Find programming tutorials
        - input: {"query": "best practices machine learning", "num_results": 5} - Research best practices
        - input: {"query": "React component lifecycle methods", "num_results": 15} - Technical documentation
        
        Args:
            input_data: WebSearchInput with search query and result preferences
            
        Returns:
            WebSearchOutput with structured search results and metadata
        """
        query = input_data.query.strip()
        engine = input_data.engine.lower()
        num_results = min(input_data.num_results, 20)  # Cap at 20 for safety
        
        start_time = time.time()
        
        logger.info(f"Searching for '{query}' using {engine} (max {num_results} results)")
        
        if not query:
            return WebSearchOutput(
                results=[],
                query=query,
                engine=engine,
                status="error",
                error="Search query cannot be empty"
            )
        
        try:
            # Get browser manager
            browser_manager = get_browser_manager()
            if not browser_manager:
                return WebSearchOutput(
                    results=[],
                    query=query,
                    engine=engine,
                    status="error",
                    error="Browser manager not available"
                )
            
            # Perform search based on engine
            if engine == "google_scholar":
                results = await _search_google_scholar(browser_manager, query, num_results)
            elif engine == "pubmed":
                results = await _search_pubmed(browser_manager, query, num_results)
            elif engine == "ieee":
                results = await _search_ieee(browser_manager, query, num_results)
            elif engine == "arxiv":
                results = await _search_arxiv(browser_manager, query, num_results)
            elif engine == "medrxiv":
                results = await _search_medrxiv(browser_manager, query, num_results)
            elif engine == "biorxiv":
                results = await _search_biorxiv(browser_manager, query, num_results)
            else:
                return WebSearchOutput(
                    results=[],
                    query=query,
                    engine=engine,
                    status="error",
                    error=f"Unsupported search engine: {engine}"
                )
            
            # Prepare metadata
            duration = time.time() - start_time
            metadata = {
                "duration_seconds": round(duration, 2),
                "results_requested": num_results,
                "results_found": len(results),
                "timestamp": time.time()
            }
            
            output = WebSearchOutput(
                results=results,
                query=query,
                engine=engine,
                status="ok",
                metadata=metadata
            )
            
            logger.info(f"Search completed: found {len(results)} results in {duration:.2f}s")
            return output
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error during search: {error_msg}")
            
            return WebSearchOutput(
                results=[],
                query=query,
                engine=engine,
                status="error",
                error=f"Search error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )




async def _search_google_scholar(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using Google Scholar.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build Google Scholar search URL
        encoded_query = quote_plus(query)
        search_url = f"https://scholar.google.com/scholar?q={encoded_query}&hl=en&as_sdt=0,5"
        
        logger.debug(f"Navigating to Google Scholar: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load
        await _wait_for_search_results(driver)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_google_scholar_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from Google Scholar")
        
    except Exception as e:
        logger.error(f"Error searching Google Scholar: {e}")
    
    return results


async def _search_pubmed(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using PubMed.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build PubMed search URL
        encoded_query = quote_plus(query)
        search_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}&size={min(num_results, 20)}"
        
        logger.debug(f"Navigating to PubMed: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load
        await _wait_for_search_results(driver)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_pubmed_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from PubMed")
        
    except Exception as e:
        logger.error(f"Error searching PubMed: {e}")
    
    return results


async def _search_ieee(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using IEEE Xplore.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build IEEE search URL
        encoded_query = quote_plus(query)
        search_url = f"https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={encoded_query}"
        
        logger.debug(f"Navigating to IEEE Xplore: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load (IEEE may need more time for JS)
        await _wait_for_search_results(driver, max_wait=20)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_ieee_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from IEEE Xplore")
        
    except Exception as e:
        logger.error(f"Error searching IEEE Xplore: {e}")
    
    return results


async def _search_arxiv(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using arXiv.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build arXiv search URL
        encoded_query = quote_plus(query)
        search_url = f"https://arxiv.org/search/?query={encoded_query}&searchtype=all&abstracts=show&order=-announced_date_first&size={min(num_results, 25)}"
        
        logger.debug(f"Navigating to arXiv: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load
        await _wait_for_search_results(driver)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_arxiv_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from arXiv")
        
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
    
    return results


async def _search_medrxiv(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using medRxiv.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build medRxiv search URL
        encoded_query = quote_plus(query)
        search_url = f"https://www.medrxiv.org/search/{encoded_query}"
        
        logger.debug(f"Navigating to medRxiv: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load
        await _wait_for_search_results(driver)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_medrxiv_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from medRxiv")
        
    except Exception as e:
        logger.error(f"Error searching medRxiv: {e}")
    
    return results


async def _search_biorxiv(browser_manager, query: str, num_results: int) -> List[SearchResult]:
    """
    Perform a search using bioRxiv.
    
    Args:
        browser_manager: Browser manager instance
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        # Get the WebDriver
        driver = await browser_manager.get_driver()
        
        # Build bioRxiv search URL
        encoded_query = quote_plus(query)
        search_url = f"https://www.biorxiv.org/search/{encoded_query}"
        
        logger.debug(f"Navigating to bioRxiv: {search_url}")
        
        # Navigate to search results
        driver.get(search_url)
        
        # Wait for results to load
        await _wait_for_search_results(driver)
        
        # Get page HTML
        html = driver.page_source
        
        # Parse results
        results = _parse_biorxiv_results(html, num_results)
        
        logger.info(f"Extracted {len(results)} results from bioRxiv")
        
    except Exception as e:
        logger.error(f"Error searching bioRxiv: {e}")
    
    return results




def _parse_google_scholar_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse Google Scholar search results from HTML.
    
    Args:
        html: HTML content from Google Scholar results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # Google Scholar result selectors
        result_selectors = [
            '.gs_r.gs_or.gs_scl',  # Main result container
            '.gs_ri',  # Alternative result container
            '[data-lid]'  # Generic result with data-lid attribute
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found Google Scholar results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No Google Scholar result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_google_scholar_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting Google Scholar result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} Google Scholar results")
        
    except Exception as e:
        logger.error(f"Error parsing Google Scholar results: {e}")
    
    return results


def _parse_pubmed_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse PubMed search results from HTML.
    
    Args:
        html: HTML content from PubMed results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # PubMed result selectors
        result_selectors = [
            'article.full-docsum',  # Main result container
            '.docsum-wrap',  # Alternative container
            '.docsum-content'  # Generic docsum
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found PubMed results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No PubMed result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_pubmed_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting PubMed result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} PubMed results")
        
    except Exception as e:
        logger.error(f"Error parsing PubMed results: {e}")
    
    return results


def _parse_ieee_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse IEEE Xplore search results from HTML.
    
    Args:
        html: HTML content from IEEE results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # IEEE result selectors
        result_selectors = [
            '.List-results-items',  # Main result container
            '.result-item',  # Alternative container
            '.document'  # Generic document
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found IEEE results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No IEEE result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_ieee_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting IEEE result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} IEEE results")
        
    except Exception as e:
        logger.error(f"Error parsing IEEE results: {e}")
    
    return results


def _parse_arxiv_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse arXiv search results from HTML.
    
    Args:
        html: HTML content from arXiv results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # arXiv result selectors
        result_selectors = [
            'li.arxiv-result',  # Main result container
            '.list-item',  # Alternative container
            'ol li'  # Generic list item
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found arXiv results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No arXiv result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_arxiv_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting arXiv result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} arXiv results")
        
    except Exception as e:
        logger.error(f"Error parsing arXiv results: {e}")
    
    return results


def _parse_medrxiv_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse medRxiv search results from HTML.
    
    Args:
        html: HTML content from medRxiv results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # medRxiv result selectors
        result_selectors = [
            '.highwire-cite',  # Main result container
            '.search-result',  # Alternative container
            '.result-item'  # Generic result
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found medRxiv results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No medRxiv result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_medrxiv_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting medRxiv result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} medRxiv results")
        
    except Exception as e:
        logger.error(f"Error parsing medRxiv results: {e}")
    
    return results


def _parse_biorxiv_results(html: str, max_results: int) -> List[SearchResult]:
    """
    Parse bioRxiv search results from HTML.
    
    Args:
        html: HTML content from bioRxiv results page
        max_results: Maximum number of results to extract
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    try:
        soup = parse_html_with_soup(html)
        
        # bioRxiv result selectors (similar to medRxiv)
        result_selectors = [
            '.highwire-cite',  # Main result container
            '.search-result',  # Alternative container
            '.result-item'  # Generic result
        ]
        
        # Try different selectors to find results
        result_elements = []
        for selector in result_selectors:
            result_elements = soup.select(selector)
            if result_elements:
                logger.debug(f"Found bioRxiv results using selector: {selector}")
                break
        
        if not result_elements:
            logger.warning("No bioRxiv result elements found")
            return results
        
        # Extract information from each result
        for i, element in enumerate(result_elements[:max_results]):
            try:
                result = _extract_biorxiv_result(element)
                if result:
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error extracting bioRxiv result {i}: {e}")
                continue
        
        logger.debug(f"Successfully extracted {len(results)} bioRxiv results")
        
    except Exception as e:
        logger.error(f"Error parsing bioRxiv results: {e}")
    
    return results




def _extract_google_scholar_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from a Google Scholar result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            'h3.gs_rt a',
            '.gs_rt a',
            'h3 a',
            '.gs_rt'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from Google Scholar result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors[:2]:  # Only check link selectors
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from Google Scholar result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://scholar.google.com', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.gs_rs',
            '.gs_a + div',
            '.gs_fl + div'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual Google Scholar result: {e}")
        return None


def _extract_pubmed_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from a PubMed result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            '.docsum-title a',
            'h1 a',
            '.title a'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from PubMed result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors:
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from PubMed result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://pubmed.ncbi.nlm.nih.gov', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.full-view-snippet',
            '.docsum-snippet',
            '.abstract'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual PubMed result: {e}")
        return None


def _extract_ieee_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from an IEEE result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            '.result-item-title a',
            'h2 a',
            '.title a'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from IEEE result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors:
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from IEEE result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://ieeexplore.ieee.org', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.description',
            '.abstract',
            '.snippet'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual IEEE result: {e}")
        return None


def _extract_arxiv_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from an arXiv result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            '.list-title a',
            'p.title a',
            '.title a'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from arXiv result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors:
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from arXiv result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://arxiv.org', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.list-abstract',
            'p.abstract',
            '.abstract'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual arXiv result: {e}")
        return None


def _extract_medrxiv_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from a medRxiv result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            '.highwire-cite-title a',
            '.citation-title a',
            '.title a'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from medRxiv result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors:
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from medRxiv result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://www.medrxiv.org', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.highwire-cite-snippet',
            '.citation-snippet',
            '.abstract'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual medRxiv result: {e}")
        return None


def _extract_biorxiv_result(element) -> Optional[SearchResult]:
    """
    Extract search result information from a bioRxiv result element.
    
    Args:
        element: BeautifulSoup element containing the result
        
    Returns:
        SearchResult object or None if extraction fails
    """
    try:
        # Extract title
        title = ""
        title_selectors = [
            '.highwire-cite-title a',
            '.citation-title a',
            '.title a'
        ]
        
        for selector in title_selectors:
            title_element = element.select_one(selector)
            if title_element:
                title = extract_element_text(title_element)
                break
        
        if not title:
            logger.debug("Could not extract title from bioRxiv result")
            return None
        
        # Extract URL
        url = ""
        for selector in title_selectors:
            url_element = element.select_one(selector)
            if url_element and url_element.get('href'):
                url = url_element['href']
                break
        
        if not url:
            logger.debug("Could not extract URL from bioRxiv result")
            return None
        
        # Clean up URL if it's a relative URL
        if url.startswith('/'):
            url = urljoin('https://www.biorxiv.org', url)
        
        # Extract snippet (abstract)
        snippet = ""
        snippet_selectors = [
            '.highwire-cite-snippet',
            '.citation-snippet',
            '.abstract'
        ]
        
        for selector in snippet_selectors:
            snippet_element = element.select_one(selector)
            if snippet_element:
                snippet = extract_element_text(snippet_element)
                break
        
        # Clean and truncate text
        title = clean_text_content(title)
        snippet = clean_text_content(snippet)
        snippet = truncate_text(snippet, max_length=300)
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet
        )
        
    except Exception as e:
        logger.warning(f"Error extracting individual bioRxiv result: {e}")
        return None




async def _wait_for_search_results(driver, max_wait: int = 15) -> None:
    """
    Wait for search results to load.
    
    Args:
        driver: Selenium WebDriver instance
        max_wait: Maximum seconds to wait
    """
    try:
        wait = WebDriverWait(driver, max_wait)
        
        # Wait for page to be ready
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        
        # Try to wait for specific result elements to appear
        result_indicators = [
            'article[data-testid="result"]',
            '.result',
            '[data-testid="result"]'
        ]
        
        # Wait for at least one result indicator (but don't fail if none found)
        for selector in result_indicators:
            try:
                elements = driver.find_elements("css selector", selector)
                if elements:
                    logger.debug(f"Found {len(elements)} result elements with selector: {selector}")
                    break
            except Exception:
                continue
        
        # Small additional wait for dynamic content
        import asyncio
        await asyncio.sleep(1)
        
    except TimeoutException:
        logger.warning(f"Timeout waiting for search results ({max_wait}s)")
    except Exception as e:
        logger.debug(f"Error waiting for search results: {e}")


# Utility function for testing/debugging
def _get_search_page_info(driver) -> Dict[str, Any]:
    """Get information about the search results page for debugging."""
    info = {}
    
    try:
        info["title"] = driver.title
        info["url"] = driver.current_url
        
        # Count potential result elements
        result_selectors = [
            'article[data-testid="result"]',
            '.result',
            '[data-testid="result"]'
        ]
        
        for selector in result_selectors:
            try:
                elements = driver.find_elements("css selector", selector)
                info[f"elements_{selector}"] = len(elements)
            except Exception:
                info[f"elements_{selector}"] = 0
        
    except Exception as e:
        info["error"] = str(e)
    
    return info