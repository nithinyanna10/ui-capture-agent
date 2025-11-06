"""Web agent using Playwright for browser automation."""
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
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
        screenshot_path: str = "data",
        session_persistence: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize web agent.
        
        Args:
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Run in headless mode
            viewport: Viewport dimensions {"width": 1920, "height": 1080}
            timeout: Default timeout in milliseconds
            screenshot_path: Base path for saving screenshots
            session_persistence: Dict with enabled, storage_path, pause_at_start, pause_duration
        """
        self.browser_type = browser_type
        self.headless = headless
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.timeout = timeout
        self.screenshot_path = Path(screenshot_path)
        self.logger = setup_logger("web_agent")
        self.session_persistence = session_persistence or {}
        self.session_storage_path = Path(self.session_persistence.get("storage_path", "data/browser_session"))
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def start(self) -> None:
        """Start the browser and create a new page with optional session persistence."""
        self.playwright = await async_playwright().start()
        browser_class = getattr(self.playwright, self.browser_type)
        
        # Check if we should use existing Chrome user profile
        use_existing = self.session_persistence.get("use_existing_browser", False)
        user_data_dir = self.session_persistence.get("user_data_dir")
        
        self.logger.info(f"Session persistence config: use_existing={use_existing}, user_data_dir={user_data_dir}, browser_type={self.browser_type}")
        
        if use_existing and user_data_dir and self.browser_type in ["chromium", "chrome"]:
            # Use persistent context with existing Chrome profile
            import os
            user_data_path = os.path.expanduser(user_data_dir)
            self.logger.info(f"Expanded user data path: {user_data_path}")
            
            if os.path.exists(user_data_path):
                self.logger.info(f"✅ User data directory found: {user_data_path}")
                self.logger.info("⚠️  IMPORTANT: Close Chrome completely before running, or use a different profile path")
                self.logger.info("   Chrome cannot use the same user data directory if it's already running.")
                
                try:
                    # Try to use system Chrome channel
                    self.logger.info("Attempting to launch persistent context with Chrome channel...")
                    self.context = await browser_class.launch_persistent_context(
                        user_data_dir=user_data_path,
                        headless=self.headless,
                        viewport=self.viewport,
                        channel="chrome"  # Use system Chrome instead of Chromium
                    )
                    # Get the first page or create a new one
                    if self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        self.page = await self.context.new_page()
                    self.page.set_default_timeout(self.timeout)
                    self.logger.info("✅ Successfully connected to existing Chrome browser with your logged-in sessions")
                    self.logger.info(f"   Current URL: {self.page.url if hasattr(self.page, 'url') else 'N/A'}")
                except Exception as e:
                    self.logger.warning(f"❌ Failed to launch persistent context with channel: {e}")
                    self.logger.info("   This often happens if Chrome is already running. Close Chrome and try again.")
                    self.logger.info("   Trying fallback without channel parameter...")
                    try:
                        # Fallback: try without channel parameter
                        self.context = await browser_class.launch_persistent_context(
                            user_data_dir=user_data_path,
                            headless=self.headless,
                            viewport=self.viewport
                        )
                        if self.context.pages:
                            self.page = self.context.pages[0]
                        else:
                            self.page = await self.context.new_page()
                        self.page.set_default_timeout(self.timeout)
                        self.logger.info("✅ Connected to existing browser profile (without channel)")
                    except Exception as e2:
                        self.logger.error(f"❌ Failed to use persistent context: {e2}")
                        self.logger.error("   Common causes:")
                        self.logger.error("   1. Chrome is already running (close it first)")
                        self.logger.error("   2. Permission issues with the user data directory")
                        self.logger.error("   3. The profile is locked by another process")
                        self.logger.info("   Falling back to new browser instance...")
                        self.browser = await browser_class.launch(headless=self.headless)
            else:
                self.logger.warning(f"❌ User data directory not found: {user_data_path}")
                self.logger.info("   Please check the path in settings.yaml")
                self.logger.info("   macOS default: ~/Library/Application Support/Google/Chrome/Default")
                self.logger.info("   Launching new browser instead...")
                self.browser = await browser_class.launch(headless=self.headless)
        else:
            # Normal launch
            if not use_existing:
                self.logger.info("ℹ️  use_existing_browser is False, launching new browser")
            elif not user_data_dir:
                self.logger.warning("⚠️  use_existing_browser is True but user_data_dir is not set")
            elif self.browser_type not in ["chromium", "chrome"]:
                self.logger.warning(f"⚠️  use_existing_browser only works with chromium/chrome, but browser_type is {self.browser_type}")
            self.browser = await browser_class.launch(headless=self.headless)
        
        # Load saved session state if available (only if not using existing browser)
        storage_state = None
        if not use_existing and self.session_persistence.get("enabled", False):
            state_file = self.session_storage_path / "state.json"
            if state_file.exists():
                storage_state = str(state_file)
                self.logger.info(f"Loading saved browser session from {state_file}")
        
        # Create context if not already created (persistent context)
        if not self.context:
            self.context = await self.browser.new_context(
                viewport=self.viewport,
                storage_state=storage_state
            )
            self.page = await self.context.new_page()
        
        self.page.set_default_timeout(self.timeout)
        self.logger.info(f"Browser started: {self.browser_type}")
        
        # Pause at start for manual login if configured
        if self.session_persistence.get("pause_at_start", False):
            pause_duration = self.session_persistence.get("pause_duration", 60)
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"⏸️  PAUSED FOR MANUAL LOGIN")
            self.logger.info(f"   You have {pause_duration} seconds to log in manually in the browser.")
            self.logger.info(f"   After logging in, the agent will continue automatically.")
            self.logger.info(f"   Press Ctrl+C to continue immediately.")
            self.logger.info(f"{'='*60}\n")
            try:
                await asyncio.sleep(pause_duration)
            except KeyboardInterrupt:
                self.logger.info("Continuing execution...")
    
    async def stop(self) -> None:
        """Stop the browser and save session state if persistence is enabled."""
        use_existing = self.session_persistence.get("use_existing_browser", False)
        
        # Save browser session state before closing (only if not using existing browser)
        if not use_existing and self.context and self.session_persistence.get("enabled", False):
            try:
                self.session_storage_path.mkdir(parents=True, exist_ok=True)
                state_file = self.session_storage_path / "state.json"
                await self.context.storage_state(path=str(state_file))
                self.logger.info(f"Browser session saved to {state_file}")
            except Exception as e:
                self.logger.warning(f"Could not save browser session: {e}")
        
        # Close persistent context or regular browser
        if self.context and use_existing:
            await self.context.close()
        elif self.browser:
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
    
    async def capture_sidebar_regions(self, base_path: str) -> Dict[str, str]:
        """
        Capture focused screenshots of different page regions (left sidebar, header, main content).
        Useful for complex pages where elements might be missed.
        
        Args:
            base_path: Base path for screenshots (e.g., "data/task/step_00")
        
        Returns:
            Dictionary with region names and their screenshot paths
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        regions = {}
        base = Path(base_path)
        
        # Common selectors for different regions
        region_selectors = {
            "left_sidebar": "aside, [role='complementary'], .sidebar, nav[aria-label*='sidebar']",
            "header": "header, nav, [role='banner'], .header, .navbar",
            "main_content": "main, [role='main'], .main-content, #main-content",
            "right_sidebar": "aside:last-of-type, .right-sidebar"
        }
        
        for region_name, selector in region_selectors.items():
            try:
                # Try multiple selectors
                selectors = selector.split(", ")
                element = None
                for sel in selectors:
                    element = await self.page.query_selector(sel.strip())
                    if element:
                        break
                
                if element:
                    region_path = base.parent / f"{base.stem}_{region_name}{base.suffix}"
                    await element.screenshot(path=str(region_path))
                    regions[region_name] = str(region_path)
                    self.logger.debug(f"Captured {region_name} region: {region_path}")
            except Exception as e:
                self.logger.debug(f"Could not capture {region_name} region: {e}")
                continue
        
        return regions
    
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
    
    async def click(self, text: Optional[str] = None, selector: Optional[str] = None, timeout: Optional[int] = None, wait_for_navigation: bool = False) -> bool:
        """
        Click an element by text or selector with multiple fallback strategies.
        
        Args:
            text: Text content to click
            selector: CSS selector to click
            timeout: Timeout in milliseconds (uses default if None)
            wait_for_navigation: If True, wait for navigation after click (for submit buttons)
        
        Returns:
            True if navigation occurred (when wait_for_navigation=True), False otherwise
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        timeout = timeout or self.timeout
        
        # Check if this looks like a submit/login button
        is_submit_button = False
        if text:
            submit_keywords = ["sign in", "login", "submit", "continue", "create", "save", "next"]
            is_submit_button = any(keyword in text.lower() for keyword in submit_keywords)
        if wait_for_navigation or is_submit_button:
            wait_for_navigation = True
        
        if text:
            # Escape special regex characters for safe regex matching
            import re
            escaped_text = re.escape(text)
            
            # Try multiple strategies to find and click the element
            strategies = [
                f"text={text}",  # Exact text match (Playwright will handle escaping)
                f"text='{text}'",  # Quoted text
                f"text=/^{escaped_text}$/i",  # Case-insensitive regex (escaped)
                f"button:has-text('{text}')",  # Button with text
                f"a:has-text('{text}')",  # Link with text
                f"[role='button']:has-text('{text}')",  # Role button with text
                f"button >> text={text}",  # Alternative syntax
                # Also try with escaped text for has-text
                f"button:has-text('{escaped_text}')",  # Button with escaped text
                f"a:has-text('{escaped_text}')",  # Link with escaped text
            ]
            
            clicked = False
            last_error = None
            
            for strategy in strategies:
                try:
                    if wait_for_navigation:
                        # Get current URL before clicking
                        url_before = self.page.url
                        # Click and wait for navigation (but don't fail if no navigation occurs)
                        try:
                            async with self.page.expect_navigation(timeout=3000) as navigation_info:
                                await self.page.click(strategy, timeout=timeout)
                            await navigation_info.value
                            url_after = self.page.url
                            self.logger.info(f"✅ Clicked element with text '{text}' using strategy: {strategy}")
                            self.logger.info(f"✅ Navigation occurred: {url_before} -> {url_after}")
                            clicked = True
                            return True
                        except Exception as nav_error:
                            # Navigation timeout is OK - click succeeded, just no navigation
                            self.logger.info(f"✅ Clicked element with text '{text}' using strategy: {strategy}")
                            self.logger.info(f"ℹ️  No navigation occurred (modal/UI change instead)")
                            clicked = True
                            return False  # Click succeeded, but no navigation
                    else:
                        await self.page.click(strategy, timeout=timeout)
                        self.logger.info(f"✅ Clicked element with text '{text}' using strategy: {strategy}")
                        clicked = True
                        break
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"Strategy '{strategy}' failed: {e}")
                    continue
            
            if not clicked:
                # Try to find similar text (case-insensitive, partial match)
                try:
                    if wait_for_navigation:
                        url_before = self.page.url
                        try:
                            async with self.page.expect_navigation(timeout=3000) as navigation_info:
                                await self.page.click(f"text=/{escaped_text}/i", timeout=timeout)
                            await navigation_info.value
                            url_after = self.page.url
                            self.logger.info(f"✅ Clicked element with text '{text}' using case-insensitive match")
                            self.logger.info(f"✅ Navigation occurred: {url_before} -> {url_after}")
                            return True
                        except Exception as nav_error:
                            # Navigation timeout is OK - click succeeded, just no navigation
                            self.logger.info(f"✅ Clicked element with text '{text}' using case-insensitive match")
                            self.logger.info(f"ℹ️  No navigation occurred (modal/UI change instead)")
                            return False  # Click succeeded, but no navigation
                    else:
                        await self.page.click(f"text=/{escaped_text}/i", timeout=timeout)
                        self.logger.info(f"✅ Clicked element with text '{text}' using case-insensitive match")
                        clicked = True
                except Exception as e:
                    last_error = e
            
            # Strategy: Try clicking checkboxes (for task completion, etc.)
            if not clicked:
                self.logger.info(f"Text-based strategies failed. Trying checkbox strategies for '{text}'...")
                checkbox_keywords = ["done", "complete", "check", "checkbox", "task", "todo", "mark"]
                is_checkbox_task = any(keyword in text.lower() for keyword in checkbox_keywords)
                
                if is_checkbox_task:
                    # Try multiple checkbox strategies
                    checkbox_strategies = [
                        # Checkbox near the text
                        f':near-text("{text}") >> input[type="checkbox"]',
                        f':has-text("{text}") >> input[type="checkbox"]',
                        # Checkbox in same container as text
                        f':has-text("{text}") >> .. >> input[type="checkbox"]',
                        # Generic checkbox selectors
                        'input[type="checkbox"]:visible',
                        '[role="checkbox"]',
                        # Checkbox with aria-label
                        f'input[type="checkbox"][aria-label*="{text}"]',
                        f'[role="checkbox"][aria-label*="{text}"]',
                    ]
                    
                    for checkbox_selector in checkbox_strategies:
                        try:
                            checkbox = await self.page.query_selector(checkbox_selector)
                            if checkbox:
                                await checkbox.click(timeout=timeout)
                                self.logger.info(f"✅ Clicked checkbox using selector: {checkbox_selector}")
                                clicked = True
                                break
                        except Exception as e:
                            last_error = e
                            continue
                    
                    # Try finding checkbox by nearby text (click the text, then find nearby checkbox)
                    if not clicked:
                        try:
                            # Find text element, then look for checkbox in parent or sibling
                            text_element = await self.page.query_selector(f'text=/{escaped_text}/i')
                            if text_element:
                                # Try to find checkbox in parent container
                                parent = await text_element.evaluate_handle('el => el.parentElement')
                                if parent:
                                    checkbox = await parent.query_selector('input[type="checkbox"], [role="checkbox"]')
                                    if checkbox:
                                        await checkbox.click(timeout=timeout)
                                        self.logger.info(f"✅ Clicked checkbox near text '{text}'")
                                        clicked = True
                        except Exception as e:
                            last_error = e
                else:
                    # Not a checkbox task, but text-based strategies failed
                    if not clicked:
                        error_msg = f"Could not find clickable element with text '{text}'. Last error: {last_error}"
                        self.logger.error(error_msg)
                        raise ValueError(error_msg)
                
        elif selector:
            try:
                if wait_for_navigation:
                    url_before = self.page.url
                    async with self.page.expect_navigation(timeout=timeout) as navigation_info:
                        await self.page.click(selector, timeout=timeout)
                    await navigation_info.value
                    url_after = self.page.url
                    self.logger.info(f"Clicked selector: {selector}")
                    self.logger.info(f"Navigation occurred: {url_before} -> {url_after}")
                    return True
                else:
                    await self.page.click(selector, timeout=timeout)
                    self.logger.info(f"Clicked selector: {selector}")
            except Exception as e:
                error_msg = f"Could not click selector '{selector}': {e}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        else:
            raise ValueError("Either text or selector must be provided")
        
        return False
    
    async def fill(self, field: str, value: str) -> None:
        """
        Fill a form field. Supports both standard input/textarea fields and contenteditable divs.
        
        Args:
            field: Field name, label, placeholder, or selector
            value: Value to fill
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        timeout = self.timeout
        
        # Strategy 1: Try standard HTML input/textarea fields first
        standard_selectors = [
            f'input[name="{field}"]',
            f'input[placeholder*="{field}"]',
            f'label:has-text("{field}") + input',
            f'input[aria-label*="{field}"]',
            f'textarea[name="{field}"]',
            f'textarea[placeholder*="{field}"]',
            f'input[placeholder*="{field}"]',
            f'textarea[placeholder*="{field}"]'
        ]
        
        filled = False
        last_error = None
        
        for selector in standard_selectors:
            try:
                await self.page.fill(selector, value, timeout=timeout)
                filled = True
                self.logger.info(f"✅ Filled standard field '{field}' with value: {value}")
                break
            except Exception as e:
                last_error = e
                continue
        
        # Strategy 2: If standard fields failed, try contenteditable divs (like Notion)
        if not filled:
            self.logger.info(f"Standard input fields not found. Trying contenteditable divs for '{field}'...")
            
            contenteditable_selectors = [
                f'[contenteditable="true"][placeholder*="{field}"]',
                f'[contenteditable="true"]:has-text("{field}")',
                f'div[contenteditable="true"]',
                f'[contenteditable="true"][aria-label*="{field}"]',
                f'[contenteditable="true"][data-placeholder*="{field}"]',
                # Try to find by nearby text/placeholder
                f':has-text("{field}") >> [contenteditable="true"]',
                f':near-text("{field}") >> [contenteditable="true"]',
            ]
            
            for selector in contenteditable_selectors:
                try:
                    # For contenteditable, we need to click first, then type
                    element = await self.page.query_selector(selector)
                    if element:
                        # Click to focus the element
                        await element.click(timeout=timeout)
                        await asyncio.sleep(0.3)  # Brief wait for focus
                        
                        # Clear existing content (use Meta+A on Mac, Control+A on Windows/Linux)
                        import platform
                        select_all_key = "Meta+A" if platform.system() == "Darwin" else "Control+A"
                        await self.page.keyboard.press(select_all_key)
                        await asyncio.sleep(0.1)
                        
                        # Type the value
                        await self.page.keyboard.type(value, delay=50)  # Small delay for reliability
                        await asyncio.sleep(0.2)  # Wait for input to register
                        
                        filled = True
                        self.logger.info(f"✅ Filled contenteditable field '{field}' with value: {value}")
                        break
                except Exception as e:
                    last_error = e
                    continue
            
            # Strategy 3: Try finding by text content and nearby contenteditable
            if not filled:
                try:
                    # Look for text that matches the field name, then find nearby contenteditable
                    field_text = field.replace('...', '').strip()
                    if field_text:
                        # Try to find element by text content, then find contenteditable nearby
                        text_locator = self.page.locator(f'text=/{field_text}/i')
                        if await text_locator.count() > 0:
                            # Find the first contenteditable element on the page
                            contenteditable = await self.page.query_selector('[contenteditable="true"]')
                            if contenteditable:
                                await contenteditable.click(timeout=timeout)
                                await asyncio.sleep(0.3)
                                import platform
                                select_all_key = "Meta+A" if platform.system() == "Darwin" else "Control+A"
                                await self.page.keyboard.press(select_all_key)
                                await asyncio.sleep(0.1)
                                await self.page.keyboard.type(value, delay=50)
                                await asyncio.sleep(0.2)
                                filled = True
                                self.logger.info(f"✅ Filled contenteditable field (found by text) '{field}' with value: {value}")
                except Exception as e:
                    last_error = e
        
        if not filled:
            error_msg = f"Could not find field '{field}'. Last error: {last_error}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
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
    
    async def perform(self, action: Dict[str, Any]) -> bool:
        """
        Perform an action based on action dictionary.
        
        Args:
            action: Action dictionary with 'action' and 'target' keys
        
        Returns:
            True if navigation occurred (for click actions), False otherwise
        """
        action_type = action.get("action")
        target = action.get("target")
        value = action.get("value")
        
        if action_type == "click":
            # For clicks, we want to wait for navigation, but it's okay if no navigation occurs
            # (for modals, dropdowns, etc.)
            try:
                navigation_occurred = await self.click(text=target, wait_for_navigation=True)
                return navigation_occurred
            except Exception as e:
                # If click failed, log it but don't fail silently
                self.logger.error(f"Click action failed: {e}")
                raise
        elif action_type == "fill":
            await self.fill(field=target, value=value)
            return False
        elif action_type == "navigate":
            await self.navigate(target)
            return True
        elif action_type == "wait":
            await asyncio.sleep(value or 1)
            return False
        else:
            raise ValueError(f"Unknown action type: {action_type}")

