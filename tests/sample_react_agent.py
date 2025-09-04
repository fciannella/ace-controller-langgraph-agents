import asyncio
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage

# Replace localhost with your actual LangGraph cloud endpoint
# client = get_client(url="http://localhost:8123")
client = get_client(url="http://lg.flashlit.ai:8123")

# Configuration to be passed to the agent
config = {
    "configurable": {
        "user_email": "francesco@flashlit.ai",
    }
}

async def run_question(question):
    """Run a single question through the LangGraph cloud agent"""
    print(f"\n\n=== Running question: {question} ===\n")
    
    # Create a message list directly instead of nested in a dictionary
    # This matches what the react-agent expects
    async for chunk in client.runs.stream(
        None,  # Threadless run
        "sample-react-agent",  # Name of assistant defined in langgraph.json
        input=[HumanMessage(content=question)],  # Pass a list of BaseMessages directly
        stream_mode="updates",
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

async def run_all_questions():
    """Run all questions sequentially"""
    questions = ["What's the weather in san francisco?"]
    for question in questions:
        await run_question(question)

# This is the main entry point for the script
def main():
    """Main function to run the script"""
    asyncio.run(run_all_questions())

if __name__ == "__main__":
    main()
