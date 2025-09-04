import asyncio
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage

# Replace localhost with your actual LangGraph cloud endpoint
client = get_client(url="http://localhost:2024")
# client = get_client(url="http://lg.flashlit.ai:8123")

# Configuration to be passed to the agent - based on agent.py main function
config = {
    "configurable": {
        "context_description": "You are talking to a new person and you are going to be his friend.",
        "character_name": "Fitzwilliam Darcy",
        "director_prompt": "Be nice and friendly but true to yourself.",
        "response_tone": "Darcy style.",
        "book_title": "Pride and Prejudice",
        "user_id": "francesco@flashlit.ai",
    }
}

async def get_or_create_thread():
    """Get an existing thread or create a new one using the LangGraph SDK API"""
    # Create thread with metadata for tracking purposes
    thread = await client.threads.create(
        metadata={"created_by": "flashlit_characters_test", "user_id": "francesco@flashlit.ai"}
    )
    # The thread is returned as a dictionary, not an object with attributes
    thread_id = thread['thread_id']
    print(f"Created new thread with ID: {thread_id}")
    return thread_id

async def run_question_in_thread(thread_id, speaker_name, question, is_first_question=False):
    """Run a question in a specific thread to maintain conversation context"""
    print(f"\n\n=== {speaker_name} asks in thread {thread_id}: {question} ===\n")
    
    messages = []
    
    # For the first question in a conversation, we add a presenter introduction
    if is_first_question:
        messages.append(
            HumanMessage(
                content="Now it is the turn for someone to ask a question about the book!", 
                additional_kwargs={"metadata": {"speaker_name": "Presenter"}}
            )
        )
    
    # Add the current question
    messages.append(
        HumanMessage(
            content=question, 
            additional_kwargs={"metadata": {"speaker_name": speaker_name}}
        )
    )
    
    async for chunk in client.runs.stream(
        thread_id,  # Using a specific thread ID to maintain context
        "flashlit-characters",  # Using the correct agent name
        input={"messages": messages, "is_new_question": True},  # Format matches what agent_graph expects
        config=config,  # Pass the configuration to the agent
        stream_mode="updates",
    ):
        print(f"Receiving new event of type: {chunk.event}...")
        if hasattr(chunk.data, 'get') and chunk.data.get('messages'):
            message = chunk.data.get('messages', [])
            if isinstance(message, list) and message:
                message = message[-1]
                if hasattr(message, 'content') and message.content:
                    print(f"Content: {message.content}")
                    if hasattr(message, 'additional_kwargs') and message.additional_kwargs.get('metadata'):
                        print(f"Speaker: {message.additional_kwargs['metadata'].get('speaker_name', 'Unknown')}")
                elif hasattr(message, 'tool_calls') and message.tool_calls:
                    print(f"Tool calls: {message.tool_calls}")
        else:
            print(chunk.data)
        print("\n---\n")

async def run_multi_turn_conversation():
    """Run a multi-turn conversation with the same thread ID to maintain context"""
    # Create a new thread for this conversation
    thread_id = await get_or_create_thread()
    
    # First question
    await run_question_in_thread(
        thread_id, 
        "Larry", 
        "Hi Tom, my name is Larry! Nice to meet you?",
        is_first_question=True
    )
    
    # Second question in the same thread (maintaining context)
    # await run_question_in_thread(
    #     thread_id, 
    #     "Sarah", 
    #     "What mischievous adventures did you have after that?"
    # )
    
    # Optional third question to show continuity
    await run_question_in_thread(
        thread_id,
        "Larry",
        "Do you still remember my name?"
    )
    
    return thread_id

# This is the main entry point for the script
async def async_main():
    """Main function to run the script asynchronously"""
    # Run a multi-turn conversation using the same thread
    thread_id = await run_multi_turn_conversation()
    print(f"\nConversation completed in thread: {thread_id}")

def main():
    """Main function to run the script"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
