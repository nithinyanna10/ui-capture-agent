"""Orchestrator for coordinating the UI capture agent pipeline."""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from agents.web_agent import WebAgent
from agents.vision_agent import VisionAgent
from agents.reasoning_agent import ReasoningAgent
from utils.state_manager import StateManager
from utils.run_recorder import RunRecorder
from utils.pdf_report import generate_run_pdf
from utils.logger import setup_logger


class Orchestrator:
    """Pipeline controller for UI capture agent."""
    
    def __init__(
        self,
        task_name: str,
        web_agent: WebAgent,
        vision_agent: VisionAgent,
        reasoning_agent: ReasoningAgent,
        state_manager: StateManager,
        max_steps: int = 50,
        wait_timeout: int = 5000,
        credentials: Optional[Dict[str, str]] = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            task_name: Name of the task
            web_agent: Web agent instance
            vision_agent: Vision agent instance
            reasoning_agent: Reasoning agent instance
            state_manager: State manager instance
            max_steps: Maximum number of steps before stopping
            wait_timeout: Wait timeout in milliseconds
            credentials: Optional dict with 'email' and 'password' for auto-filling
        """
        self.task_name = task_name
        self.web_agent = web_agent
        self.vision_agent = vision_agent
        self.reasoning_agent = reasoning_agent
        self.state_manager = state_manager
        self.max_steps = max_steps
        self.wait_timeout = wait_timeout
        self.credentials = credentials or {}
        self.logger = setup_logger("orchestrator")
    
    async def run_task(self, task_description: str, initial_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete task execution pipeline.
        
        Args:
            task_description: Natural language task description
            initial_url: Optional initial URL to start from
        
        Returns:
            Final result dictionary
        """
        self.logger.info(f"Starting task: {task_description}")
        
        # Navigate to initial URL if provided
        if initial_url:
            await self.web_agent.navigate(initial_url)
            await asyncio.sleep(2)  # Wait for page to load
        
        # Track original domain to detect OAuth redirects
        if initial_url:
            original_domain = urlparse(initial_url).netloc
        else:
            original_domain = None
        
        step = 0
        done = False
        error = None
        oauth_detected = False
        recorder = RunRecorder(self.task_name)
        
        try:
            # Track if we already captured a screenshot in this iteration (for non-navigation clicks)
            screenshot_already_captured = False
            
            while step < self.max_steps and not done:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Step {step + 1}/{self.max_steps}")
                self.logger.info(f"{'='*60}")
                
                # Capture screenshot at the start of each step (unless we just captured one after a click)
                if not screenshot_already_captured:
                    screenshot_path = f"data/{self.task_name}/step_{step:02d}.png"
                    self.logger.info(f"Capturing screenshot: {screenshot_path}")
                    img_path = await self.web_agent.capture_screenshot(screenshot_path)
                    self.logger.info(f"Screenshot captured: {img_path}")
                else:
                    # Use the screenshot we just captured after the click
                    screenshot_path = f"data/{self.task_name}/step_{step:02d}.png"
                    img_path = screenshot_path
                    screenshot_already_captured = False  # Reset flag
                    self.logger.info(f"Using screenshot captured after action: {img_path}")
                
                # Get current URL and DOM
                current_url = await self.web_agent.get_current_url()
                
                # Detect OAuth redirects (Google, GitHub, etc.)
                current_domain = urlparse(current_url).netloc
                oauth_domains = ['accounts.google.com', 'github.com', 'oauth', 'login.microsoftonline.com', 'appleid.apple.com']
                is_oauth_page = any(oauth in current_domain.lower() for oauth in oauth_domains)
                
                # Check if we're on OAuth page and need to wait for redirect back
                if is_oauth_page and original_domain:
                    self.logger.warning(f"Detected OAuth redirect to {current_domain}. Waiting for redirect back to {original_domain}...")
                    oauth_detected = True
                    # Wait for redirect back to original domain
                    for wait_attempt in range(10):  # Wait up to 10 seconds
                        await asyncio.sleep(1)
                        current_url = await self.web_agent.get_current_url()
                        current_domain = urlparse(current_url).netloc
                        if original_domain in current_domain or not any(oauth in current_domain.lower() for oauth in oauth_domains):
                            self.logger.info(f"Redirected back to {current_domain}")
                            oauth_detected = False
                            break
                    if oauth_detected:
                        self.logger.error("Still on OAuth page after waiting. Manual intervention may be needed.")
                        error = f"Stuck on OAuth page: {current_domain}. Please complete authentication manually."
                        break
                
                dom_data = await self.web_agent.get_dom_tree()
                
                # Skip vision/reasoning if we're on OAuth page (waiting for redirect)
                if oauth_detected:
                    self.logger.info("Skipping action on OAuth page, waiting for redirect...")
                    step += 1
                    continue
                
                # Vision agent describes UI
                vision_data = self.vision_agent.describe_ui(img_path)
                
                # Reasoning agent plans next action
                previous_steps = self.state_manager.get_all_steps()
                reasoning_data = self.reasoning_agent.plan_next(
                    task_description,
                    vision_data,
                    previous_steps
                )
                
                # Check if task is done
                done = reasoning_data.get("done", False)
                action = reasoning_data.get("action", "unknown")
                
                # Save step to state
                self.state_manager.save_step(
                    step=step,
                    url=current_url,
                    screenshot_path=img_path,
                    description=vision_data.get("title", "Unknown UI"),
                    action_taken=f"{action}: {reasoning_data.get('target', 'N/A')}",
                    vision_data=vision_data,
                    reasoning_data=reasoning_data,
                    dom_data=dom_data
                )

                # Lightweight step log
                try:
                    buttons = [
                        b if isinstance(b, str) else b.get("text", "")
                        for b in vision_data.get("buttons", [])
                    ]
                    recorder.record_step(
                        step=step,
                        url=current_url,
                        image_path=img_path,
                        action=action,
                        target=reasoning_data.get("target"),
                        buttons=buttons,
                        status="pending",
                        reasoning=reasoning_data.get("reasoning"),
                    )
                except Exception:
                    # Do not fail run due to logging
                    pass
                
                if done:
                    self.logger.info("Task completed!")
                    break
                
                # Perform action
                if action == "error":
                    error = reasoning_data.get("error", "Unknown error")
                    self.logger.error(f"Action error: {error}")
                    break
                
                try:
                    # Auto-fill credentials if action is fill and credentials are available
                    action_type = action.lower()
                    action_target = reasoning_data.get("target", "").lower()
                    
                    if action_type == "fill" and self.credentials:
                        # Check if it's an email field
                        if any(keyword in action_target for keyword in ["email", "e-mail", "username", "user name"]):
                            if self.credentials.get("email"):
                                reasoning_data["value"] = self.credentials["email"]
                                self.logger.info("Auto-filling email from credentials")
                        # Check if it's a password field
                        elif "password" in action_target:
                            if self.credentials.get("password"):
                                reasoning_data["value"] = self.credentials["password"]
                                self.logger.info("Auto-filling password from credentials")
                    
                    self.logger.info(f"Performing action: {action} -> {reasoning_data.get('target')}")
                    
                    # Store URL before action to detect changes
                    url_before_action = await self.web_agent.get_current_url()
                    
                    try:
                        navigation_occurred = await self.web_agent.perform(reasoning_data)
                        self.logger.info(f"✅ Action executed successfully. Navigation occurred: {navigation_occurred}")
                    except Exception as click_error:
                        self.logger.error(f"❌ Action failed: {click_error}")
                        # Mark as failure
                        try:
                            recorder.record_step(
                                step=step,
                                url=url_before_action,
                                image_path=img_path,
                                action=action,
                                target=reasoning_data.get("target"),
                                buttons=buttons if 'buttons' in locals() else [],
                                status="failure",
                                reasoning=f"Action failed: {str(click_error)}",
                            )
                        except Exception:
                            pass
                        raise  # Re-raise to be caught by outer exception handler
                    
                    # Wait for UI to update after any action
                    if navigation_occurred:
                        # Wait longer after navigation (page change)
                        self.logger.info("Waiting for page to load after navigation...")
                        await asyncio.sleep(2)
                        # Update current URL after navigation
                        current_url = await self.web_agent.get_current_url()
                        self.logger.info(f"New URL after navigation: {current_url}")
                    else:
                        # For clicks that don't cause navigation (modals, dropdowns, etc.)
                        # ALWAYS take a screenshot after non-navigation clicks to capture UI changes
                        if action_type == "click":
                            self.logger.info("Click did not cause navigation. Waiting for UI to update (modal, form, etc.)...")
                            
                            # Wait a bit for UI to update
                            await asyncio.sleep(2)  # Base wait for UI to update
                            
                            # Try to detect if a modal or form appeared (but don't fail if we can't detect it)
                            ui_changed = False
                            try:
                                # Check for common modal/form indicators
                                modal_selectors = [
                                    '[role="dialog"]',
                                    '.modal',
                                    '[class*="modal"]',
                                    '[class*="dialog"]',
                                    'form',
                                    '[role="form"]',
                                    '[class*="overlay"]',
                                    '[class*="popup"]'
                                ]
                                for selector in modal_selectors:
                                    try:
                                        await self.web_agent.page.wait_for_selector(
                                            selector,
                                            timeout=2000,
                                            state="visible"
                                        )
                                        self.logger.info(f"✅ Detected UI change after click: {selector} appeared")
                                        ui_changed = True
                                        await asyncio.sleep(1)  # Extra wait for modal to fully render
                                        break
                                    except Exception:
                                        continue
                            except Exception as e:
                                self.logger.debug(f"Could not detect UI change: {e}")
                            
                            if not ui_changed:
                                self.logger.info("⚠️  No modal/form detected, but taking screenshot anyway to capture any UI changes...")
                            
                            # IMPORTANT: ALWAYS take a new screenshot after non-navigation clicks
                            # This ensures we capture modals, forms, and other UI changes
                            step += 1  # Increment step first to get the next screenshot number
                            new_screenshot_path = f"data/{self.task_name}/step_{step:02d}.png"
                            self.logger.info(f"📸 Capturing updated UI screenshot: {new_screenshot_path}")
                            
                            try:
                                new_img_path = await self.web_agent.capture_screenshot(new_screenshot_path)
                                self.logger.info(f"✅ Updated screenshot captured: {new_img_path}")
                                
                                # Mark that we already captured a screenshot for the next iteration
                                screenshot_already_captured = True
                                
                                # Update current URL (might have changed even if navigation_occurred was False)
                                current_url = await self.web_agent.get_current_url()
                                
                                # Log this step with the updated UI
                                try:
                                    # Quick vision analysis for logging
                                    updated_vision_data = self.vision_agent.describe_ui(new_img_path)
                                    updated_buttons = [
                                        b if isinstance(b, str) else b.get("text", "")
                                        for b in updated_vision_data.get("buttons", [])
                                    ]
                                    recorder.record_step(
                                        step=step,
                                        url=current_url,
                                        image_path=new_img_path,
                                        action="ui_updated",
                                        target=f"After clicking: {reasoning_data.get('target')}",
                                        buttons=updated_buttons,
                                        status="success",
                                        reasoning=f"UI updated after clicking {reasoning_data.get('target')}. New state captured.",
                                    )
                                    self.logger.info(f"✅ Step {step} logged with updated UI state")
                                except Exception as log_error:
                                    self.logger.warning(f"Could not log updated step: {log_error}")
                                
                                # Continue to next iteration - it will use the screenshot we just captured
                                await asyncio.sleep(0.5)
                                self.logger.info(f"🔄 Step {step} screenshot captured. Loop will continue to analyze this state...")
                                continue  # Skip the normal increment at the end since we already incremented
                            except Exception as screenshot_error:
                                self.logger.error(f"❌ Failed to capture screenshot after click: {screenshot_error}")
                                # Don't break, just continue normally
                    
                    # Mark as success in lightweight log
                    try:
                        recorder.record_step(
                            step=step,
                            url=current_url,
                            image_path=img_path,
                            action=action,
                            target=reasoning_data.get("target"),
                            buttons=buttons if 'buttons' in locals() else [],
                            status="success" if navigation_occurred or action_type != "click" else "pending",
                            reasoning=reasoning_data.get("reasoning"),
                        )
                    except Exception:
                        pass

                    await asyncio.sleep(0.5)  # Brief pause before next iteration
                    self.logger.info(f"Step {step + 1} completed. Moving to next step...")
                except Exception as e:
                    self.logger.error(f"Error performing action: {e}")
                    error = str(e)
                    # Mark as failure in lightweight log
                    try:
                        recorder.record_step(
                            step=step,
                            url=current_url,
                            image_path=img_path,
                            action=action,
                            target=reasoning_data.get("target"),
                            buttons=buttons if 'buttons' in locals() else [],
                            status="failure",
                            reasoning=reasoning_data.get("reasoning"),
                        )
                    except Exception:
                        pass
                    break
                
                step += 1
                self.logger.info(f"Incrementing step to {step + 1}. Loop will continue...")
            
            if step >= self.max_steps:
                self.logger.warning(f"Reached maximum steps ({self.max_steps})")
            
            result = {
                "task": task_description,
                "completed": done,
                "steps": step + 1,
                "error": error,
                "final_state": self.state_manager.get_last_step()
            }
            # Write concise summary
            try:
                recorder.write_summary(completed=done, error=error)
            except Exception:
                pass

            # Generate PDF report
            try:
                generate_run_pdf(self.task_name)
            except Exception:
                pass

            return result
            
        except Exception as e:
            self.logger.error(f"Fatal error in orchestrator: {e}")
            return {
                "task": task_description,
                "completed": False,
                "steps": step + 1,
                "error": str(e),
                "final_state": None
            }

