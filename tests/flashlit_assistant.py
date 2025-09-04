import asyncio
import uuid
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage

# Use the same LangGraph cloud endpoint as in the flashlit_characters.py test
client = get_client(url="http://lg.flashlit.ai:8123")

# Configuration to be passed to the agent - based on the agent.py implementation
config = {
    "configurable": {
        "user_email": "francesco@flashlit.ai",
    }
}

# List of test questions from the agent.py main function
test_questions = [
    "Can you list the bad habits?",
    "Can you generate a calendar view of the express gratitude habit for the current month?",
    "Can you summarize this paper: https://arxiv.org/pdf/2412.15605",
    "Can you get the content of chapter 5 of the book the Singularity by Chalmers and show the content nicely?"
]

async def get_or_create_thread():
    """Get an existing thread or create a new one using the LangGraph SDK API"""
    # Create thread with metadata for tracking purposes
    thread = await client.threads.create(
        metadata={"created_by": "flashlit_assistant_test", "user_id": "francesco@flashlit.ai"}
    )
    # The thread is returned as a dictionary, not an object with attributes
    thread_id = thread['thread_id']
    print(f"Created new thread with ID: {thread_id}")
    return thread_id

async def run_question(question, thread_id=None):
    """Run a single question through the flashlit-assistant-agent"""
    print(f"\n\n=== Running question: {question} ===\n")
    
    # Create or get thread ID if not provided
    if thread_id is None:
        thread_id = await get_or_create_thread()
    
    # Format input as used in the agent.py main function
    async for chunk in client.runs.stream(
        thread_id,  # Using thread ID to maintain conversation context
        "flashlit-assistant-agent",  # Name of the agent
        input={"messages": ("user", question)},  # Format matches what agent_graph expects
        config=config,  # Pass the configuration
        stream_mode="updates",  # Using updates for more detailed streaming
    ):
        print(f"Receiving new event of type: {chunk.event}...")
        if hasattr(chunk.data, 'get') and chunk.data.get('messages'):
            message = chunk.data.get('messages', [])
            if isinstance(message, list) and message:
                message = message[-1]
                if hasattr(message, 'content') and message.content:
                    print(f"Content: {message.content}")
                elif hasattr(message, 'tool_calls') and message.tool_calls:
                    print(f"Tool calls: {message.tool_calls}")
        else:
            print(chunk.data)
        print("\n---\n")
    
    return thread_id

async def run_conversation():
    """Run a multi-turn conversation using the same thread"""
    # Create a new thread for this conversation
    thread_id = await get_or_create_thread()
    
    # Run a sequence of questions in the same thread
    questions = [
        "Can you list the bad habits?",
        "Tell me more about the first one",
        "Can you provide a calendar view for expressing gratitude in January 2025?",
        "Can you add a reminder for meditation every Monday?"
    ]
    
    for question in questions:
        print(f"\n\n=== Continuing conversation with question: {question} ===\n")
        thread_id = await run_question(question, thread_id)

async def run_all_questions():
    """Run all predefined test questions sequentially"""
    # Create a new thread for all questions
    thread_id = await get_or_create_thread()
    
    for question in test_questions:
        thread_id = await run_question(question, thread_id)

async def run_interactive_session():
    """Run an interactive session where the user can input questions"""
    print("\n\n=== Starting interactive session with flashlit-assistant-agent ===\n")
    print("Type 'exit' to end the session")
    
    # Create a thread for this interactive session
    thread_id = await get_or_create_thread()
    
    while True:
        user_question = input("\nEnter your question: ")
        if user_question.lower() == "exit":
            print("Ending session...")
            break
        thread_id = await run_question(user_question, thread_id)

# This is the main entry point for the script
async def async_main():
    """Async main function to run the script"""
    # Uncomment one of the options below:
    
    # Option 1: Run a single question with a new thread
    # await run_question("Can you provide to me a calendar view for the habit of expressing gratitude on January 2025?")
    
    # Option 2: Run a multi-turn conversation in the same thread
    await run_conversation()
    
    # Option 3: Run all predefined questions in the same thread
    # await run_all_questions()
    
    # Option 4: Run an interactive session
    # await run_interactive_session()

def main():
    """Main function to run the script"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main() 