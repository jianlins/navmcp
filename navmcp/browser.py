"""
Browser Manager for MCP Browser Tools

Manages Selenium WebDriver lifecycle, Chrome configuration, and download settings.
"""

import os
try:
    import chrome_version
    CHROME_VERSION_DETECT_AVAILABLE = True
except ImportError:
    CHROME_VERSION_DETECT_AVAILABLE = False
import asyncio
from typing import Optional
from pathlib import Path
from loguru import logger

# Use undetected-chromedriver for stealth automation
try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROMEDRIVER_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROMEDRIVER_AVAILABLE = False
    logger.error("undetected-chromedriver is not installed. Please install it for stealth automation.")



class BrowserManager:
    """Manages Chrome WebDriver lifecycle and configuration."""

    def __init__(self):
        self.driver: Optional[object] = None
        self._lock = asyncio.Lock()
        self.headless = True
        self.download_dir = Path(os.getenv("DOWNLOAD_DIR", ".data/downloads")).resolve()
        self.page_load_timeout = int(os.getenv("PAGE_LOAD_TIMEOUT_S", "30"))
        self.script_timeout = int(os.getenv("SCRIPT_TIMEOUT_S", "30"))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Browser config: headless={self.headless}, download_dir={self.download_dir}")

    async def set_headless(self, headless: bool):
        if self.headless != headless:
            self.headless = headless
            await self.restart_driver()
            logger.info(f"Headless mode set to {self.headless} and browser restarted")

    def _create_chrome_options(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.headless = True
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--enable-unsafe-swiftshader")
        # Use a valid Windows Chrome user-agent string (April 2025)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
        download_prefs = {
            "profile.default_content_settings.popups": 0,
            "download.default_directory": str(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", download_prefs)
        return options

    async def start(self) -> None:
        async with self._lock:
            if self.driver:
                logger.warning("Driver already initialized")
                return
            if not UNDETECTED_CHROMEDRIVER_AVAILABLE:
                logger.error("undetected-chromedriver is not available. Please install it.")
                raise ImportError("undetected-chromedriver is required for stealth automation.")
            try:
                options = self._create_chrome_options()
                # Detect Chrome version automatically
                if CHROME_VERSION_DETECT_AVAILABLE:
                    version_str = chrome_version.get_chrome_version()
                    if version_str:
                        major_version = int(version_str.split('.')[0])
                        logger.info(f"Detected Chrome version: {version_str}, using major version: {major_version}")
                        self.driver = uc.Chrome(options=options, version_main=major_version)
                    else:
                        logger.error("Could not detect Chrome version. Falling back to default version_main=137.")
                        self.driver = uc.Chrome(options=options, version_main=137)
                else:
                    logger.error("chrome-version package not installed. Falling back to default version_main=137.")
                    self.driver = uc.Chrome(options=options, version_main=137)
                self.driver.set_page_load_timeout(self.page_load_timeout)
                self.driver.set_script_timeout(self.script_timeout)
                self.driver.implicitly_wait(5)
                logger.info("Undetected Chrome WebDriver initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize undetected Chrome WebDriver: {e}")
                raise

    async def stop(self) -> None:
        async with self._lock:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Chrome WebDriver closed")
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {e}")
                finally:
                    self.driver = None

    async def get_driver(self):
        if not self.driver:
            await self.start()
        else:
            try:
                _ = self.driver.current_url
            except Exception as e:
                logger.warning(f"WebDriver appears invalid: {e}. Restarting driver.")
                await self.restart_driver()
        return self.driver

    async def restart_driver(self) -> None:
        logger.info("Restarting Chrome WebDriver")
        await self.stop()
        await self.start()

    def enable_javascript(self) -> None:
        logger.info("JavaScript enable requested - consider driver restart")

    def get_download_dir(self) -> Path:
        return self.download_dir
