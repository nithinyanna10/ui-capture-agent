"""Reasoning agent using cloud LLM via Ollama for task planning."""
import json
import requests
from typing import Dict, Any, Optional
from utils.logger import setup_logger


class ReasoningAgent:
    """Task planner using cloud LLM via Ollama."""
    
    def __init__(
        self,
        model: str = "deepseek-v3.1:671b-cloud",
        endpoint: str = "http://localhost:11434/api/generate",
        timeout: int = 60
    ):
        """
        Initialize reasoning agent.
        
        Args:
            model: Model name for Ollama
            endpoint: Ollama API endpoint
            timeout: Request timeout in seconds
        """
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.logger = setup_logger("reasoning_agent")
    
    def _parse_action(self, text: str) -> Dict[str, Any]:
        """
        Parse action from model response.
        
        Args:
            text: Response text that may contain JSON
        
        Returns:
            Parsed action dictionary
        """
        text = text.strip()
        
        # Try to extract JSON from response
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx + 1]
            try:
                action = json.loads(json_str)
                # Validate required fields
                if "action" in action:
                    return action
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse from text
        action = {
            "action": "unknown",
            "target": None,
            "value": None,
            "confidence": 0.5,
            "done": False,
            "reasoning": text
        }
        
        # Try to extract action keywords
        text_lower = text.lower()
        if "click" in text_lower:
            action["action"] = "click"
        elif "fill" in text_lower or "enter" in text_lower or "type" in text_lower:
            action["action"] = "fill"
        elif "navigate" in text_lower or "go to" in text_lower:
            action["action"] = "navigate"
        elif "done" in text_lower or "complete" in text_lower or "finished" in text_lower:
            action["done"] = True
        
        return action
    
    def plan_next(
        self,
        task_description: str,
        vision_state: Dict[str, Any],
        previous_steps: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Plan next action based on task and current UI state.
        
        Args:
            task_description: Natural language task description
            vision_state: Current UI state from vision agent
            previous_steps: List of previous steps (optional)
        
        Returns:
            Structured action dictionary
        """
        self.logger.info("Planning next action...")
        
        # Build context from previous steps
        context = ""
        if previous_steps:
            context = "\nPrevious steps:\n"
            for step in previous_steps[-3:]:  # Last 3 steps for context
                context += f"- Step {step.get('step', '?')}: {step.get('action_taken', 'N/A')}\n"
        
        # Build prompt
        available_buttons = [b if isinstance(b, str) else b.get('text', '') for b in vision_state.get('buttons', [])]
        available_fields = [f if isinstance(f, str) else f.get('label', f.get('placeholder', '')) for f in vision_state.get('fields', [])]
        
        prompt = f"""You are a web automation agent. Your task is: {task_description}

IMPORTANT RULES:
1. You can ONLY interact with elements that are currently visible on the page
2. You MUST click buttons/links FIRST to navigate before filling forms
3. You can ONLY fill fields that are currently visible in the "Fields" list below
4. If no fields are visible, you must click a button to navigate to the form first
5. Follow logical flow: navigate → fill forms → submit
6. AVOID clicking OAuth buttons like "Continue with Google", "Sign in with GitHub", etc. - these cause redirects and break automation. Prefer email/password signup instead.
7. The order of filling is important. You must fill the username field first, then the password field, then click the sign in button.

Current UI State:
- Title: {vision_state.get('title', 'Unknown')}
- Available Buttons: {', '.join(available_buttons) if available_buttons else 'None'}
- Available Fields: {', '.join(available_fields) if available_fields else 'None'}
- Main Content: {vision_state.get('text_content', '')[:200]}

{context}

Determine the next action to take. CRITICAL: Only use buttons/fields that are listed above as "Available".

Return your response as JSON with this structure:
{{
  "action": "click" | "fill" | "navigate" | "wait" | "done",
  "target": "element text that MUST be in Available Buttons/Fields list above",
  "value": "value to fill (if action is fill, and field must be in Available Fields)",
  "confidence": 0.0-1.0,
  "done": true/false,
  "reasoning": "brief explanation"
}}

If the task is complete, set "done" to true and "action" to "done".
Return ONLY valid JSON, no additional text."""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract response text
            if isinstance(result, dict):
                response_text = result.get("response", "")
            else:
                response_text = str(result)
            
            # Parse action from response
            action = self._parse_action(response_text)
            
            self.logger.info(f"Action planned: {action.get('action')} -> {action.get('target')}")
            return action
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error calling reasoning model: {e}")
            return {
                "action": "error",
                "target": None,
                "value": None,
                "confidence": 0.0,
                "done": False,
                "reasoning": f"Error: {str(e)}",
                "error": str(e)
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in reasoning agent: {e}")
            return {
                "action": "error",
                "target": None,
                "value": None,
                "confidence": 0.0,
                "done": False,
                "reasoning": f"Unexpected error: {str(e)}",
                "error": str(e)
            }

