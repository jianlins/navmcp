"""
Save tool for MCP Browser Tools

Provides the save_file tool for writing large/untruncated content to files.
"""

from typing import Dict, Any, Optional, Annotated
from pydantic import BaseModel, Field

class SaveFileInput(BaseModel):
    """Input schema for save_file tool."""
    path: str = Field(
        description="File path to save content to (relative to project root)",
        examples=["output.html", "data/large.txt"],
        min_length=1,
        max_length=4096
    )
    content: str = Field(
        description="Raw content to write to the file",
        min_length=1
    )

class SaveFileOutput(BaseModel):
    """Output schema for save_file tool."""
    path: str = Field(description="File path where content was saved")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

def setup_save_tools(mcp):
    """Setup save-related MCP tools."""

    from navmcp.tools.fetch import fetch_url

    @mcp.tool()
    async def save_file(
        path: Annotated[str, Field(
            description="File path to save content to (relative to project root)",
            examples=["output.html", "data/large.txt"],
            min_length=1,
            max_length=4096
        )],
        content: Annotated[str, Field(
            description="Raw content to write to the file",
            min_length=1
        )]
    ) -> SaveFileOutput:
        import os

        try:
            abs_path = os.path.abspath(path)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            metadata = {"size_bytes": len(content)}
            return SaveFileOutput(
                path=abs_path,
                status="ok",
                metadata=metadata
            )
        except Exception as e:
            return SaveFileOutput(
                path=path,
                status="error",
                error=str(e),
                metadata={}
            )

    class FetchAndSaveUrlInput(BaseModel):
        url: str = Field(
            description="URL to fetch content from",
            min_length=1,
            max_length=2048
        )
        path: str = Field(
            description="File path to save content to (relative to project root)",
            min_length=1,
            max_length=4096
        )

    class FetchAndSaveUrlOutput(BaseModel):
        path: str = Field(description="File path where content was saved")
        status: str = Field(description="Status: 'ok' or 'error'")
        error: Optional[str] = Field(None, description="Error message if status is 'error'")
        metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @mcp.tool()
    async def fetch_and_save_url(
        url: Annotated[str, Field(
            description="URL to fetch content from",
            min_length=1,
            max_length=2048
        )],
        path: Annotated[str, Field(
            description="File path to save content to (relative to project root)",
            min_length=1,
            max_length=4096
        )]
    ) -> FetchAndSaveUrlOutput:
        """
        Fetch content from a URL using the fetch tool (Selenium) and save it directly to a file.
        Args:
            url: URL to fetch content from
            path: File path to save content to (relative to project root)
        Returns:
            FetchAndSaveUrlOutput with status and metadata
        """
        import os

        try:
            fetch_result = await fetch_url(url)
            if fetch_result.status != "ok":
                return FetchAndSaveUrlOutput(
                    path=path,
                    status="error",
                    error=f"Fetch failed: {fetch_result.error}",
                    metadata=fetch_result.metadata
                )
            content = fetch_result.html
            abs_path = os.path.abspath(path)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            metadata = {
                "size_bytes": len(content),
                "url": url,
                "final_url": fetch_result.final_url,
                "status_code": fetch_result.metadata.get("status_code", None),
                "title": fetch_result.title
            }
            return FetchAndSaveUrlOutput(
                path=abs_path,
                status="ok",
                metadata=metadata
            )
        except Exception as e:
            return FetchAndSaveUrlOutput(
                path=path,
                status="error",
                error=str(e),
                metadata={}
            )
