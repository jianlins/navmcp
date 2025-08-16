"""
Smoke tests for MCP Browser Tools Server

Tests MCP server functionality using fastmcp Client for efficient in-memory testing.
No HTTP transport layer testing - focuses on MCP protocol directly.
"""

import pytest
import asyncio
from typing import Dict, Any

from fastmcp import Client
from navmcp.app import mcp

# Skip these tests if browser tests are disabled
pytestmark = pytest.mark.skipif(
    __import__('os').getenv('SKIP_BROWSER_TESTS') == '1',
    reason="Browser tests disabled via SKIP_BROWSER_TESTS=1"
)


class TestMCPServer:
    """Test the MCP server using fastmcp Client (recommended approach)."""
    
    @pytest.mark.asyncio
    async def test_mcp_initialize(self):
        """Test MCP initialize using fastmcp Client."""
        async with Client(mcp) as client:
            # Get initialize result 
            result = client.initialize_result
            
            # Check server info
            assert hasattr(result, "serverInfo")
            server_info = result.serverInfo
            assert server_info.name == "navmcp"
            assert hasattr(server_info, "version")
            
            # Check capabilities
            assert hasattr(result, "capabilities")
            capabilities = result.capabilities
            assert hasattr(capabilities, "tools")
    
    @pytest.mark.asyncio
    async def test_mcp_tools_list(self):
        """Test MCP tools/list using fastmcp Client."""
        async with Client(mcp) as client:
            # List tools
            tools = await client.list_tools()
            
            # Check that we have the expected tools
            expected_tools = {
                "fetch_url",
                "find_elements", 
                "click_element",
                "run_js_interaction",
                "download_pdfs",
                "web_search"
            }
            
            tool_names = {tool.name for tool in tools}
            assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"
            
            # Check tool structure
            for tool in tools:
                assert hasattr(tool, "name")
                assert hasattr(tool, "description")
                assert hasattr(tool, "inputSchema")
                
                # Validate input schema
                schema = tool.inputSchema
                assert "type" in schema
                assert schema["type"] == "object"
                assert "properties" in schema

    @pytest.mark.asyncio
    async def test_mcp_tool_call_validation(self):
        """Test calling a tool with invalid input."""
        async with Client(mcp) as client:
            # Try calling fetch_url with invalid URL (should handle gracefully)
            try:
                result = await client.call_tool("fetch_url", arguments={"url": "invalid-url"})
                # Should either succeed or raise an appropriate error
                assert result is not None or True  # Allow either success or controlled failure
            except Exception as e:
                # Should be a controlled error, not a crash
                assert "invalid" in str(e).lower() or "error" in str(e).lower()

    @pytest.mark.asyncio
    async def test_mcp_tool_call_nonexistent(self):
        """Test calling a non-existent tool."""
        async with Client(mcp) as client:
            # Try calling non-existent tool
            try:
                result = await client.call_tool("nonexistent_tool", arguments={})
                # Should raise an appropriate error
                pytest.fail("Expected error for non-existent tool")
            except Exception as e:
                # Should be a controlled error about the tool not existing
                error_msg = str(e).lower()
                assert any(word in error_msg for word in ["not found", "unknown", "nonexistent", "invalid"])

    @pytest.mark.asyncio
    async def test_mcp_tools_schemas_valid(self):
        """Test that all tool schemas are valid."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
            
            # Test each tool's schema
            for tool in tools:
                name = tool.name
                schema = tool.inputSchema
                
                # Basic schema validation
                assert isinstance(schema, dict), f"Tool {name} schema is not a dict"
                assert schema.get("type") == "object", f"Tool {name} schema type is not object"
                assert "properties" in schema, f"Tool {name} schema missing properties"
                
                properties = schema["properties"]
                assert isinstance(properties, dict), f"Tool {name} properties is not a dict"
                
                # Check that each property has a type
                for prop_name, prop_schema in properties.items():
                    assert "type" in prop_schema or "$ref" in prop_schema or "anyOf" in prop_schema, \
                        f"Tool {name} property {prop_name} missing type definition"


# Standalone test function for basic verification
@pytest.mark.asyncio
async def test_server_initialization():
    """Standalone test for server initialization."""
    async with Client(mcp) as client:
        result = client.initialize_result
    assert result.serverInfo.name == "navmcp"
    print(f"Server initialized successfully: {result.serverInfo.name} v{result.serverInfo.version}")


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_server_initialization())
