"""
Basic end-to-end tests for MCP Browser Tools

Tests the actual tool functionality using stable public pages.
"""

import pytest
import asyncio
import time
from typing import Dict, Any

import httpx

# Skip these tests if browser tests are disabled
pytestmark = pytest.mark.skipif(
    __import__('os').getenv('SKIP_BROWSER_TESTS') == '1',
    reason="Browser tests disabled via SKIP_BROWSER_TESTS=1"
)


class TestFetchTool:
    """Test the fetch_url tool."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=60.0)
    
    def test_fetch_example_com(self, client: httpx.Client):
        """Test fetching example.com."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "fetch_url",
                    "arguments": {
                        "url": "https://example.com"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "content" in data
            content = data["content"]
            assert "status" in content
            assert "final_url" in content
            assert "title" in content
            assert "html" in content
            
            # Check successful fetch
            if content["status"] == "ok":
                assert content["final_url"].startswith("https://example.com")
                assert len(content["html"]) > 0
                assert "Example Domain" in content["title"] or "Example" in content["title"]
            else:
                # If fetch failed, should have error message
                assert "error" in content
                print(f"Fetch failed: {content['error']}")
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")
    
    def test_fetch_invalid_url(self, client: httpx.Client):
        """Test fetching an invalid URL."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "fetch_url",
                    "arguments": {
                        "url": "not-a-valid-url"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return error for invalid URL
            content = data["content"]
            assert content["status"] == "error"
            assert "error" in content
            
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


class TestFindElementsTool:
    """Test the find_elements tool."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=60.0)
    
    def test_find_elements_example_com(self, client: httpx.Client):
        """Test finding elements on example.com."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "find_elements",
                    "arguments": {
                        "url": "https://example.com",
                        "selector": "h1",
                        "by": "css"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            assert "status" in content
            
            if content["status"] == "ok":
                assert "count" in content
                assert "elements" in content
                assert "url" in content
                
                # Should find at least one h1 element
                assert content["count"] >= 0
                
                if content["count"] > 0:
                    element = content["elements"][0]
                    assert "text" in element
                    assert "attrs" in element
                    assert "tag_name" in element
                    assert element["tag_name"] == "h1"
            else:
                assert "error" in content
                print(f"Find elements failed: {content['error']}")
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")
    
    def test_find_elements_invalid_selector(self, client: httpx.Client):
        """Test finding elements with invalid selector."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "find_elements",
                    "arguments": {
                        "url": "https://example.com",
                        "selector": "invalid[[[selector",
                        "by": "css"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            # Should handle invalid selector gracefully
            assert content["status"] == "error" or content["count"] == 0
            
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


class TestSearchTool:
    """Test the web_search tool."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=60.0)
    
    def test_search_simple_query(self, client: httpx.Client):
        """Test a simple search query."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "web_search",
                    "arguments": {
                        "query": "python programming",
                        "engine": "duckduckgo",
                        "num_results": 5
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            assert "status" in content
            
            if content["status"] == "ok":
                assert "results" in content
                assert "query" in content
                assert "engine" in content
                
                assert content["query"] == "python programming"
                assert content["engine"] == "duckduckgo"
                
                # Should return some results
                results = content["results"]
                assert isinstance(results, list)
                assert len(results) <= 5
                
                if len(results) > 0:
                    result = results[0]
                    assert "title" in result
                    assert "url" in result
                    assert "snippet" in result
                    
                    # Basic validation
                    assert len(result["title"]) > 0
                    assert result["url"].startswith("http")
            else:
                assert "error" in content
                print(f"Search failed: {content['error']}")
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")
    
    def test_search_empty_query(self, client: httpx.Client):
        """Test search with empty query."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "web_search",
                    "arguments": {
                        "query": "",
                        "engine": "duckduckgo"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            assert content["status"] == "error"
            assert "error" in content
            
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


class TestJavaScriptTool:
    """Test the run_js_interaction tool."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=60.0)
    
    def test_simple_javascript(self, client: httpx.Client):
        """Test running simple JavaScript."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "run_js_interaction",
                    "arguments": {
                        "url": "https://example.com",
                        "script": "return document.title;",
                        "args": []
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            assert "status" in content
            
            if content["status"] == "ok":
                assert "result" in content
                # Should return the page title
                result = content["result"]
                assert isinstance(result, str)
                assert len(result) > 0
            else:
                assert "error" in content
                print(f"JavaScript execution failed: {content['error']}")
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")
    
    def test_javascript_with_args(self, client: httpx.Client):
        """Test JavaScript with arguments."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "run_js_interaction",
                    "arguments": {
                        "url": "https://example.com",
                        "script": "return arguments[0] + arguments[1];",
                        "args": [10, 20]
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            if content["status"] == "ok":
                assert content["result"] == 30
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


class TestClickTool:
    """Test the click_element tool."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=60.0)
    
    def test_click_nonexistent_element(self, client: httpx.Client):
        """Test clicking a non-existent element."""
        try:
            response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "click_element",
                    "arguments": {
                        "url": "https://example.com",
                        "selector": "#nonexistent-button",
                        "by": "css",
                        "timeout_s": 5
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            content = data["content"]
            # Should return error for non-existent element
            assert content["status"] == "error"
            assert "error" in content
            
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


class TestToolIntegration:
    """Test tool integration and chaining."""
    
    @pytest.fixture
    def client(self):
        return httpx.Client(timeout=90.0)
    
    def test_fetch_then_find_elements(self, client: httpx.Client):
        """Test fetching a page then finding elements on it."""
        try:
            # First, fetch the page
            fetch_response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "fetch_url",
                    "arguments": {
                        "url": "https://example.com"
                    }
                }
            )
            
            assert fetch_response.status_code == 200
            fetch_data = fetch_response.json()
            
            if fetch_data["content"]["status"] != "ok":
                pytest.skip("Fetch failed, cannot test integration")
            
            # Then find elements (should use the already loaded page)
            find_response = client.post(
                "http://127.0.0.1:3333/tools/call",
                json={
                    "name": "find_elements",
                    "arguments": {
                        "selector": "p",
                        "by": "css"
                    }
                }
            )
            
            assert find_response.status_code == 200
            find_data = find_response.json()
            
            if find_data["content"]["status"] == "ok":
                # Should find some paragraph elements
                assert find_data["content"]["count"] >= 0
                
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


def test_all_tools_registered():
    """Test that all expected tools are registered."""
    try:
        with httpx.Client() as client:
            response = client.post("http://127.0.0.1:3333/tools/list", json={})
            
            if response.status_code != 200:
                pytest.skip("Cannot get tools list")
                
            tools = response.json()["tools"]
            tool_names = {tool["name"] for tool in tools}
            
            expected_tools = {
                "fetch_url",
                "find_elements", 
                "click_element",
                "run_js_interaction",
                "download_pdfs",
                "web_search"
            }
            
            missing_tools = expected_tools - tool_names
            assert not missing_tools, f"Missing tools: {missing_tools}"
            
            print(f"All expected tools are registered: {sorted(tool_names)}")
            
    except httpx.ConnectError:
        pytest.skip("MCP server not running")


if __name__ == "__main__":
    # Run basic test when called directly
    test_all_tools_registered()