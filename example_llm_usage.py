import asyncio
import os
from pydantic_agent.base import CodeContext, AgentAction, AgentCapability
from pydantic_agent.llm_integration import LLMConfig
from pydantic_agent.llm_agent import LLMAgent

async def main():
    # Configure the LLM
    llm_config = LLMConfig(
        base_url="https://glhf.chat/api/openai/v1",
        api_key="glhf_a30f9885a9da64366f8c83ab23d63a39",
        model="openai/hf:Qwen/QwQ-32B-Preview",
        temperature=0.7,
        stream=True
    )

    # Create an LLM-powered agent
    agent = LLMAgent(
        name="CodeAssistant",
        llm_config=llm_config,
        capabilities=[
            AgentCapability.CODE_COMPLETION,
            AgentCapability.CODE_REVIEW
        ]
    )

    # Set up the context
    context = CodeContext(
        file_path="example.py",
        content="""
def calculate_fibonacci(n: int) -> int:
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
        """,
        language="python",
        cursor_position=(7, 0)
    )
    agent.update_context(context)

    # Example 1: Stream generation of docstring
    print("\nStreaming docstring generation:")
    stream_action = AgentAction(
        action_type="stream_generate",
        parameters={
            "system_prompt": "You are a Python documentation expert.",
            "prompt": "Write a detailed docstring for this fibonacci function."
        }
    )
    
    try:
        async for partial_result in agent.stream_generate(stream_action.parameters):
            # In a real application, you would update the UI with each chunk
            print("Received chunk:", partial_result["partial_response"]["changes"][0]["content"], end="", flush=True)
    except Exception as e:
        print(f"Error during streaming: {e}")

    # Example 2: Code analysis (non-streaming)
    print("\n\nCode analysis:")
    analyze_action = AgentAction(
        action_type="analyze",
        parameters={}  # Uses default system prompt
    )
    analyze_response = await agent.process_action(analyze_action)
    print(f"Success: {analyze_response.success}")
    if analyze_response.suggestions:
        print("Analysis:", analyze_response.suggestions[0])

if __name__ == "__main__":
    asyncio.run(main())
