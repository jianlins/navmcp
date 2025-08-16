"""
I/O utilities for MCP Browser Tools

Provides path utilities, safe filename generation, and temporary directory management.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse, unquote

from loguru import logger


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to be safe for filesystem use.
    
    Args:
        filename: Original filename
        max_length: Maximum length for the filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove or replace invalid characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "untitled"
    
    # Truncate if too long, preserving extension
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        max_name_length = max_length - len(ext)
        if max_name_length > 0:
            sanitized = name[:max_name_length] + ext
        else:
            sanitized = sanitized[:max_length]
    
    # Avoid reserved names on Windows
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    name_part = os.path.splitext(sanitized)[0].upper()
    if name_part in reserved_names:
        sanitized = f"_{sanitized}"
    
    return sanitized


def filename_from_url(url: str, default_name: str = "download") -> str:
    """
    Extract a safe filename from a URL.
    
    Args:
        url: URL to extract filename from
        default_name: Default name if none can be extracted
        
    Returns:
        Safe filename extracted from URL
    """
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        # Get the last part of the path
        filename = os.path.basename(path)
        
        if filename and '.' in filename:
            return sanitize_filename(filename)
        
        # Try to use the domain name if no filename
        if parsed.netloc:
            domain_name = parsed.netloc.replace('www.', '').split('.')[0]
            return sanitize_filename(f"{domain_name}_{default_name}")
            
    except Exception as e:
        logger.warning(f"Failed to extract filename from URL {url}: {e}")
    
    return sanitize_filename(default_name)


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Returns:
        Path object for the directory
        
    Raises:
        OSError: If directory cannot be created
    """
    path_obj = Path(path)
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj
    except OSError as e:
        logger.error(f"Failed to create directory {path_obj}: {e}")
        raise


def get_unique_filename(directory: Union[str, Path], filename: str) -> Path:
    """
    Get a unique filename in a directory, adding a counter if needed.
    
    Args:
        directory: Directory to check for uniqueness
        filename: Desired filename
        
    Returns:
        Path object for a unique filename
    """
    directory = Path(directory)
    ensure_directory(directory)
    
    base_path = directory / filename
    
    if not base_path.exists():
        return base_path
    
    # Add counter to make unique
    name, ext = os.path.splitext(filename)
    counter = 1
    
    while True:
        unique_filename = f"{name}_{counter}{ext}"
        unique_path = directory / unique_filename
        if not unique_path.exists():
            return unique_path
        counter += 1
        
        # Prevent infinite loop
        if counter > 9999:
            raise OSError(f"Could not create unique filename for {filename}")


def get_file_size(path: Union[str, Path]) -> Optional[int]:
    """
    Get the size of a file in bytes.
    
    Args:
        path: Path to the file
        
    Returns:
        File size in bytes, or None if file doesn't exist
    """
    try:
        return Path(path).stat().st_size
    except (OSError, FileNotFoundError):
        return None


def is_pdf_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is likely a PDF based on extension and magic bytes.
    
    Args:
        path: Path to the file
        
    Returns:
        True if file appears to be a PDF
    """
    path_obj = Path(path)
    
    # Check extension
    if path_obj.suffix.lower() != '.pdf':
        return False
    
    # Check magic bytes if file exists
    try:
        with open(path_obj, 'rb') as f:
            header = f.read(4)
            return header == b'%PDF'
    except (OSError, FileNotFoundError):
        # If we can't read the file, trust the extension
        return True


def create_temp_directory(prefix: str = "mcp_browser_") -> Path:
    """
    Create a temporary directory.
    
    Args:
        prefix: Prefix for the temporary directory name
        
    Returns:
        Path object for the temporary directory
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    logger.debug(f"Created temporary directory: {temp_dir}")
    return temp_dir


def cleanup_temp_directory(temp_dir: Union[str, Path]) -> None:
    """
    Clean up a temporary directory and its contents.
    
    Args:
        temp_dir: Path to the temporary directory
    """
    import shutil
    
    temp_dir = Path(temp_dir)
    if temp_dir.exists() and temp_dir.is_dir():
        try:
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except OSError as e:
            logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")