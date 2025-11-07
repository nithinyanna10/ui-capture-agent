# UI Capture Agent

An intelligent web automation agent that uses vision models and reasoning agents to perform tasks on web applications.

## Architecture

The system consists of four main components:

1. **Web Agent** (`agents/web_agent.py`) - Playwright-based browser controller
2. **Vision Agent** (`agents/vision_agent.py`) - Qwen3-VL visual interpreter via Ollama
3. **Reasoning Agent** (`agents/reasoning_agent.py`) - Cloud LLM task planner via Ollama
4. **Orchestrator** (`agents/orchestrator.py`) - Pipeline controller coordinating the flow

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Setup Ollama

Ensure Ollama is running and you have the required models:

```bash
# Pull vision model
ollama pull qwen3-vl:4b

# Pull reasoning model
ollama pull gpt-oss120B
```

### 3. Configure Settings

Edit `configs/settings.yaml` to adjust:
- Model names
- API endpoints
- Browser settings
- Timeouts

## Usage

### Basic Usage

```bash
python main.py --task "Create a project in Linear" --url "https://linear.app"
```

### With Custom Task Name

```bash
python main.py \
  --task "Create a project in Linear" \
  --url "https://linear.app" \
  --task-name "linear_create_project"
```

### Command Line Arguments

- `--task`: Natural language task description (required)
- `--url`: Initial URL to start from (optional)
- `--task-name`: Custom task name for data storage (optional)
- `--config`: Path to configuration file (default: `configs/settings.yaml`)

## Data Flow

1. **Task Description** → Reasoning Agent plans initial action
2. **Web Agent** → Opens browser, navigates, captures screenshot
3. **Vision Agent** → Analyzes screenshot, returns structured UI description
4. **Reasoning Agent** → Plans next action based on UI state
5. **Web Agent** → Executes action
6. **State Manager** → Saves step data
7. **Loop** continues until task is complete or max steps reached

## Output

All task data is stored in `data/{task_name}/`:
- `step_XX.png` - Screenshots for each step
- `metadata.json` - Complete execution history with vision/reasoning data

## Example Output Structure

```
data/linear_create_project/
├── step_00.png
├── step_01.png
├── step_02_modal.png
└── metadata.json
```

The `metadata.json` contains:
- Task information
- Step-by-step execution history
- Vision agent descriptions
- Reasoning agent decisions
- DOM tree snapshots

## Components

### Web Agent

Provides browser automation:
- `navigate(url)` - Navigate to URL
- `capture_screenshot(path)` - Save screenshot
- `click(text/selector)` - Click element
- `fill(field, value)` - Fill form field
- `wait_for_modal(text)` - Wait for modal
- `get_dom_tree()` - Extract DOM structure

### Vision Agent

Analyzes screenshots:
- Takes screenshot path
- Returns structured JSON with:
  - Title
  - Buttons
  - Form fields
  - Links
  - Text content
  - Layout description

### Reasoning Agent

Plans actions:
- Receives task description + vision state
- Returns structured action:
  - `action`: click, fill, navigate, wait, done
  - `target`: element identifier
  - `value`: value for fill actions
  - `confidence`: confidence score
  - `done`: completion flag

### Orchestrator

Main execution loop:
- Coordinates all agents
- Manages step iteration
- Handles errors
- Saves state

## Configuration

See `configs/settings.yaml` for:
- Model configurations
- API endpoints
- Browser settings
- Timeouts and limits
- Logging configuration

## Manual Intervention

The agent supports **human-in-the-loop** functionality, allowing you to manually intervene when needed (e.g., entering email addresses, passwords, or other sensitive information).

### How It Works

1. **Automatic Pausing**: When the agent detects it needs to fill sensitive fields (email, password, username), it will automatically pause and wait for manual input.

2. **Manual Typing**: During the pause, you can:
   - Click on the browser window
   - Type your email, password, or any other information manually
   - The browser is fully interactive during this time

3. **Configuration**: In `configs/settings.yaml`:
   ```yaml
   task:
     manual_intervention:
       enabled: true        # Enable/disable manual intervention
       wait_on_fill: true  # Pause when filling sensitive fields
       wait_time: 30       # Seconds to wait for manual input
   ```

4. **Example Flow**:
   - Agent navigates to login page
   - Agent identifies email field
   - **Agent pauses** → You manually type your email
   - Agent continues and fills password (or you can type that too)
   - Agent proceeds with the task

### Tips

- The browser window stays open and interactive during execution
- You can manually click, type, or interact at any time
- The agent will continue after the wait time expires
- For best results, type during the pause period when prompted

## Troubleshooting

1. **Ollama connection errors**: Ensure Ollama is running on `localhost:11434`
2. **Model not found**: Pull required models using `ollama pull <model-name>`
3. **Browser errors**: Run `playwright install chromium`
4. **Timeout errors**: Increase timeout values in `configs/settings.yaml`
5. **405 Method Not Allowed in Chrome**: This is normal - Ollama API requires POST requests, not GET. The browser will show 405, but the agent works fine.

