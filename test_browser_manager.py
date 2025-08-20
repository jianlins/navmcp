"""
Test script for BrowserManager
"""
import asyncio
from navmcp.browser import BrowserManager
from pathlib import Path
async def main():
    bm = BrowserManager()
    await bm.start()
    driver = await bm.get_driver()
    # Visit a site that shows user-agent and bot detection status
    driver.get("https://bot.sannysoft.com/")
    print("Page title:", driver.title)
    # Optionally, print page source for debugging
    print(driver.page_source[:1000]) 
    Path('tmp/detect_browser.txt').write_text(driver.page_source) # Print first 1000 chars
    await bm.stop()

if __name__ == "__main__":
    asyncio.run(main())
