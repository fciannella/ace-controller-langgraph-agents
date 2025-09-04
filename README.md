# ACE Controller LangGraph Agents

This repository contains LangGraph agents for the ACE controller project. The primary agent exposed locally is `ace-base-agent`.

## Agents

- `ace-base-agent`: A simple conversational agent (Plato-style base prompt) defined in `agents/ace_base_agent/ace_base_agent.py` and registered in `agents/langgraph.json`.

## Quick Start (Local Development)

### 1) Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Environment variables
Create `.env` files in both locations:
- `./.env`
- `./agents/.env`

At minimum, include your OpenAI API key:
```env
OPENAI_API_KEY=your-openai-key
```

### 4) Run the LangGraph dev server
From the `agents` directory:
```bash
cd agents
langgraph dev
```
The API will be available at `http://127.0.0.1:2024` and the registered graph id is `ace-base-agent`.

### 5) Talk to the agent from Python
Use the helper script at the repo root:
```bash
python talk_to_agent.py -i --stream-mode values
```
Tips:
- `--stream-mode values` prints final messages; use `updates` for token-by-token.
- The script persists a thread id in `saved_thread_id.txt` so the conversation continues across turns. Type `/reset` in interactive mode to start a new thread.
- You can set defaults via env vars: `STREAM_MODE`, `LANGGRAPH_BASE_URL`, `LANGGRAPH_ASSISTANT`, `USER_EMAIL`.

## Logging

The base agent uses Python `logging` with default level `INFO`. You can raise verbosity by setting the agent logger to `DEBUG` in code if needed.

## Docker (optional)

You can package the API with LangGraph's container tooling. From `agents/`:
```bash
langgraph build -t your-org/ace-agents:0.0.1 -t your-org/ace-agents:latest
```
Or generate a Dockerfile and build manually:
```bash
langgraph dockerfile Dockerfile.langgraph.api
docker build -f Dockerfile.langgraph.api -t your-org/ace-agents:0.0.1 -t your-org/ace-agents:latest .
```
Reference docs: https://langchain-ai.github.io/langgraph/cloud/deployment/standalone_container/

## Project layout

- `agents/langgraph.json`: Graph registration for `ace-base-agent`
- `agents/ace_base_agent/`: Agent implementation and prompt
- `talk_to_agent.py`: Local Python client to interact with the agent
- `requirements.txt`: Python dependencies

