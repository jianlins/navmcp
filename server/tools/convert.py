"""
Convert tool for MCP Browser Tools

Provides the convert_to_markdown tool for converting PDF or HTML content to markdown.
"""

import asyncio
import time
import tempfile
import os
from typing import Callable, Dict, Any, Optional, Annotated
from pathlib import Path

from pydantic import BaseModel, Field
from loguru import logger
from markitdown import MarkItDown

from server.utils.net import validate_url_security, normalize_url


class ConvertToMarkdownInput(BaseModel):
    """Input schema for convert_to_markdown tool."""
    content_type: str = Field(
        description="Type of content to convert: 'url' for web pages, 'html' for HTML content, or 'pdf_url' for PDF files",
        examples=["url", "html", "pdf_url"]
    )
    content: str = Field(
        description="The content to convert - URL for 'url'/'pdf_url' types, or HTML string for 'html' type",
        examples=[
            "https://www.example.com", 
            "<html><body><h1>Hello World</h1></body></html>",
            "https://www.example.com/document.pdf"
        ],
        min_length=1,
        max_length=50000
    )


class ConvertToMarkdownOutput(BaseModel):
    """Output schema for convert_to_markdown tool."""
    markdown: str = Field(description="Converted markdown content")
    original_format: str = Field(description="Original format of the content")
    conversion_success: bool = Field(description="Whether conversion was successful")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def setup_convert_tools(mcp, get_browser_manager: Callable):
    """Setup conversion-related MCP tools."""
    
    @mcp.tool()
    async def convert_to_markdown(
        content_type: Annotated[str, Field(
            description="Type of content to convert: 'url' for web pages, 'html' for HTML content, or 'pdf_url' for PDF files",
            examples=["url", "html", "pdf_url"]
        )],
        content: Annotated[str, Field(
            description="The content to convert - URL for 'url'/'pdf_url' types, or HTML string for 'html' type",
            examples=[
                "https://www.example.com", 
                "<html><body><h1>Hello World</h1></body></html>",
                "https://www.example.com/document.pdf"
            ],
            min_length=1,
            max_length=50000
        )]
    ) -> ConvertToMarkdownOutput:
        """
        Convert PDF or HTML content to markdown format using MarkItDown.
        
        This tool can convert content from various sources:
        - Web pages (URLs) - fetches HTML and converts to markdown
        - HTML content - directly converts HTML string to markdown  
        - PDF files (URLs) - downloads PDF and converts to markdown
        
        The conversion uses Microsoft's MarkItDown library which provides
        high-quality conversion with proper formatting preservation.
        
        Key features:
        - Supports both HTML and PDF conversion
        - Handles web page fetching automatically
        - Preserves document structure and formatting
        - Provides detailed error reporting
        
        Use cases:
        - Converting web pages to markdown for documentation
        - Processing PDF documents for text analysis
        - Converting HTML content for markdown-based workflows
        - Creating readable text versions of documents
        
        Args:
            content_type: The type of content ('url', 'html', or 'pdf_url')
            content: The content to convert (URL or HTML string)
            
        Returns:
            ConvertToMarkdownOutput with markdown content and metadata
        """
        start_time = time.time()
        
        logger.info(f"Converting {content_type} content to markdown")
        
        try:
            # Validate content type
            valid_types = ['url', 'html', 'pdf_url']
            if content_type not in valid_types:
                return ConvertToMarkdownOutput(
                    markdown="",
                    original_format="unknown",
                    conversion_success=False,
                    status="error",
                    error=f"Invalid content_type. Must be one of: {valid_types}"
                )
            
            # Initialize MarkItDown
            md_converter = MarkItDown()
            
            # Handle different content types
            if content_type == 'html':
                # Convert HTML string directly
                result = await _convert_html_content(md_converter, content)
                
            elif content_type in ['url', 'pdf_url']:
                # Validate URL security for URL-based conversions
                is_valid, error_msg = validate_url_security(content, allow_private=False)
                if not is_valid:
                    logger.warning(f"URL validation failed for {content}: {error_msg}")
                    return ConvertToMarkdownOutput(
                        markdown="",
                        original_format="url",
                        conversion_success=False,
                        status="error",
                        error=f"URL validation failed: {error_msg}"
                    )
                
                # Normalize URL
                normalized_url = normalize_url(content)
                
                # Convert URL content
                result = await _convert_url_content(md_converter, normalized_url, content_type)
            
            # Add timing metadata
            duration = time.time() - start_time
            result.metadata["duration_seconds"] = round(duration, 2)
            result.metadata["timestamp"] = time.time()
            result.metadata["content_type"] = content_type
            
            logger.info(f"Conversion completed in {duration:.2f}s - Status: {result.status}")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error during conversion: {error_msg}")
            
            return ConvertToMarkdownOutput(
                markdown="",
                original_format=content_type,
                conversion_success=False,
                status="error",
                error=f"Unexpected error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )


async def _convert_html_content(md_converter: MarkItDown, html_content: str) -> ConvertToMarkdownOutput:
    """Convert HTML string content to markdown."""
    try:
        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(html_content)
            temp_file_path = temp_file.name
        
        try:
            # Convert using MarkItDown
            result = md_converter.convert_local(temp_file_path)
            
            return ConvertToMarkdownOutput(
                markdown=result.text_content,
                original_format="html",
                conversion_success=True,
                status="ok",
                metadata={"source": "html_string", "file_size": len(html_content)}
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
                
    except Exception as e:
        logger.error(f"Error converting HTML content: {str(e)}")
        return ConvertToMarkdownOutput(
            markdown="",
            original_format="html",
            conversion_success=False,
            status="error",
            error=f"HTML conversion failed: {str(e)}"
        )


async def _convert_url_content(md_converter: MarkItDown, url: str, content_type: str) -> ConvertToMarkdownOutput:
    """Convert URL content (web page or PDF) to markdown."""
    try:
        # Use MarkItDown's URL conversion capability
        result = md_converter.convert_url(url)
        
        # Determine original format based on content type
        original_format = "pdf" if content_type == "pdf_url" else "html"
        
        return ConvertToMarkdownOutput(
            markdown=result.text_content,
            original_format=original_format,
            conversion_success=True,
            status="ok",
            metadata={
                "source": "url",
                "url": url,
                "title": getattr(result, 'title', ''),
                "content_length": len(result.text_content)
            }
        )
        
    except Exception as e:
        logger.error(f"Error converting URL content {url}: {str(e)}")
        original_format = "pdf" if content_type == "pdf_url" else "html"
        
        return ConvertToMarkdownOutput(
            markdown="",
            original_format=original_format,
            conversion_success=False,
            status="error",
            error=f"URL conversion failed: {str(e)}"
        )