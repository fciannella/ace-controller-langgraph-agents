from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langgraph.func import entrypoint, task
from langgraph.graph.message import add_messages
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.types import StreamWriter 
import asyncio
import os
import logging

# Import Plato's base prompt from separate file
try:
    from .ace_base_prompt import PLATO_PROMPT_BASE
except ImportError:
    # Fallback for different import contexts
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from ace_base_prompt import PLATO_PROMPT_BASE

openai_api_key = os.environ["OPENAI_API_KEY"]

# Set up logger for Plato agent base
logger = logging.getLogger("PlatoAgent_base")
logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)

prompt = PLATO_PROMPT_BASE

MODEL_NAME = "gpt-4o"

llm = ChatOpenAI(model=MODEL_NAME, streaming=True, api_key=openai_api_key)

chain = prompt | llm

@task
async def call_model(messages, assistant_name):
    """Call the model with the conversation history."""
    response = await chain.ainvoke({"messages": messages, "assistant_name": assistant_name})
    return response


### We don't need a checkpointer when we use langgraph cloud (dev)
@entrypoint()
async def agent(messages, previous, config=None, writer: StreamWriter = None):
    logger.info("=" * 60)
    logger.info("🏛️ PLATO AGENT BASE STARTED")
    logger.info("=" * 60)
    
    # Process configuration
    config = config or {}
    configurable = config.get("configurable", {})
    
    # Get assistant name from config (should be "Plato")
    assistant_name = configurable.get("assistant_name", "Plato")
    character_version = "base"  # Fixed version for this agent
    user_id = configurable.get("user_id", "unknown")
    
    logger.info(f"👤 Assistant Name: {assistant_name}")
    logger.info(f"🔢 Character Version: {character_version}")
    logger.info(f"👥 User ID: {user_id}")
    
    # DEBUG: Log the initial incoming messages
    logger.info(f"📥 INITIAL MESSAGES - Received {len(messages)} messages:")
    for i, msg in enumerate(messages):
        msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
        msg_content = msg.content if hasattr(msg, 'content') else str(msg)
        logger.debug(f"  {i+1}. [{msg_type}]: {msg_content}")
    
    # DEBUG: Log previous messages if they exist
    if previous is not None:
        logger.info(f"📚 PREVIOUS CONTEXT - Found {len(previous)} previous messages:")
        for i, msg in enumerate(previous):
            msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
            msg_content = msg.content if hasattr(msg, 'content') else str(msg)
            logger.debug(f"  {i+1}. [{msg_type}]: {msg_content}")
        
        logger.info("🔄 MERGING previous messages with current messages...")
        messages = add_messages(previous, messages)
        
        logger.debug(f"📋 AFTER MERGE - Total {len(messages)} messages:")
        for i, msg in enumerate(messages):
            msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
            msg_content = msg.content if hasattr(msg, 'content') else str(msg)
            logger.debug(f"  {i+1}. [{msg_type}]: {msg_content}")
    else:
        logger.info("📭 NO PREVIOUS CONTEXT - Starting fresh conversation")

    logger.info("🧠 CALLING MODEL with full conversation history...")
    
    # Generate response using the full conversation history
    llm_response = await call_model(messages, assistant_name)

    logger.info(f"✨ MODEL RESPONSE RECEIVED (v{character_version}):")
    logger.info(f"  Content: {llm_response.content}")
    logger.debug(f"  Type: {type(llm_response).__name__}")
    
    # Add the response to messages for saving
    if previous is not None:
        logger.info("💾 ADDING RESPONSE to conversation history...")
        final_messages = add_messages(messages, [llm_response])
        logger.debug(f"📦 FINAL CONVERSATION - Total {len(final_messages)} messages:")
        for i, msg in enumerate(final_messages):
            msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
            msg_content = msg.content if hasattr(msg, 'content') else str(msg)
            logger.debug(f"  {i+1}. [{msg_type}]: {msg_content}")
    else:
        final_messages = add_messages(messages, [llm_response])
        logger.info(f"📦 SAVING CONVERSATION - Total {len(final_messages)} messages")

    logger.info(f"🏛️ PLATO AGENT {character_version.upper()} COMPLETED")
    logger.info("=" * 60)

    ### The next iteration of previous will hold the final messages, the entrypoint will return the llm_response.
    return entrypoint.final(value=llm_response, save=final_messages)


# async def run_agent_streaming():
#     user_message = {"role": "user", "content": "What's the weather in san francisco?"}
#     print(user_message)

#     config = {
#         "configurable": {
#             "thread_id": "1",
#             "assistant_name": "Chris"  # Set default speaker
#         }
#     }
#     async for msg, metadata in agent.astream([user_message], config, stream_mode="messages"):
#         if msg.content:
#             print(msg.content, end="|", flush=True)


# if __name__ == "__main__":
#     asyncio.run(run_agent_streaming())
