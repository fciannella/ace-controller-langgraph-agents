import asyncio
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage

# Configuration for local langgraph service on port 2024
LOCAL_LANGGRAPH_URL = "http://localhost:2024"

# Initialize the client
client = get_client(url=LOCAL_LANGGRAPH_URL)

# Configuration to be passed to the agent
config = {
    "configurable": {
        "user_email": "test@example.com",
    }
}

async def test_connection():
    """Test connection to the LangGraph service"""
    print(f"Testing connection to {LOCAL_LANGGRAPH_URL}...")
    
    try:
        # Try to list available assistants
        assistants = await client.assistants.search()
        print(f"✅ Connection successful! Found {len(assistants)} assistants:")
        
        for i, assistant in enumerate(assistants):
            print(f"\nAssistant {i+1}:")
            # Handle both dict and object formats
            if isinstance(assistant, dict):
                name = assistant.get('name', assistant.get('assistant_id', 'Unknown'))
                description = assistant.get('description', 'No description available')
                print(f"  - Name: {name}")
                print(f"  - Description: {description}")
                # Show all keys for debugging
                print(f"  - Available keys: {list(assistant.keys())}")
            else:
                print(f"  - Name: {assistant.name}")
                print(f"  - Description: {assistant.description}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def run_test_message(assistant_name, message_content):
    """Run a test message through the specified assistant"""
    print(f"\n=== Testing assistant: {assistant_name} ===")
    print(f"Input: {message_content}")
    print("Response:")
    
    try:
        # Create a message list and stream the response
        async for chunk in client.runs.stream(
            None,  # Threadless run
            assistant_name,
            input=[HumanMessage(content=message_content)],
            stream_mode="updates",
            config=config
        ):
            print(f"Event type: {chunk.event}")
            if hasattr(chunk.data, 'get') and chunk.data.get('messages'):
                messages = chunk.data.get('messages', [])
                if isinstance(messages, list) and messages:
                    message = messages[-1]
                    if hasattr(message, 'content') and message.content:
                        print(f"Content: {message.content}")
                    elif hasattr(message, 'tool_calls') and message.tool_calls:
                        print(f"Tool calls: {message.tool_calls}")
            else:
                print(f"Data: {chunk.data}")
            print("---")
        
        print("✅ Test message completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test message failed: {e}")
        return False

async def run_comprehensive_test():
    """Run a comprehensive test of the langgraph service"""
    print("🚀 Starting LangGraph Client Test Suite")
    print("=" * 50)
    
    # Test 1: Connection test
    print("\n1. Testing connection...")
    connection_success = await test_connection()
    
    if not connection_success:
        print("❌ Stopping tests due to connection failure")
        return
    
    # Test 2: List and test available assistants
    print("\n2. Testing available assistants...")
    try:
        assistants = await client.assistants.search()
        
        if not assistants:
            print("⚠️  No assistants found. Creating a test message anyway...")
            # You can specify a known assistant name here
            await run_test_message("sample-react-agent", "Hello, this is a test message!")
        else:
            # Test the first available assistant
            first_assistant = assistants[0]
            # Handle both dict and object formats
            if isinstance(first_assistant, dict):
                assistant_name = first_assistant.get('name', first_assistant.get('assistant_id', 'Unknown'))
            else:
                assistant_name = first_assistant.name
            await run_test_message(assistant_name, "Hello, this is a test message!")
    
    except Exception as e:
        print(f"❌ Assistant test failed: {e}")
    
    # Test 3: Test with multiple message types
    print("\n3. Testing different message types...")
    test_messages = [
        "What's the weather like today?",
        "Can you help me with a simple calculation: 15 + 27?",
        "Tell me a short joke",
    ]
    
    try:
        assistants = await client.assistants.search()
        if assistants:
            first_assistant = assistants[0]
            # Handle both dict and object formats
            if isinstance(first_assistant, dict):
                assistant_name = first_assistant.get('name', first_assistant.get('assistant_id', 'Unknown'))
            else:
                assistant_name = first_assistant.name
            
            for message in test_messages:
                print(f"\nTesting message: {message}")
                await run_test_message(assistant_name, message)
                await asyncio.sleep(1)  # Small delay between tests
    except Exception as e:
        print(f"❌ Multiple message test failed: {e}")
    
    print("\n🎉 Test suite completed!")

async def test_specific_assistant(assistant_name, message="Hello, this is a test!"):
    """Test a specific assistant by name"""
    print(f"🎯 Testing specific assistant: {assistant_name}")
    print("=" * 50)
    
    connection_success = await test_connection()
    if connection_success:
        await run_test_message(assistant_name, message)

def main():
    """Main function to run the test script"""
    print("LangGraph Client Test Script")
    print("Connecting to:", LOCAL_LANGGRAPH_URL)
    
    # You can modify this to test specific scenarios
    try:
        # Run comprehensive test
        asyncio.run(run_comprehensive_test())
        
        # Uncomment the line below to test a specific assistant instead
        # asyncio.run(test_specific_assistant("your-assistant-name", "Your test message"))
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    main() 