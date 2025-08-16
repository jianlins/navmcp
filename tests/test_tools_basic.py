"""
Basic end-to-end tests for MCP Browser Tools

Tests the actual tool functionality using stable public pages.
"""

import pytest
import asyncio
import time
from typing import Dict, Any

try:
    from fastmcp import Client, FastMCP
    from fastmcp.exceptions import ToolError
    from navmcp.app import mcp
except ImportError:
    Client = None
    FastMCP = None
    ToolError = Exception
    mcp = None

# Skip these tests if browser tests are disabled
pytestmark = pytest.mark.skipif(
    __import__('os').getenv('SKIP_BROWSER_TESTS') == '1',
    reason="Browser tests disabled via SKIP_BROWSER_TESTS=1"
)


class TestFetchTool:
    """Test the fetch_url tool using FastMCP client."""
    @pytest.fixture
    def client(self):
        return Client(mcp)

    @pytest.mark.asyncio
    async def test_fetch_httpbin(self, client):
        async with client:
            result = await client.call_tool("fetch_url", {"url": "https://httpbin.org"}, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert content is not None
            # Check response structure
            assert hasattr(content, "final_url")
            assert hasattr(content, "title")
            assert hasattr(content, "html")
            # Check successful fetch
            assert content.final_url.startswith("https://httpbin.org")
            assert len(content.html) > 0
            assert "httpbin" in content.title.lower() or "httpbin" in content.html.lower()

    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self, client):
        async with client:
            result = await client.call_tool("fetch_url", {"url": "not-a-valid-url"}, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert content is not None
            assert hasattr(content, "status") and content.status == "error"
            assert hasattr(content, "error")


class TestFindElementsTool:
    """Test the find_elements tool using FastMCP client."""
    @pytest.fixture
    def client(self):
        return Client(mcp)

    @pytest.mark.asyncio
    async def test_find_elements_httpbin(self, client):
        async with client:
            result = await client.call_tool("find_elements", {
                "url": "https://httpbin.org",
                "selector": "h1",
                "by": "css"
            }, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert hasattr(content, "status")
            if content.status == "ok":
                assert hasattr(content, "count")
                assert hasattr(content, "elements")
                assert hasattr(content, "url")
                assert content.count >= 0
                if content.count > 0:
                    element = content.elements[0]
                    assert hasattr(element, "text")
                    assert hasattr(element, "attrs")
                    assert hasattr(element, "tag_name")
                    assert element.tag_name == "h1"
            else:
                assert hasattr(content, "error")

    @pytest.mark.asyncio
    async def test_find_elements_invalid_selector(self, client):
        async with client:
            result = await client.call_tool("find_elements", {
                "url": "https://httpbin.org",
                "selector": "invalid[[[selector",
                "by": "css"
            }, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert hasattr(content, "status") and (content.status == "error" or getattr(content, "count", 0) == 0)




class TestJavaScriptTool:
    """Test the run_js_interaction tool using FastMCP client."""
    @pytest.fixture
    def client(self):
        return Client(mcp)

    @pytest.mark.asyncio
    async def test_simple_javascript(self, client):
        async with client:
            result = await client.call_tool("run_js_interaction", {
                "url": "https://httpbin.org",
                "script": "return document.title;",
                "args": []
            }, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert hasattr(content, "status")
            if content.status == "ok":
                assert hasattr(content, "result")
                result_val = content.result
                assert isinstance(result_val, str)
                assert len(result_val) > 0
            else:
                assert hasattr(content, "error")

    @pytest.mark.asyncio
    async def test_javascript_with_args(self, client):
        async with client:
            result = await client.call_tool("run_js_interaction", {
                "url": "https://httpbin.org",
                "script": "return arguments[0] + arguments[1];",
                "args": [10, 20]
            }, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            if hasattr(content, "status") and content.status == "ok":
                assert hasattr(content, "result")
                assert content.result == 30


class TestClickTool:
    """Test the click_element tool using FastMCP client."""
    @pytest.fixture
    def client(self):
        return Client(mcp)

    @pytest.mark.asyncio
    async def test_click_nonexistent_element(self, client):
        async with client:
            result = await client.call_tool("click_element", {
                "url": "https://httpbin.org",
                "selector": "#nonexistent-button",
                "by": "css",
                "timeout_s": 5
            }, raise_on_error=False)
            content = result.data or (result.structured_content if hasattr(result, "structured_content") else {})
            assert hasattr(content, "status") and content.status == "error"
            assert hasattr(content, "error")


class TestToolIntegration:
    """Test tool integration and chaining using FastMCP client."""
    @pytest.fixture
    def client(self):
        return Client(mcp)

    @pytest.mark.asyncio
    async def test_fetch_then_find_elements(self, client):
        async with client:
            fetch_result = await client.call_tool("fetch_url", {"url": "https://httpbin.org"}, raise_on_error=False)
            fetch_content = fetch_result.data or (fetch_result.structured_content if hasattr(fetch_result, "structured_content") else {})
            assert fetch_content and hasattr(fetch_content, "status") and fetch_content.status == "ok"
            find_result = await client.call_tool("find_elements", {
                "selector": "p",
                "by": "css"
            }, raise_on_error=False)
            find_content = find_result.data or (find_result.structured_content if hasattr(find_result, "structured_content") else {})
            if hasattr(find_content, "status") and find_content.status == "ok":
                assert hasattr(find_content, "count")
                assert find_content.count >= 0

@pytest.mark.asyncio
async def test_toolerror_handling():
    """Test ToolError exception-based error handling."""
    if not (FastMCP and Client):
        pytest.skip("fastmcp not available")
    client = Client(mcp)
    async with client:
        try:
            await client.call_tool("nonexistent_tool", {}, raise_on_error=True)
        except ToolError as e:
            assert "nonexistent_tool" in str(e)

@pytest.mark.asyncio
async def test_tool_tag_filtering():
    """Test filtering tools by tag if metadata is available."""
    if not (FastMCP and Client):
        pytest.skip("fastmcp not available")
    client = Client(mcp)
    async with client:
        tools = await client.list_tools()
        analysis_tools = [
            tool for tool in tools
            if hasattr(tool, '_meta') and tool._meta and
               tool._meta.get('_fastmcp', {}) and
               'analysis' in tool._meta.get('_fastmcp', {}).get('tags', [])
        ]
        assert isinstance(analysis_tools, list)
@pytest.mark.asyncio
async def test_all_tools_registered():
    """Test that all expected tools are registered using FastMCP client."""
    if not (FastMCP and Client):
        pytest.skip("fastmcp not available")
    client = Client(mcp)
    async with client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
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


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_all_tools_registered())
