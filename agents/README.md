# Buchwurm Agents - Agents Directory

This directory contains the individual LangGraph agents.

## Available Agents

- **buchwurm-plato**: Philosophical conversations with Plato
- **buchwurm-terry**: Witty conversations with Terry Pratchett
- **flashlit-images-agent**: Image generation agent
- **sample-react-agent**: Sample React pattern agent

## Running the Development Server

From this directory (`buchwurm-agents/agents`):

```bash
langgraph dev
```

This will start the LangGraph development server on `http://localhost:2024`

## Agent Configuration

Each agent is configured through its `langgraph.json` file and has its own:
- Agent implementation file (e.g., `plato-agent.py`)
- Character prompt file (e.g., `plato_prompt.py`)

## Character Prompts

Each agent has its personality defined in separate prompt files:
- `plato_prompt.py` - Plato's philosophical personality
- `terry_prompt.py` - Terry Pratchett's witty author personality

This allows for easy editing of character personalities without modifying the main agent code.

## Environment Variables

Make sure you have `.env` files in both:
- `buchwurm-agents/.env`
- `buchwurm-agents/agents/.env`

With your OpenAI API key:
```
OPENAI_API_KEY=your-api-key-here
``` 