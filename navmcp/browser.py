"""
Browser Manager for MCP Browser Tools

Manages Selenium WebDriver lifecycle, Chrome configuration, and download settings.
"""

import os
import asyncio
from typing import Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from loguru import logger

try:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.service import Service
except ImportError:
    # Fallback for older selenium versions
    from selenium.webdriver.chrome.service import Service as ChromeService

# Fallback import for webdriver-manager if Selenium Manager fails
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False
    logger.warning("webdriver-manager not available, relying on Selenium Manager")


class BrowserManager:
    """Manages Chrome WebDriver lifecycle and configuration."""
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self._lock = asyncio.Lock()
        
        # Configuration from environment
        # Headless mode is now only controlled by command parameters, not environment variable
        self.headless = True
        self.download_dir = Path(os.getenv("DOWNLOAD_DIR", ".data/downloads")).resolve()
        self.page_load_timeout = int(os.getenv("PAGE_LOAD_TIMEOUT_S", "30"))
        self.script_timeout = int(os.getenv("SCRIPT_TIMEOUT_S", "30"))
        
        # Ensure download directory exists
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Browser config: headless={self.headless}, download_dir={self.download_dir}")

    async def set_headless(self, headless: bool):
        """Set headless mode and restart driver if needed."""
        if self.headless != headless:
            self.headless = headless
            await self.restart_driver()
            logger.info(f"Headless mode set to {self.headless} and browser restarted")
    
    def _create_chrome_options(self) -> Options:
        """Create Chrome options with download and security settings."""
        options = Options()
        
        # Headless mode
        if self.headless:
            options.add_argument("--headless=new")
        
        # Security and performance flags
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        # options.add_argument("--disable-javascript")  # Will be re-enabled per tool as needed
        
        # Set genuine user agent
        # Latest Chrome user-agent string for Windows 10 (April 2025)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
        
        # Download preferences
        download_prefs = {
            "profile.default_content_settings.popups": 0,
            "download.default_directory": str(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", download_prefs)
        
        # Disable automation indicators
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        return options
    
    def _create_driver_service(self) -> Optional[ChromeService]:
        """Create Chrome driver service, trying Selenium Manager first."""
        try:
            # Try Selenium Manager (built-in since Selenium 4.6+)
            service = ChromeService()
            logger.info("Using Selenium Manager for ChromeDriver")
            return service
        except Exception as e:
            logger.warning(f"Selenium Manager failed: {e}")
            
            # Fallback to webdriver-manager if available
            if WEBDRIVER_MANAGER_AVAILABLE:
                try:
                    driver_path = ChromeDriverManager().install()
                    service = ChromeService(executable_path=driver_path)
                    logger.info("Using webdriver-manager for ChromeDriver")
                    return service
                except Exception as e:
                    logger.error(f"webdriver-manager failed: {e}")
            
            # Let Selenium handle it (might work if ChromeDriver is in PATH)
            logger.info("Using system ChromeDriver (if available)")
            return None
    
    async def start(self) -> None:
        """Initialize the Chrome WebDriver."""
        async with self._lock:
            if self.driver:
                logger.warning("Driver already initialized")
                return
            
            try:
                options = self._create_chrome_options()
                service = self._create_driver_service()
                
                # Create driver
                if service:
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    self.driver = webdriver.Chrome(options=options)
                
                # Set timeouts
                self.driver.set_page_load_timeout(self.page_load_timeout)
                self.driver.set_script_timeout(self.script_timeout)
                self.driver.implicitly_wait(5)
                
                logger.info("Chrome WebDriver initialized successfully")
                
            except WebDriverException as e:
                logger.error(f"Failed to initialize Chrome WebDriver: {e}")
                raise
    
    async def stop(self) -> None:
        """Clean up the WebDriver."""
        async with self._lock:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Chrome WebDriver closed")
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {e}")
                finally:
                    self.driver = None
    
    async def get_driver(self) -> webdriver.Chrome:
        """Get the WebDriver instance, creating it if necessary. If the driver is invalid, restart it."""
        if not self.driver:
            await self.start()
        else:
            # Check if driver is alive by accessing a property
            try:
                _ = self.driver.current_url
            except WebDriverException as e:
                logger.warning(f"WebDriver appears invalid: {e}. Restarting driver.")
                await self.restart_driver()
        return self.driver
    
    async def restart_driver(self) -> None:
        """Restart the WebDriver (useful if it becomes unresponsive)."""
        logger.info("Restarting Chrome WebDriver")
        await self.stop()
        await self.start()
    
    def enable_javascript(self) -> None:
        """Enable JavaScript for the current session."""
        if self.driver:
            # This requires restarting the driver with different options
            # For now, log the request - full implementation would restart driver
            logger.info("JavaScript enable requested - consider driver restart")
    
    def get_download_dir(self) -> Path:
        """Get the configured download directory."""
        return self.download_dir
