"""Main entrypoint for UI Capture Agent."""
import asyncio
import yaml
import argparse
from pathlib import Path
from agents.web_agent import WebAgent
from agents.vision_agent import VisionAgent
from agents.reasoning_agent import ReasoningAgent
from agents.orchestrator import Orchestrator
from utils.state_manager import StateManager
from utils.logger import setup_logger


def load_config(config_path: str = "configs/settings.yaml") -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
    
    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="UI Capture Agent")
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="Task description (e.g., 'Create a project in Linear')"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Initial URL to start from"
    )
    parser.add_argument(
        "--task-name",
        type=str,
        help="Task name for data storage (default: auto-generated)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/settings.yaml",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup logging
    log_config = config.get("logging", {})
    logger = setup_logger(
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file"),
        format_string=log_config.get("format")
    )
    
    logger.info("Starting UI Capture Agent")
    
    # Generate task name if not provided
    task_name = args.task_name
    if not task_name:
        # Simple slug generation from task description
        task_name = args.task.lower().replace(" ", "_").replace("'", "").replace(",", "")[:30]
    
    # Initialize agents
    vision_config = config.get("vision", {})
    reasoning_config = config.get("reasoning", {})
    web_config = config.get("web", {})
    task_config = config.get("task", {})
    
    web_agent = WebAgent(
        browser_type=web_config.get("browser", "chromium"),
        headless=web_config.get("headless", False),
        viewport=web_config.get("viewport"),
        timeout=web_config.get("timeout", 30000),
        screenshot_path=web_config.get("screenshot_path", "data"),
        session_persistence=web_config.get("session_persistence", {})
    )
    
    vision_agent = VisionAgent(
        model=vision_config.get("model", "qwen3-vl:4b"),
        endpoint=vision_config.get("endpoint", "http://localhost:11434/api/generate"),
        timeout=vision_config.get("timeout", 180),
        retry_attempts=vision_config.get("retry_attempts", 2),
        retry_delay=vision_config.get("retry_delay", 5)
    )
    
    reasoning_agent = ReasoningAgent(
        model=reasoning_config.get("model", "deepseek-v3.1:671b-cloud"),
        endpoint=reasoning_config.get("endpoint", "http://localhost:11434/api/generate"),
        timeout=reasoning_config.get("timeout", 60)
    )
    
    state_manager = StateManager(task_name, data_dir=web_config.get("screenshot_path", "data"))
    
    # Load credentials from config
    credentials_config = config.get("credentials", {})
    credentials = {}
    if credentials_config.get("email"):
        credentials["email"] = credentials_config["email"]
    if credentials_config.get("password"):
        credentials["password"] = credentials_config["password"]
    
    orchestrator = Orchestrator(
        task_name=task_name,
        web_agent=web_agent,
        vision_agent=vision_agent,
        reasoning_agent=reasoning_agent,
        state_manager=state_manager,
        max_steps=task_config.get("max_steps", 50),
        wait_timeout=task_config.get("wait_timeout", 5000),
        credentials=credentials if credentials else None
    )
    
    try:
        # Start browser
        await web_agent.start()
        
        # Run task
        result = await orchestrator.run_task(args.task, initial_url=args.url)
        
        # Print results
        print("\n" + "="*50)
        print("Task Execution Summary")
        print("="*50)
        print(f"Task: {result['task']}")
        print(f"Completed: {result['completed']}")
        print(f"Steps: {result['steps']}")
        if result.get('error'):
            print(f"Error: {result['error']}")
        print("="*50)
        
        logger.info(f"Task execution completed: {result['completed']}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        await web_agent.stop()


if __name__ == "__main__":
    asyncio.run(main())

