import asyncio
from pydantic_agent.base import CodeContext, AgentAction
from pydantic_agent.completion_agent import CompletionAgent

async def main():
    # Create a completion agent
    agent = CompletionAgent()

    # Set up the context
    context = CodeContext(
        file_path="example.py",
        content="def hello_world():\n    ",
        language="python",
        cursor_position=(1, 4)
    )
    agent.update_context(context)

    # Create an action
    action = AgentAction(
        action_type="generate_completion",
        parameters={"prefix": "def hello"}
    )

    # Process the action
    response = await agent.process_action(action)
    
    print(f"Success: {response.success}")
    print(f"Message: {response.message}")
    if response.changes:
        print("Changes:", response.changes)
    if response.suggestions:
        print("Suggestions:", response.suggestions)

if __name__ == "__main__":
    asyncio.run(main())
