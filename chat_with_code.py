import asyncio
from pydantic_agent.base import AgentCapability
from pydantic_agent.llm_integration import LLMConfig
from pydantic_agent.llm_agent import LLMAgent
from pydantic_agent.chat_interface import CodeChatInterface
from rich.console import Console

async def main():
    # Configure the LLM
    llm_config = LLMConfig(
        base_url="https://glhf.chat/api/openai/v1",
        api_key="glhf_a30f9885a9da64366f8c83ab23d63a39",
        model="openai/hf:Qwen/QwQ-32B-Preview",
        temperature=0.7,
        stream=True
    )

    # Create the agent
    agent = LLMAgent(
        name="CodeChat",
        llm_config=llm_config,
        capabilities=[
            AgentCapability.CODE_COMPLETION,
            AgentCapability.CODE_REVIEW,
            AgentCapability.DOCUMENTATION
        ]
    )

    # Create and start the chat interface
    console = Console()
    chat = CodeChatInterface(agent, console)
    
    try:
        await chat.start_chat()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
    finally:
        console.print("[yellow]Goodbye![/yellow]")

if __name__ == "__main__":
    asyncio.run(main())
