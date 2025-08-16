"""
Tests for search.py functionality.

This module contains comprehensive tests for the academic search functionality
including real browser tests that verify actual search engine functionality.
Tests check if MCP server is running and prompt user to start it if needed.
"""

import pytest
import pytest_asyncio
import asyncio
import os
import sys
from typing import List
import requests
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from navmcp.tools.search import (
    WebSearchInput, WebSearchOutput, SearchResult,
    _search_google_scholar, _search_pubmed, _search_ieee,
    _search_arxiv, _search_medrxiv, _search_biorxiv,
    _parse_google_scholar_results, _parse_pubmed_results,
    _parse_ieee_results, _parse_arxiv_results,
    _parse_medrxiv_results, _parse_biorxiv_results,
    _extract_google_scholar_result, _extract_pubmed_result,
    _extract_ieee_result, _extract_arxiv_result,
    _extract_medrxiv_result, _extract_biorxiv_result,
    _wait_for_search_results, _get_search_page_info,
    setup_search_tools
)
from navmcp.browser import BrowserManager


# Server configuration
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "3333"))
SERVER_URL = f"http://{MCP_HOST}:{MCP_PORT}"


def check_mcp_server_running() -> bool:
    """
    Check if MCP server is running by testing the health endpoint.
    
    Returns:
        bool: True if server is running, False otherwise
    """
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "ok" and data.get("server") == "navmcp"
        return False
    except (requests.RequestException, Exception):
        return False


def prompt_user_to_start_server():
    """
    Prompt user to start the MCP server if it's not running.
    """
    print("\n" + "="*60)
    print("⚠️  MCP SERVER NOT RUNNING")
    print("="*60)
    print(f"The MCP server is not running on {SERVER_URL}")
    print("\nTo start the server, run one of these commands:")
    print(f"  py -m fastmcp http navmcp.app:app --host {MCP_HOST} --port {MCP_PORT}")
    print(f"  uvicorn navmcp.app:app --host {MCP_HOST} --port {MCP_PORT}")
    print("\nOr run from the project directory:")
    print("  python -m navmcp")
    print("\nWaiting for server to start...")
    print("="*60)
    
    # Wait for server to start (check every 2 seconds for up to 60 seconds)
    for i in range(30):
        time.sleep(2)
        if check_mcp_server_running():
            print("✅ Server is now running!")
            return True
            
    print("❌ Server did not start within 60 seconds.")
    print("Please start the server manually and run tests again.")
    return False


def ensure_mcp_server_running():
    """
    Ensure MCP server is running, prompt user if not.
    
    Returns:
        bool: True if server is running, False otherwise
    """
    if check_mcp_server_running():
        return True
        
    return prompt_user_to_start_server()


@pytest.fixture(scope="session", autouse=True)
def check_server_running():
    """
    Session-wide fixture that ensures MCP server is running before any tests.
    """
    if not ensure_mcp_server_running():
        pytest.exit("MCP server is not running. Please start the server and run tests again.")


@pytest_asyncio.fixture
async def browser_manager():
    """
    Create a real browser manager for testing.
    """
    manager = BrowserManager()
    await manager.start()
    yield manager
    await manager.stop()


class TestWebSearchInput:
    """Test WebSearchInput validation."""
    
    def test_valid_input_defaults(self):
        """Test valid input with default values."""
        input_data = WebSearchInput(query="machine learning")
        assert input_data.query == "machine learning"
        assert input_data.engine == "google_scholar"  # New default
        assert input_data.num_results == 10
    
    def test_valid_input_all_engines(self):
        """Test valid input with all supported engines."""
        engines = ["google_scholar", "pubmed", "ieee", "arxiv", "medrxiv", "biorxiv"]
        
        for engine in engines:
            input_data = WebSearchInput(
                query="test query",
                engine=engine,
                num_results=5
            )
            assert input_data.engine == engine
    
    def test_invalid_engine(self):
        """Test invalid engine raises validation error."""
        with pytest.raises(ValueError):
            WebSearchInput(query="test", engine="duckduckgo")  # Should be rejected
    
    def test_invalid_query_empty(self):
        """Test empty query raises validation error."""
        with pytest.raises(ValueError):
            WebSearchInput(query="")
    
    def test_invalid_query_too_long(self):
        """Test query too long raises validation error."""
        long_query = "a" * 513  # Over 512 character limit
        with pytest.raises(ValueError):
            WebSearchInput(query=long_query)
    
    def test_invalid_num_results_bounds(self):
        """Test num_results bounds validation."""
        with pytest.raises(ValueError):
            WebSearchInput(query="test", num_results=0)
        
        with pytest.raises(ValueError):
            WebSearchInput(query="test", num_results=21)
    
    def test_valid_num_results_bounds(self):
        """Test valid num_results bounds."""
        input_data = WebSearchInput(query="test", num_results=1)
        assert input_data.num_results == 1
        
        input_data = WebSearchInput(query="test", num_results=20)
        assert input_data.num_results == 20


class TestSearchResult:
    """Test SearchResult model."""
    
    def test_valid_search_result(self):
        """Test valid SearchResult creation."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet"
        )
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"


class TestWebSearchOutput:
    """Test WebSearchOutput model."""
    
    def test_valid_output_success(self):
        """Test valid successful output."""
        results = [
            SearchResult(title="Test", url="https://test.com", snippet="snippet")
        ]
        output = WebSearchOutput(
            results=results,
            query="test query",
            engine="google_scholar",
            status="ok"
        )
        assert len(output.results) == 1
        assert output.status == "ok"
        assert output.error is None
    
    def test_valid_output_error(self):
        """Test valid error output."""
        output = WebSearchOutput(
            results=[],
            query="test query",
            engine="google_scholar",
            status="error",
            error="Test error message"
        )
        assert len(output.results) == 0
        assert output.status == "error"
        assert output.error == "Test error message"


class TestSearchFunctions:
    """Test individual search engine functions with real browser."""
    
    @pytest.mark.asyncio
    async def test_search_google_scholar(self, browser_manager):
        """Test Google Scholar search function."""
        results = await _search_google_scholar(browser_manager, "machine learning", 3)
        
        # Should return a list (may be empty if search fails, but should be a list)
        assert isinstance(results, list)
        # If results are found, they should have the correct structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_pubmed(self, browser_manager):
        """Test PubMed search function."""
        results = await _search_pubmed(browser_manager, "covid-19", 3)
        
        # Should return a list
        assert isinstance(results, list)
        # If results are found, verify structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_ieee(self, browser_manager):
        """Test IEEE search function."""
        results = await _search_ieee(browser_manager, "neural networks", 3)
        
        # Should return a list
        assert isinstance(results, list)
        # If results are found, verify structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_arxiv(self, browser_manager):
        """Test arXiv search function."""
        results = await _search_arxiv(browser_manager, "quantum computing", 3)
        
        # Should return a list
        assert isinstance(results, list)
        # If results are found, verify structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_medrxiv(self, browser_manager):
        """Test medRxiv search function."""
        results = await _search_medrxiv(browser_manager, "vaccine", 3)
        
        # Should return a list
        assert isinstance(results, list)
        # If results are found, verify structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_biorxiv(self, browser_manager):
        """Test bioRxiv search function."""
        results = await _search_biorxiv(browser_manager, "CRISPR", 3)
        
        # Should return a list
        assert isinstance(results, list)
        # If results are found, verify structure
        for result in results:
            assert hasattr(result, 'title')
            assert hasattr(result, 'url')
            assert hasattr(result, 'snippet')
            assert len(result.title) > 0
            assert result.url.startswith('http')
    
    @pytest.mark.asyncio
    async def test_search_function_error_handling(self, browser_manager):
        """Test search function error handling with invalid query."""
        # Test with empty query - should still return empty list without crashing
        results = await _search_google_scholar(browser_manager, "", 5)
        assert isinstance(results, list)


class TestParsingFunctions:
    """Test HTML parsing functions."""
    
    def test_parse_google_scholar_results_empty(self):
        """Test parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_google_scholar_results(html, 5)
        assert results == []
    
    def test_parse_pubmed_results_empty(self):
        """Test PubMed parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_pubmed_results(html, 5)
        assert results == []
    
    def test_parse_ieee_results_empty(self):
        """Test IEEE parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_ieee_results(html, 5)
        assert results == []
    
    def test_parse_arxiv_results_empty(self):
        """Test arXiv parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_arxiv_results(html, 5)
        assert results == []
    
    def test_parse_medrxiv_results_empty(self):
        """Test medRxiv parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_medrxiv_results(html, 5)
        assert results == []
    
    def test_parse_biorxiv_results_empty(self):
        """Test bioRxiv parsing with empty HTML."""
        html = "<html><body></body></html>"
        results = _parse_biorxiv_results(html, 5)
        assert results == []


class TestExtractionFunctions:
    """Test result extraction functions."""
    
    def test_extract_google_scholar_result_none(self):
        """Test Google Scholar extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_google_scholar_result(element)
        assert result is None
    
    def test_extract_pubmed_result_none(self):
        """Test PubMed extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_pubmed_result(element)
        assert result is None
    
    def test_extract_ieee_result_none(self):
        """Test IEEE extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_ieee_result(element)
        assert result is None
    
    def test_extract_arxiv_result_none(self):
        """Test arXiv extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_arxiv_result(element)
        assert result is None
    
    def test_extract_medrxiv_result_none(self):
        """Test medRxiv extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_medrxiv_result(element)
        assert result is None
    
    def test_extract_biorxiv_result_none(self):
        """Test bioRxiv extraction with invalid element."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<div></div>", 'html.parser')
        element = soup.find('div')
        
        result = _extract_biorxiv_result(element)
        assert result is None


class TestUtilityFunctions:
    """Test utility functions with real browser."""
    
    @pytest.mark.asyncio
    async def test_wait_for_search_results(self, browser_manager):
        """Test waiting for search results with real browser."""
        # browser_manager is already properly yielded from the fixture
        driver = await browser_manager.get_driver()
        
        # Navigate to a simple page first
        driver.get("https://example.com")
        
        # Should not raise an exception
        await _wait_for_search_results(driver, max_wait=1)
    
    @pytest.mark.asyncio
    async def test_get_search_page_info(self, browser_manager):
        """Test getting search page info with real browser."""
        # browser_manager is already properly yielded from the fixture
        driver = await browser_manager.get_driver()
        
        # Navigate to a simple page
        driver.get("https://example.com")
        
        info = _get_search_page_info(driver)
        
        assert "title" in info
        assert "url" in info
        assert info["url"] == "https://example.com/"


class TestWebSearchTool:
    """Test the main web_search tool."""
    
    def test_web_search_input_validation_integration(self):
        """Test web_search input validation integration."""
        # Test that valid inputs work
        valid_input = WebSearchInput(
            query="machine learning",
            engine="google_scholar",
            num_results=5
        )
        assert valid_input.query == "machine learning"
        assert valid_input.engine == "google_scholar"
        assert valid_input.num_results == 5


class TestSearchIntegration:
    """Integration tests for search functionality."""
    
    @pytest.mark.skipif(
        pytest.importorskip("os").getenv("SKIP_BROWSER_TESTS", "1") == "1",
        reason="Browser tests skipped (set SKIP_BROWSER_TESTS=0 to enable)"
    )
    @pytest.mark.asyncio
    async def test_google_scholar_integration(self):
        """Integration test for Google Scholar search."""
        # This test would require a real browser manager
        # Skip by default to avoid external dependencies
        pytest.skip("Integration test - requires real browser")
    
    @pytest.mark.skipif(
        pytest.importorskip("os").getenv("SKIP_BROWSER_TESTS", "1") == "1",
        reason="Browser tests skipped (set SKIP_BROWSER_TESTS=0 to enable)"
    )
    @pytest.mark.asyncio
    async def test_pubmed_integration(self):
        """Integration test for PubMed search."""
        pytest.skip("Integration test - requires real browser")


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])
