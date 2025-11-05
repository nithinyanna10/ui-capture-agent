"""Vision agent using Qwen3-VL via Ollama for UI description."""
import base64
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import setup_logger


class VisionAgent:
    """Visual interpreter using Qwen3-VL model via Ollama."""
    
    def __init__(
        self,
        model: str = "qwen3-vl:4b",
        endpoint: str = "http://localhost:11434/api/generate",
        timeout: int = 180,
        retry_attempts: int = 2,
        retry_delay: int = 5
    ):
        """
        Initialize vision agent.
        
        Args:
            model: Model name for Ollama
            endpoint: Ollama API endpoint
            timeout: Request timeout in seconds (default: 180 for vision models)
            retry_attempts: Number of retry attempts on timeout
            retry_delay: Delay in seconds between retries
        """
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.logger = setup_logger("vision_agent")
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode image to base64.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from model response text.
        
        Args:
            text: Response text that may contain JSON
        
        Returns:
            Parsed JSON dictionary
        """
        # Try to extract JSON from the response
        text = text.strip()
        
        # Find JSON object boundaries
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # If JSON parsing fails, return a structured description
        return {
            "description": text,
            "raw_response": text
        }
    
    def describe_ui(self, image_path: str) -> Dict[str, Any]:
        """
        Describe UI from screenshot in structured JSON format.
        
        Args:
            image_path: Path to screenshot
        
        Returns:
            Structured JSON description of the UI
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        self.logger.info(f"Describing UI from: {image_path}")
        
        # Encode image
        b64_image = self._encode_image(image_path)
        
        # Create prompt for structured UI description
        prompt = """Analyze this web UI screenshot and describe it precisely in JSON format. Include:
- title: Page title or main heading
- buttons: List of all visible buttons with their text
- fields: List of all form fields (inputs, textareas) with labels/placeholders
- links: List of clickable links
- text_content: Main text content visible on the page
- layout: Description of the page layout
- interactive_elements: List of all interactive elements

Return ONLY valid JSON, no additional text."""

        # Prepare request - use /api/chat for vision models (more reliable)
        # Convert endpoint from /api/generate to /api/chat if needed
        chat_endpoint = self.endpoint.replace("/api/generate", "/api/chat")
        
        # For Ollama chat API with vision models, images can be passed in content array
        # Format: content can be a string or array with text and image data
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_image]  # Images as separate field (Ollama supports this)
                }
            ],
            "stream": False
        }
        
        # Retry logic for timeout errors
        last_error = None
        for attempt in range(self.retry_attempts + 1):
            try:
                self.logger.info(f"Vision model request (attempt {attempt + 1}/{self.retry_attempts + 1})...")
                response = requests.post(
                    chat_endpoint,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Extract response text from chat API format
                if isinstance(result, dict):
                    # Chat API returns message.content
                    message = result.get("message", {})
                    if isinstance(message, dict):
                        response_text = message.get("content", "")
                    else:
                        # Fallback for generate API format
                        response_text = result.get("response", "")
                else:
                    response_text = str(result)
                
                # Parse JSON from response
                ui_description = self._parse_json(response_text)
                
                # Ensure required fields exist
                ui_description.setdefault("title", "")
                ui_description.setdefault("buttons", [])
                ui_description.setdefault("fields", [])
                ui_description.setdefault("links", [])
                ui_description.setdefault("text_content", "")
                ui_description.setdefault("layout", "")
                ui_description.setdefault("interactive_elements", [])
                
                self.logger.info(f"UI description completed: {ui_description.get('title', 'Unknown')}")
                return ui_description
                
            except requests.exceptions.Timeout as e:
                last_error = e
                self.logger.warning(f"Vision model timeout (attempt {attempt + 1}/{self.retry_attempts + 1}): {e}")
                if attempt < self.retry_attempts:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Vision model timed out after {self.retry_attempts + 1} attempts")
                    return {
                        "title": "Timeout Error",
                        "buttons": [],
                        "fields": [],
                        "links": [],
                        "text_content": f"Vision model timeout after {self.timeout}s (tried {self.retry_attempts + 1} times). Model may be too slow or image too large.",
                        "layout": "unknown",
                        "interactive_elements": [],
                        "error": f"Timeout: {str(e)}"
                    }
            except requests.exceptions.RequestException as e:
                last_error = e
                self.logger.error(f"Error calling vision model: {e}")
                # Return fallback description for non-timeout errors
                return {
                    "title": "Error",
                    "buttons": [],
                    "fields": [],
                    "links": [],
                    "text_content": f"Error describing UI: {str(e)}",
                    "layout": "unknown",
                    "interactive_elements": [],
                    "error": str(e)
                }
            except Exception as e:
                last_error = e
                self.logger.error(f"Unexpected error in vision agent: {e}")
                return {
                    "title": "Error",
                    "buttons": [],
                    "fields": [],
                    "links": [],
                    "text_content": f"Unexpected error: {str(e)}",
                    "layout": "unknown",
                    "interactive_elements": [],
                    "error": str(e)
                }
        
        # Should not reach here, but just in case
        return {
            "title": "Error",
            "buttons": [],
            "fields": [],
            "links": [],
            "text_content": f"Failed after all retries: {str(last_error)}",
            "layout": "unknown",
            "interactive_elements": [],
            "error": str(last_error) if last_error else "Unknown error"
        }

