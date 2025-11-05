"""Web agent using Playwright for browser automation."""
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from utils.dom_extractor import extract_dom_tree, extract_interactive_elements, extract_form_fields
from utils.logger import setup_logger


class WebAgent:
    """Browser controller using Playwright."""
    
    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = False,
        viewport: Optional[Dict[str, int]] = None,
        timeout: int = 30000,
        screenshot_path: str = "data"
    ):
        """
        Initialize web agent.
        
        Args:
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Run in headless mode
            viewport: Viewport dimensions {"width": 1920, "height": 1080}
            timeout: Default timeout in milliseconds
            screenshot_path: Base path for saving screenshots
        """
        self.browser_type = browser_type
        self.headless = headless
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.timeout = timeout
        self.screenshot_path = Path(screenshot_path)
        self.logger = setup_logger("web_agent")
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def start(self) -> None:
        """Start the browser and create a new page."""
        self.playwright = await async_playwright().start()
        browser_class = getattr(self.playwright, self.browser_type)
        self.browser = await browser_class.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport=self.viewport
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        self.logger.info(f"Browser started: {self.browser_type}")
    
    async def stop(self) -> None:
        """Stop the browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Browser stopped")
    
    async def navigate(self, url: str, wait_until: str = "load", timeout: Optional[int] = None) -> None:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            wait_until: Wait condition - "load", "domcontentloaded", "networkidle", or "commit"
            timeout: Timeout in milliseconds (uses default if None)
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=timeout or self.timeout)
            # Give a small additional wait for SPAs to initialize
            await asyncio.sleep(2)
            self.logger.info(f"Navigated to: {url}")
        except Exception as e:
            self.logger.warning(f"Navigation timeout or error: {e}. Page may still be loading.")
            # Try to wait for page to be ready anyway
            await asyncio.sleep(3)
            self.logger.info(f"Continuing after navigation attempt to: {url}")
    
    async def capture_screenshot(self, filepath: str, full_page: bool = False) -> str:
        """
        Capture screenshot of current page.
        
        Args:
            filepath: Path to save screenshot
            full_page: If True, capture entire page. If False, capture only viewport (default: False)
        
        Returns:
            Path to saved screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        screenshot_path = Path(filepath)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Scroll to top to ensure we capture the main content area
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)  # Wait for scroll to complete
        
        # Capture viewport only (better for LLM processing)
        await self.page.screenshot(
            path=str(screenshot_path),
            full_page=full_page,
            type='png'
        )
        self.logger.info(f"Screenshot saved: {screenshot_path} (full_page={full_page})")
        return str(screenshot_path)
    
    async def capture_focused_area(self, filepath: str, selector: str = "main, [role='main'], .main-content, #main-content") -> str:
        """
        Capture screenshot of a focused content area instead of entire viewport.
        
        Args:
            filepath: Path to save screenshot
            selector: CSS selector for the main content area
        
        Returns:
            Path to saved screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        screenshot_path = Path(filepath)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Try to find and capture main content area
            element = await self.page.query_selector(selector)
            if element:
                await element.screenshot(path=str(screenshot_path))
                self.logger.info(f"Focused screenshot saved: {screenshot_path} (selector: {selector})")
                return str(screenshot_path)
            else:
                # Fallback to viewport if main content not found
                self.logger.warning(f"Main content selector not found, using viewport: {selector}")
                return await self.capture_screenshot(filepath, full_page=False)
        except Exception as e:
            self.logger.warning(f"Error capturing focused area: {e}, falling back to viewport")
            return await self.capture_screenshot(filepath, full_page=False)
    
    async def get_dom_tree(self) -> Dict[str, Any]:
        """
        Extract DOM tree from current page.
        
        Returns:
            DOM tree structure
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        return await extract_dom_tree(self.page)
    
    async def get_interactive_elements(self) -> list:
        """
        Get all interactive elements on the page.
        
        Returns:
            List of interactive elements
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        return await extract_interactive_elements(self.page)
    
    async def get_form_fields(self) -> list:
        """
        Get all form fields on the page.
        
        Returns:
            List of form fields
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        return await extract_form_fields(self.page)
    
    async def click(self, text: Optional[str] = None, selector: Optional[str] = None, timeout: Optional[int] = None) -> None:
        """
        Click an element by text or selector with multiple fallback strategies.
        
        Args:
            text: Text content to click
            selector: CSS selector to click
            timeout: Timeout in milliseconds (uses default if None)
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        timeout = timeout or self.timeout
        
        if text:
            # Try multiple strategies to find and click the element
            strategies = [
                f"text={text}",  # Exact text match
                f"text='{text}'",  # Quoted text
                f"text=/^{text}$/i",  # Case-insensitive regex
                f"button:has-text('{text}')",  # Button with text
                f"a:has-text('{text}')",  # Link with text
                f"[role='button']:has-text('{text}')",  # Role button with text
                f"button >> text={text}",  # Alternative syntax
            ]
            
            clicked = False
            last_error = None
            
            for strategy in strategies:
                try:
                    await self.page.click(strategy, timeout=timeout)
                    self.logger.info(f"Clicked element with text '{text}' using strategy: {strategy}")
                    clicked = True
                    break
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"Strategy '{strategy}' failed: {e}")
                    continue
            
            if not clicked:
                # Try to find similar text (case-insensitive, partial match)
                try:
                    # Use more flexible matching
                    await self.page.click(f"text=/{text}/i", timeout=timeout)
                    self.logger.info(f"Clicked element with text '{text}' using case-insensitive match")
                    clicked = True
                except Exception as e:
                    last_error = e
                
            if not clicked:
                error_msg = f"Could not find clickable element with text '{text}'. Last error: {last_error}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
                
        elif selector:
            try:
                await self.page.click(selector, timeout=timeout)
                self.logger.info(f"Clicked selector: {selector}")
            except Exception as e:
                error_msg = f"Could not click selector '{selector}': {e}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        else:
            raise ValueError("Either text or selector must be provided")
    
    async def fill(self, field: str, value: str) -> None:
        """
        Fill a form field.
        
        Args:
            field: Field name, label, placeholder, or selector
            value: Value to fill
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        # Try multiple strategies to find the field
        selectors = [
            f'input[name="{field}"]',
            f'input[placeholder*="{field}"]',
            f'label:has-text("{field}") + input',
            f'input[aria-label*="{field}"]',
            f'textarea[name="{field}"]',
            f'textarea[placeholder*="{field}"]'
        ]
        
        filled = False
        for selector in selectors:
            try:
                await self.page.fill(selector, value)
                filled = True
                self.logger.info(f"Filled field '{field}' with value: {value}")
                break
            except Exception:
                continue
        
        if not filled:
            raise ValueError(f"Could not find field: {field}")
    
    async def wait_for_modal(self, modal_text: Optional[str] = None, timeout: int = 5000) -> None:
        """
        Wait for a modal to appear.
        
        Args:
            modal_text: Text to look for in modal
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        if modal_text:
            await self.page.wait_for_selector(
                f'text={modal_text}',
                timeout=timeout
            )
        else:
            # Wait for common modal selectors
            modal_selectors = [
                '[role="dialog"]',
                '.modal',
                '[class*="modal"]',
                '[class*="dialog"]'
            ]
            for selector in modal_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=timeout)
                    break
                except Exception:
                    continue
        
        self.logger.info(f"Modal appeared: {modal_text or 'generic'}")
    
    async def wait_for_element(self, selector: str, timeout: int = 5000) -> None:
        """
        Wait for an element to appear.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        await self.page.wait_for_selector(selector, timeout=timeout)
        self.logger.info(f"Element appeared: {selector}")
    
    async def get_current_url(self) -> str:
        """Get current page URL."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        return self.page.url
    
    async def perform(self, action: Dict[str, Any]) -> None:
        """
        Perform an action based on action dictionary.
        
        Args:
            action: Action dictionary with 'action' and 'target' keys
        """
        action_type = action.get("action")
        target = action.get("target")
        value = action.get("value")
        
        if action_type == "click":
            await self.click(text=target)
        elif action_type == "fill":
            await self.fill(field=target, value=value)
        elif action_type == "navigate":
            await self.navigate(target)
        elif action_type == "wait":
            await asyncio.sleep(value or 1)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

