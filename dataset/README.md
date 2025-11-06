# UI Capture Agent Dataset

This dataset contains captured UI states from automated task execution across multiple web applications, demonstrating a generalizable multi-agent system for web automation.

## Overview

The UI Capture Agent uses:
- **Vision Agent** (Qwen3-VL) to interpret UI screenshots
- **Reasoning Agent** (GPT-OSS) to plan actions based on task descriptions
- **Web Agent** (Playwright) to interact with web applications

The system captures **both URL-based and non-URL-based UI states** (modals, forms, dropdowns) in real-time, making it applicable to any web application without prior knowledge.

## Tasks

### 1. Enter Notion To-Do List and Add Task
**Status**: ✅ Completed (11 steps)  
**Location**: `enter_notion_on_the_to_do_list/`

**Task**: "Go to Notion on the to-do list, add task called 'test', and then go to settings, and change start week on Monday"

**Highlights**:
- ✅ Captures multiple non-URL UI states (modals, forms)
- ✅ Handles contenteditable divs (Notion's task name fields)
- ✅ Complex multi-step workflow (navigation, form filling, settings)
- ✅ Demonstrates real-time adaptation to Notion's interface

See `enter_notion_on_the_to_do_list/README.md` for detailed breakdown.

### 2. Create Project in Linear
**Status**: ✅ Completed (7 steps)  
**Location**: `create_project_in_linear/`

**Task**: "Create a new project in Linear called Test Project"

**Highlights**:
- ✅ Cross-app generalizability (Linear is different from Notion)
- ✅ Standard HTML input fields (faster than contenteditable)
- ✅ Icon-based button detection
- ✅ Multiple non-URL states captured (modals, settings panels, view changes)
- ✅ Demonstrates system works across different web app architectures

See `create_project_in_linear/README.md` for detailed breakdown.

## Dataset Structure

Each task folder contains:

```
{task_name}/
├── step_00.png          # Screenshot at step 0
├── step_01.png          # Screenshot at step 1
├── ...
├── steps.jsonl          # Concise per-step logs (image path, action, buttons, reasoning, status)
├── summary.json         # Run summary (completed, total steps, error)
├── metadata.json        # Complete execution history (vision/reasoning data, DOM)
├── report.pdf           # PDF report with embedded images and step details
└── README.md            # Task-specific documentation
```

## Key Features Demonstrated

### 1. Non-URL State Capture
The system successfully captures UI states that don't have unique URLs:
- **Modals**: After clicking buttons, modals appear (captured even when URL doesn't change)
- **Forms**: Form fields and input states are captured
- **Dropdowns**: UI changes from dropdowns are captured

### 2. Generalizability
- **No hardcoded tasks**: All tasks are described in natural language
- **Works across apps**: Tested on Notion, GitHub, and Linear
- **Real-time adaptation**: The reasoning agent plans actions based on current UI state
- **No prior knowledge**: System learns the UI structure as it goes

### 3. Comprehensive Logging
Each task includes:
- **Screenshots**: Visual state at each step
- **JSONL logs**: Concise step-by-step logs with:
  - Action taken (click, fill, navigate, etc.)
  - Target element
  - Buttons visible in UI
  - LLM reasoning for the action
  - Success/failure status
- **PDF reports**: Human-readable reports with embedded images
- **Metadata**: Complete execution history for analysis

## Technical Details

### Vision Agent
- **Model**: Qwen3-VL:8b (via Ollama)
- **Output**: Structured JSON describing UI elements (buttons, fields, text, layout)

### Reasoning Agent  
- **Model**: GPT-OSS:120b-cloud (via Ollama)
- **Output**: Next action to perform (click, fill, navigate, wait, done)

### Web Agent
- **Tool**: Playwright
- **Features**: 
  - Browser automation
  - Screenshot capture
  - DOM extraction
  - Session persistence (for logged-in states)
  - Support for contenteditable divs, checkboxes, modals

## Usage

To run a task:

```bash
python main.py --task "Your task description" --url "https://app-url.com"
```

The system will:
1. Navigate to the URL
2. Capture screenshots at each step
3. Analyze UI state with vision model
4. Plan next action with reasoning model
5. Execute action
6. Repeat until task complete or max steps reached

## Output Files Explained

### steps.jsonl
One JSON object per line, containing:
- `step`: Step number
- `timestamp`: When the step occurred
- `url`: Current page URL
- `image`: Path to screenshot
- `action`: Action taken (click, fill, navigate, etc.)
- `target`: What element was targeted
- `buttons`: List of buttons visible in UI
- `status`: success, pending, or failure
- `reasoning`: LLM's reasoning for the action

### summary.json
Overall run summary:
- Task name
- Start/finish times
- Completion status
- Total steps
- Error (if any)
- Last step data

### report.pdf
Human-readable PDF with:
- Embedded screenshots
- Step-by-step details
- Actions taken
- Reasoning for each step

### metadata.json
Complete execution history:
- Full vision agent descriptions
- Full reasoning agent plans
- DOM tree snapshots
- Complete step-by-step data

## Notes

- The system is designed to be **generalizable** - it doesn't rely on hardcoded task knowledge
- It handles **both URL and non-URL UI states** through intelligent screenshot capture
- Session persistence allows reusing logged-in browser sessions
- The system can handle authentication flows, OAuth redirects, and complex interactions
- Supports modern web apps with contenteditable divs, ARIA roles, and dynamic UI

