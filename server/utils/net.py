"""
Network utilities for MCP Browser Tools

Provides URL validation, domain allowlist checking, and security functions.
"""

import os
import re
from typing import Set, Optional, List
from urllib.parse import urlparse, urlunparse
from ipaddress import ip_address, AddressValueError

from loguru import logger


# Default blocked schemes
BLOCKED_SCHEMES = {'file', 'data', 'javascript', 'vbscript', 'ftp'}

# Private/local IP ranges (RFC 1918, RFC 3927, loopback)
PRIVATE_IP_PATTERNS = [
    re.compile(r'^127\.'),  # Loopback
    re.compile(r'^10\.'),   # Private class A
    re.compile(r'^192\.168\.'),  # Private class C
    re.compile(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.'),  # Private class B
    re.compile(r'^169\.254\.'),  # Link-local
    re.compile(r'^0\.0\.0\.0$'),  # Unspecified
    re.compile(r'^255\.255\.255\.255$'),  # Broadcast
]


def get_allowed_hosts() -> Optional[Set[str]]:
    """
    Get the set of allowed hosts from environment variable.
    
    Returns:
        Set of allowed host patterns, or None if no restriction
    """
    allowed_hosts_env = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if not allowed_hosts_env:
        return None
    
    hosts = {host.strip().lower() for host in allowed_hosts_env.split(",") if host.strip()}
    logger.info(f"Loaded allowed hosts: {hosts}")
    return hosts if hosts else None


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is basically valid and parseable.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    if not url or not isinstance(url, str):
        return False
    
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def is_allowed_scheme(url: str) -> bool:
    """
    Check if URL scheme is allowed (not in blocked list).
    
    Args:
        url: URL to check
        
    Returns:
        True if scheme is allowed
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        return scheme not in BLOCKED_SCHEMES and scheme in {'http', 'https'}
    except Exception:
        return False


def is_private_ip(hostname: str) -> bool:
    """
    Check if hostname resolves to a private/local IP address.
    
    Args:
        hostname: Hostname to check
        
    Returns:
        True if hostname appears to be private/local
    """
    hostname_lower = hostname.lower()
    local_hostnames = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}
    # If it's a valid domain (contains a dot, not .local, not local hostnames), treat as public
    if '.' in hostname and hostname_lower not in local_hostnames and not hostname_lower.endswith('.local'):
        return False
    # Otherwise, check IP logic
    try:
        ip = ip_address(hostname)
        # Check for private ranges
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return True
        # Check specific patterns
        ip_str = str(ip)
        return any(pattern.match(ip_str) for pattern in PRIVATE_IP_PATTERNS)
    except (AddressValueError, ValueError):
        if hostname_lower in local_hostnames:
            return True
        if hostname_lower.endswith('.local'):
            return True
        if '.' not in hostname:
            return True
        return False


def is_allowed_host(url: str, allowed_hosts: Optional[Set[str]] = None) -> bool:
    """
    Check if URL's host is in the allowed hosts list.
    
    Args:
        url: URL to check
        allowed_hosts: Set of allowed host patterns (None = all allowed)
        
    Returns:
        True if host is allowed
    """
    if allowed_hosts is None:
        allowed_hosts = get_allowed_hosts()
    
    if allowed_hosts is None:
        return True  # No restriction
    
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        hostname_lower = hostname.lower()
        
        # Check exact matches and wildcard patterns
        for allowed_host in allowed_hosts:
            if allowed_host == hostname_lower:
                return True
            # Simple wildcard support (*.example.com)
            if allowed_host.startswith('*.') and hostname_lower.endswith(allowed_host[1:]):
                return True
            # Domain suffix matching (example.com matches sub.example.com)
            if hostname_lower.endswith('.' + allowed_host):
                return True
                
        return False
    except Exception as e:
        logger.warning(f"Error checking allowed host for {url}: {e}")
        return False


def validate_url_security(url: str, 
                         allow_private: bool = False,
                         allowed_hosts: Optional[Set[str]] = None) -> tuple[bool, Optional[str]]:
    """
    Comprehensive URL security validation.
    
    Args:
        url: URL to validate
        allow_private: Whether to allow private/local IP addresses
        allowed_hosts: Set of allowed host patterns
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not is_valid_url(url):
        return False, "Invalid URL format"
    
    if not is_allowed_scheme(url):
        return False, f"URL scheme not allowed. Only http and https are permitted"
    
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False, "URL missing hostname"
        
        # Check for private IP addresses
        if not allow_private and is_private_ip(hostname):
            return False, "Private/local IP addresses are not allowed"
        
        # Check allowed hosts
        if not is_allowed_host(url, allowed_hosts):
            return False, f"Host '{hostname}' is not in allowed hosts list"
        
        return True, None
        
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


def normalize_url(url: str) -> str:
    """
    Normalize a URL to a standard form.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL
    """
    if not url:
        return url
    
    try:
        # Parse and reconstruct to normalize
        parsed = urlparse(url)
        
        # Ensure scheme is lowercase
        scheme = parsed.scheme.lower()
        
        # Ensure netloc is lowercase
        netloc = parsed.netloc.lower()
        
        # Reconstruct URL
        normalized = urlunparse((
            scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return normalized
        
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url


def extract_domain(url: str) -> Optional[str]:
    """
    Extract the domain from a URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name or None if extraction fails
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname:
            # Remove 'www.' prefix if present
            if hostname.startswith('www.'):
                hostname = hostname[4:]
            return hostname.lower()
        return None
    except Exception:
        return None


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if both URLs are from the same domain
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    return domain1 is not None and domain1 == domain2


def get_base_url(url: str) -> Optional[str]:
    """
    Get the base URL (scheme + netloc) from a full URL.
    
    Args:
        url: Full URL
        
    Returns:
        Base URL or None if parsing fails
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return None
    except Exception:
        return None
