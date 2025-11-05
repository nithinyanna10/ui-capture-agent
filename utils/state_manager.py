"""State management for tracking task execution steps."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class StateManager:
    """Manages state persistence for UI capture agent tasks."""
    
    def __init__(self, task_name: str, data_dir: str = "data"):
        """
        Initialize state manager for a task.
        
        Args:
            task_name: Name of the task (e.g., "linear_create_project")
            data_dir: Base directory for storing task data
        """
        self.task_name = task_name
        self.data_dir = Path(data_dir) / task_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.data_dir / "metadata.json"
        self.steps: List[Dict[str, Any]] = []
        self.load_state()
    
    def load_state(self) -> None:
        """Load existing state from metadata.json if it exists."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    self.steps = data.get('steps', [])
            except Exception as e:
                print(f"Warning: Could not load state: {e}")
                self.steps = []
        else:
            self.steps = []
    
    def save_step(
        self,
        step: int,
        url: str,
        screenshot_path: str,
        description: str,
        action_taken: Optional[str] = None,
        vision_data: Optional[Dict[str, Any]] = None,
        reasoning_data: Optional[Dict[str, Any]] = None,
        dom_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save a step to the state.
        
        Args:
            step: Step number
            url: Current URL
            screenshot_path: Path to screenshot
            description: Description of the UI state
            action_taken: Action that was performed
            vision_data: Vision agent output
            reasoning_data: Reasoning agent output
            dom_data: DOM extraction data
        """
        step_data = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "screenshot": screenshot_path,
            "description": description,
            "action_taken": action_taken,
            "vision_data": vision_data,
            "reasoning_data": reasoning_data,
            "dom_data": dom_data
        }
        
        # Update or append step
        if step < len(self.steps):
            self.steps[step] = step_data
        else:
            self.steps.append(step_data)
        
        self._persist()
    
    def _persist(self) -> None:
        """Persist current state to metadata.json."""
        metadata = {
            "task_name": self.task_name,
            "created_at": self.steps[0]["timestamp"] if self.steps else datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total_steps": len(self.steps),
            "steps": self.steps
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def get_last_step(self) -> Optional[Dict[str, Any]]:
        """Get the last saved step."""
        return self.steps[-1] if self.steps else None
    
    def get_step(self, step: int) -> Optional[Dict[str, Any]]:
        """Get a specific step by number."""
        if 0 <= step < len(self.steps):
            return self.steps[step]
        return None
    
    def get_all_steps(self) -> List[Dict[str, Any]]:
        """Get all steps."""
        return self.steps.copy()

