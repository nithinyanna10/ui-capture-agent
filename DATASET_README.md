# UI Capture Agent Dataset

This dataset contains captured UI states from automated task execution across multiple web applications.

## Overview

The UI Capture Agent is a generalizable multi-agent system that uses:
- **Vision Agent** (Qwen3-VL) to interpret UI screenshots
- **Reasoning Agent** (GPT-OSS) to plan actions based on task descriptions
- **Web Agent** (Playwright) to interact with web applications

The system captures **both URL-based and non-URL-based UI states** (modals, forms, dropdowns) in real-time, making it applicable to any web application without prior knowledge.

## Dataset Structure

```
data/
├── {task_name}/
│   ├── step_00.png          # Screenshot at step 0
│   ├── step_01.png          # Screenshot at step 1
│   ├── ...
│   ├── steps.jsonl          # Concise per-step logs (image path, action, buttons, reasoning, status)
│   ├── summary.json         # Run summary (completed, total steps, error)
│   ├── metadata.json        # Complete execution history (vision/reasoning data, DOM)
│   └── report.pdf           # PDF report with embedded images and step details
```

## Tasks

### 1. Create a New Page in Notion
**Task**: "Create a new page in Notion"
**Status**: Partial completion (6 steps captured)
**Highlights**:
- ✅ Captures modal UI state (non-URL) after clicking "Add new"
- ✅ Demonstrates navigation through Notion's page creation flow
- ✅ Shows UI state changes without URL changes

**Steps captured**:
- Step 0: Initial Notion dashboard
- Step 1: Modal opened after clicking "Add new" (non-URL state)
- Step 2: New page editor opened
- Step 3-5: Page editing interactions

**Location**: `data/create_a_new_page_in_notion_an/`

### 2. Login to GitHub and Create Repository
**Task**: "Login to GitHub and create an empty repository"
**Status**: Partial completion (13 steps captured)
**Highlights**:
- ✅ Demonstrates authentication flow
- ✅ Captures form filling states
- ✅ Shows repository creation workflow

**Steps captured**:
- Multiple steps through GitHub login flow
- Form filling states
- Repository creation interface

**Location**: `data/login_to_github_and_create_an_/`

### 3. Create Project in Linear
**Task**: "Create a project in Linear"
**Status**: Initial attempt
**Highlights**:
- Demonstrates system works across different apps
- Shows generalizability

**Location**: `data/create_a_project_in_linear/`

## Key Features Demonstrated

### 1. Non-URL State Capture
The system successfully captures UI states that don't have unique URLs:
- **Modals**: After clicking "Add new" in Notion, a modal appears (captured in step_01.png)
- **Forms**: Form fields and input states are captured
- **Dropdowns**: UI changes from dropdowns are captured

### 2. Generalizability
- **No hardcoded tasks**: All tasks are described in natural language
- **Works across apps**: Tested on Notion, GitHub, and Linear
- **Real-time adaptation**: The reasoning agent plans actions based on current UI state

### 3. Comprehensive Logging
Each task includes:
- **Screenshots**: Visual state at each step
- **JSONL logs**: Concise step-by-step logs (actions, buttons seen, reasoning, status)
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

## Usage

To run a task:

```bash
python main.py --task "Create a new page in Notion" --url "https://www.notion.so"
```

The system will:
1. Navigate to the URL
2. Capture screenshots at each step
3. Analyze UI state with vision model
4. Plan next action with reasoning model
5. Execute action
6. Repeat until task complete or max steps reached

## Output Files

- **steps.jsonl**: One JSON object per line, containing:
  - `step`: Step number
  - `timestamp`: When the step occurred
  - `url`: Current page URL
  - `image`: Path to screenshot
  - `action`: Action taken (click, fill, navigate, etc.)
  - `target`: What element was targeted
  - `buttons`: List of buttons visible in UI
  - `status`: success, pending, or failure
  - `reasoning`: LLM's reasoning for the action

- **summary.json**: Overall run summary
- **report.pdf**: PDF with embedded images and step details
- **metadata.json**: Complete execution history with full vision/reasoning data

## Notes

- The system is designed to be **generalizable** - it doesn't rely on hardcoded task knowledge
- It handles **both URL and non-URL UI states** through intelligent screenshot capture
- Session persistence allows reusing logged-in browser sessions
- The system can handle authentication flows, OAuth redirects, and complex interactions

