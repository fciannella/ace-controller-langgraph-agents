# Buchwurm Agents

This directory contains the LangGraph agents for the Buchwurm project.

## Agents

- **buchwurm-plato**: Philosophical conversations with Plato
- **buchwurm-terry**: Witty conversations with Terry Pratchett
- **flashlit-images-agent**: Image generation agent
- **sample-react-agent**: Sample React pattern agent

## Quick Start (Development)

### 1. Setup Virtual Environment
From the `buchwurm-agents` directory:

```bash
# Create virtual environment using uv
uv venv

# Activate the virtual environment
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create `.env` files in both:
- `buchwurm-agents/.env`
- `buchwurm-agents/agents/.env`

Include your OpenAI API key:
```
OPENAI_API_KEY=your-api-key-here
```

### 4. Start the LangGraph Development Server
From the `buchwurm-agents/agents` directory:

```bash
cd agents
langgraph dev
```

The agents will be available at `http://localhost:2024`

## Logging Configuration

Both the Plato and Terry agents use Python's `logging` module for better debugging and monitoring. The logging is configured with:

- **Logger Names**: 
  - `PlatoAgent` for the Plato agent
  - `TerryAgent` for the Terry agent
- **Default Level**: `INFO`
- **Format**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### Log Levels Used

- `INFO`: General information about agent execution flow
- `DEBUG`: Detailed message content and debugging information 
- `WARNING`: Potential issues (not currently used)
- `ERROR`: Error conditions (not currently used)

### Adjusting Log Levels

To see more detailed logging (including message contents), you can set the log level to `DEBUG`:

```python
logger.setLevel(logging.DEBUG)
```

To see only warnings and errors:

```python
logger.setLevel(logging.WARNING)
```

## Character Prompts

Each agent has its personality defined in separate prompt files:
- `plato_prompt.py` - Plato's philosophical personality
- `terry_prompt.py` - Terry Pratchett's witty author personality

This allows for easy editing of character personalities without modifying the main agent code.

## Docker Deployment

We are following this link:

https://langchain-ai.github.io/langgraph/cloud/deployment/standalone_container/


## Create the image

You need to create an image first, so build your agent and then create its docker image.

We need to create the image inside the agents directory:

You can create the image using the langgraph command directly with these commands

```
cd agents
langgraph build -t author-space/buchwurm-agents:0.0.1 -t author-space/buchwurm-agents:latest
```

Or you can first generate a Dockerfile with `langgraph dockerfile Dockerfile.langgraph.api`, edit it as needed and then build the image

```
docker build -f Dockerfile.langgraph.api -t author-space/buchwurm-agents:0.0.1 -t author-space/buchwurm-agents:latest .
```


