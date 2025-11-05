"""Orchestrator for coordinating the UI capture agent pipeline."""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from agents.web_agent import WebAgent
from agents.vision_agent import VisionAgent
from agents.reasoning_agent import ReasoningAgent
from utils.state_manager import StateManager
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
        
        try:
            while step < self.max_steps and not done:
                self.logger.info(f"Step {step + 1}/{self.max_steps}")
                
                # Capture screenshot
                screenshot_path = f"data/{self.task_name}/step_{step:02d}.png"
                img_path = await self.web_agent.capture_screenshot(screenshot_path)
                
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
                    
                    await self.web_agent.perform(reasoning_data)
                    await asyncio.sleep(1)  # Brief pause between actions
                except Exception as e:
                    self.logger.error(f"Error performing action: {e}")
                    error = str(e)
                    break
                
                step += 1
            
            if step >= self.max_steps:
                self.logger.warning(f"Reached maximum steps ({self.max_steps})")
            
            result = {
                "task": task_description,
                "completed": done,
                "steps": step + 1,
                "error": error,
                "final_state": self.state_manager.get_last_step()
            }
            
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

