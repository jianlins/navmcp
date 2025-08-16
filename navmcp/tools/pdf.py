"""
PDF download tools for MCP Browser Tools

Provides the download_pdfs tool for downloading PDF files from web pages.
"""

import asyncio
import time
import os
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Annotated

from pydantic import BaseModel, Field
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

from navmcp.utils.net import validate_url_security, normalize_url, get_base_url
from navmcp.utils.parsing import (
    normalize_selector, detect_selector_type, extract_links, parse_html_with_soup
)
from navmcp.utils.io import (
    sanitize_filename, filename_from_url, get_unique_filename, is_pdf_file,
    get_file_size, ensure_directory
)


class DownloadPdfsInput(BaseModel):
    """Input schema for download_pdfs tool."""
    url: str = Field(
        description="URL of the web page to navigate to for finding and downloading PDF files",
        examples=[
            "https://www.example.com/documents", 
            "https://research.example.com/papers",
            "https://company.com/reports"
        ],
        min_length=1,
        max_length=2048
    )
    strategy: str = Field(
        default="auto", 
        description="Download strategy to use for finding PDFs",
        examples=["auto", "links", "js"],
        pattern="^(auto|links|js)$"
    )
    link_selector: Optional[str] = Field(
        None, 
        description="CSS selector to find PDF links when using 'links' strategy (e.g., 'a[href$=\".pdf\"]')",
        examples=["a[href$='.pdf']", ".pdf-link", "a[href*='download']", ".document-link a"],
        max_length=512
    )
    max_files: Optional[int] = Field(
        5, 
        description="Maximum number of PDF files to download (capped at 20 for performance)",
        ge=1,
        le=20,
        examples=[1, 5, 10]
    )
    timeout_s: Optional[int] = Field(
        60, 
        description="Maximum time in seconds to wait for each download to complete",
        ge=10,
        le=300,
        examples=[30, 60, 120]
    )


class DownloadedFile(BaseModel):
    """Information about a downloaded file."""
    file: str = Field(description="Path to the downloaded file")
    url: str = Field(description="Original URL of the file")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    filename: str = Field(description="Original filename")


class DownloadPdfsOutput(BaseModel):
    """Output schema for download_pdfs tool."""
    downloaded: List[DownloadedFile] = Field(description="List of successfully downloaded files")
    directory: str = Field(description="Download directory path")
    status: str = Field(description="Status: 'ok' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def setup_pdf_tools(mcp, get_browser_manager: Callable):
    """Setup PDF-related MCP tools."""
    
    @mcp.tool()
    async def download_pdfs(
        url: Annotated[str, Field(
            description="URL of the web page to navigate to for finding and downloading PDF files",
            examples=[
                "https://www.example.com/documents", 
                "https://research.example.com/papers",
                "https://company.com/reports"
            ],
            min_length=1,
            max_length=2048
        )],
        strategy: Annotated[str, Field(
            description="Download strategy to use for finding PDFs",
            examples=["auto", "links", "js"],
            pattern="^(auto|links|js)$"
        )] = "auto",
        link_selector: Annotated[Optional[str], Field(
            description="CSS selector to find PDF links when using 'links' strategy (e.g., 'a[href$=\".pdf\"]')",
            examples=["a[href$='.pdf']", ".pdf-link", "a[href*='download']", ".document-link a"],
            max_length=512
        )] = None,
        max_files: Annotated[int, Field(
            description="Maximum number of PDF files to download (capped at 20 for performance)",
            ge=1,
            le=20,
            examples=[1, 5, 10]
        )] = 5,
        timeout_s: Annotated[int, Field(
            description="Maximum time in seconds to wait for each download to complete",
            ge=10,
            le=300,
            examples=[30, 60, 120]
        )] = 60
    ) -> DownloadPdfsOutput:
        """
        Download PDF files from web pages using multiple detection and download strategies.
        
        This comprehensive tool navigates to a specified URL and downloads PDF files using
        intelligent strategies to handle different types of PDF hosting scenarios. It supports
        direct PDF links, JavaScript-triggered downloads, and custom selector-based detection.
        
        Download strategies:
        - 'auto': Automatically scans the page for PDF links (href ending with .pdf or containing 'pdf')
        - 'links': Uses a custom CSS selector to find specific PDF download links
        - 'js': Waits for JavaScript-triggered downloads after page interaction
        
        Key features:
        - Multiple download strategies for different site types
        - Automatic PDF file detection and validation
        - Safe filename generation and conflict resolution
        - Download progress monitoring and timeout handling
        - Comprehensive metadata about downloaded files
        - Performance limits to prevent abuse
        
        Strategy details:
        - auto: Best for sites with standard PDF links like research papers, documentation
        - links: Perfect when you know the specific CSS selector for PDF links
        - js: Ideal for sites that trigger downloads via JavaScript or require interaction
        
        Use cases:
        - Downloading research papers from academic sites
        - Bulk downloading reports and documentation
        - Collecting PDF resources from repositories
        - Archiving important documents for offline access
        - Automated document collection workflows
        
        Example usage:
        - input: {"url": "https://research.example.com/papers"} - Auto-detect and download PDFs
        - input: {"url": "https://docs.example.com", "strategy": "links", "link_selector": "a.pdf-download"} - Custom selector
        - input: {"url": "https://app.example.com/reports", "strategy": "js", "max_files": 3} - JS-triggered downloads
        
        Args:
            url: URL of the web page to navigate to for PDF downloads
            strategy: Download strategy ('auto', 'links', or 'js')
            link_selector: CSS selector for PDF links (for 'links' strategy)
            max_files: Maximum number of files to download
            timeout_s: Timeout for downloads in seconds
            
        Returns:
            DownloadPdfsOutput with downloaded file information and metadata
        """
        url = url.strip()
        strategy = strategy.lower()
        link_selector = link_selector.strip() if link_selector else None
        max_files = min(max_files or 5, 20)  # Cap at 20 for safety
        timeout_s = timeout_s or 60
        
        start_time = time.time()
        
        logger.info(f"Downloading PDFs from {url} using '{strategy}' strategy")
        if link_selector:
            logger.info(f"Using link selector: {link_selector}")
        
        try:
            # Validate URL security
            is_valid, error_msg = validate_url_security(url, allow_private=False)
            if not is_valid:
                logger.warning(f"URL validation failed for {url}: {error_msg}")
                return DownloadPdfsOutput(
                    downloaded=[],
                    directory="",
                    status="error",
                    error=f"URL validation failed: {error_msg}"
                )
            
            # Get browser manager
            browser_manager = await get_browser_manager()
            if not browser_manager:
                return DownloadPdfsOutput(
                    downloaded=[],
                    directory="",
                    status="error",
                    error="Browser manager not available"
                )
            
            # Get download directory
            download_dir = browser_manager.get_download_dir()
            ensure_directory(download_dir)
            
            # Get the WebDriver
            driver = await browser_manager.get_driver()
            
            # Track downloads before navigation
            initial_files = set(f.name for f in download_dir.iterdir() if f.is_file())
            
            # Navigate to the URL
            normalized_url = normalize_url(url)
            logger.debug(f"Navigating to: {normalized_url}")
            driver.get(normalized_url)
            
            # Wait for page to load
            await _wait_for_page_ready(driver)
            
            # Execute download strategy
            if strategy == "auto":
                downloaded_files = await _download_auto_strategy(
                    driver, download_dir, normalized_url, max_files, timeout_s, initial_files
                )
            elif strategy == "links":
                downloaded_files = await _download_links_strategy(
                    driver, download_dir, normalized_url, link_selector, max_files, timeout_s, initial_files
                )
            elif strategy == "js":
                downloaded_files = await _download_js_strategy(
                    driver, download_dir, normalized_url, max_files, timeout_s, initial_files
                )
            else:
                return DownloadPdfsOutput(
                    downloaded=[],
                    directory=str(download_dir),
                    status="error",
                    error=f"Unknown strategy: {strategy}"
                )
            
            # Prepare metadata
            duration = time.time() - start_time
            metadata = {
                "duration_seconds": round(duration, 2),
                "strategy": strategy,
                "max_files_requested": max_files,
                "files_downloaded": len(downloaded_files),
                "timestamp": time.time()
            }
            
            result = DownloadPdfsOutput(
                downloaded=downloaded_files,
                directory=str(download_dir),
                status="ok",
                metadata=metadata
            )
            
            logger.info(f"Downloaded {len(downloaded_files)} PDF files in {duration:.2f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Unexpected error downloading PDFs: {error_msg}")
            
            return DownloadPdfsOutput(
                downloaded=[],
                directory="",
                status="error",
                error=f"Unexpected error: {error_msg}",
                metadata={"duration_seconds": round(duration, 2)}
            )


async def _download_auto_strategy(
    driver, download_dir: Path, base_url: str, max_files: int, timeout_s: int, initial_files: set
) -> List[DownloadedFile]:
    """
    Auto strategy: Find PDF links automatically and download them.
    """
    downloaded_files = []
    
    try:
        # Get page HTML and parse it
        html = driver.page_source
        soup = parse_html_with_soup(html, base_url)
        
        # Extract all links that might be PDFs
        pdf_links = extract_links(soup, filter_extensions=['.pdf'])
        
        logger.info(f"Found {len(pdf_links)} potential PDF links")
        
        # Download each PDF link
        for link_info in pdf_links[:max_files]:
            pdf_url = link_info['url']
            
            try:
                # Navigate to PDF URL
                logger.debug(f"Downloading PDF: {pdf_url}")
                driver.get(pdf_url)
                
                # Wait for download to start/complete
                downloaded_file = await _wait_for_download(
                    download_dir, pdf_url, timeout_s, initial_files
                )
                
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
                    initial_files.add(downloaded_file.filename)
                
            except Exception as e:
                logger.warning(f"Failed to download PDF {pdf_url}: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Error in auto download strategy: {e}")
    
    return downloaded_files


async def _download_links_strategy(
    driver, download_dir: Path, base_url: str, link_selector: Optional[str], 
    max_files: int, timeout_s: int, initial_files: set
) -> List[DownloadedFile]:
    """
    Links strategy: Use a specific selector to find and click PDF links.
    """
    downloaded_files = []
    
    if not link_selector:
        # Default to PDF link selector
        link_selector = "a[href$='.pdf'], a[href*='.pdf']"
    
    try:
        # Normalize selector
        selector_type = detect_selector_type(link_selector)
        normalized_selector, selenium_by = normalize_selector(link_selector, selector_type)
        
        # Find PDF links
        wait = WebDriverWait(driver, 10)
        pdf_elements = driver.find_elements(selenium_by, normalized_selector)
        
        logger.info(f"Found {len(pdf_elements)} PDF link elements")
        
        # Click each link to download
        for i, element in enumerate(pdf_elements[:max_files]):
            try:
                href = element.get_attribute('href')
                if not href:
                    continue
                
                logger.debug(f"Clicking PDF link: {href}")
                
                # Click the link
                element.click()
                
                # Wait for download
                downloaded_file = await _wait_for_download(
                    download_dir, href, timeout_s, initial_files
                )
                
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
                    initial_files.add(downloaded_file.filename)
                
                # Small delay between downloads
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"Failed to click/download PDF link: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Error in links download strategy: {e}")
    
    return downloaded_files


async def _download_js_strategy(
    driver, download_dir: Path, base_url: str, max_files: int, timeout_s: int, initial_files: set
) -> List[DownloadedFile]:
    """
    JavaScript strategy: Wait for JavaScript-triggered downloads.
    """
    downloaded_files = []
    
    try:
        # Wait for any downloads to complete
        logger.info("Waiting for JavaScript-triggered downloads...")
        
        # Check periodically for new files
        end_time = time.time() + timeout_s
        last_file_count = 0
        
        while time.time() < end_time and len(downloaded_files) < max_files:
            # Check for new files
            current_files = {f for f in download_dir.iterdir() 
                           if f.is_file() and f.name not in initial_files}
            
            # Look for new PDF files
            for file_path in current_files:
                if is_pdf_file(file_path):
                    file_size = get_file_size(file_path)
                    
                    downloaded_file = DownloadedFile(
                        file=str(file_path),
                        url=base_url,  # We don't know the exact URL for JS downloads
                        size_bytes=file_size,
                        filename=file_path.name
                    )
                    
                    downloaded_files.append(downloaded_file)
                    initial_files.add(file_path.name)
                    logger.info(f"Found JS-triggered download: {file_path.name}")
            
            # If we found files, continue checking for more
            if len(downloaded_files) > last_file_count:
                last_file_count = len(downloaded_files)
                await asyncio.sleep(2)  # Give more time for additional downloads
            else:
                await asyncio.sleep(1)
        
        logger.info(f"JS strategy completed with {len(downloaded_files)} files")
        
    except Exception as e:
        logger.error(f"Error in JS download strategy: {e}")
    
    return downloaded_files


async def _wait_for_download(
    download_dir: Path, file_url: str, timeout_s: int, initial_files: set
) -> Optional[DownloadedFile]:
    """
    Wait for a specific download to complete.
    
    Args:
        download_dir: Directory to monitor for downloads
        file_url: URL of the file being downloaded
        timeout_s: Maximum time to wait
        initial_files: Set of files that existed before download
        
    Returns:
        DownloadedFile info if successful, None otherwise
    """
    end_time = time.time() + timeout_s
    expected_filename = filename_from_url(file_url, "download.pdf")
    
    while time.time() < end_time:
        # Check for new files
        current_files = list(download_dir.iterdir())
        
        for file_path in current_files:
            if not file_path.is_file() or file_path.name in initial_files:
                continue
            
            # Check if it's a PDF file
            if is_pdf_file(file_path):
                # Check if file is complete (not being written to)
                if await _is_download_complete(file_path):
                    file_size = get_file_size(file_path)
                    
                    return DownloadedFile(
                        file=str(file_path),
                        url=file_url,
                        size_bytes=file_size,
                        filename=file_path.name
                    )
        
        await asyncio.sleep(0.5)
    
    logger.warning(f"Download timeout for {file_url}")
    return None


async def _is_download_complete(file_path: Path, stability_time: float = 1.0) -> bool:
    """
    Check if a download is complete by monitoring file size stability.
    
    Args:
        file_path: Path to the file
        stability_time: Time in seconds to check for size stability
        
    Returns:
        True if download appears complete
    """
    try:
        initial_size = file_path.stat().st_size
        await asyncio.sleep(stability_time)
        final_size = file_path.stat().st_size
        
        # File size should be stable and non-zero
        return final_size > 0 and final_size == initial_size
        
    except Exception:
        return False


async def _wait_for_page_ready(driver, max_wait: int = 10) -> None:
    """Wait for page to be ready for interaction."""
    try:
        wait = WebDriverWait(driver, max_wait)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    except Exception as e:
        logger.debug(f"Page ready wait completed with exception: {e}")


# Utility function for debugging
def _get_download_info(download_dir: Path) -> Dict[str, Any]:
    """Get information about the download directory for debugging."""
    files = list(download_dir.iterdir()) if download_dir.exists() else []
    pdf_files = [f for f in files if f.is_file() and is_pdf_file(f)]
    
    return {
        "directory_exists": download_dir.exists(),
        "total_files": len(files),
        "pdf_files": len(pdf_files),
        "recent_files": [f.name for f in sorted(files, key=lambda x: x.stat().st_mtime)[-5:]]
    }
