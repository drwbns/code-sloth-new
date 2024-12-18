from .base import BaseAgent, AgentCapability, AgentAction, AgentResponse
from .llm_integration import LLMConfig, LLMClient, Message, ChatResponse
from typing import Dict, Any, List, AsyncGenerator, Optional
import asyncio
from pydantic import Field
import logging

class LLMAgent(BaseAgent):
    llm_client: LLMClient = None
    llm_config: LLMConfig = None
    logger: logging.Logger = Field(default_factory=lambda: logging.getLogger(__name__))

    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
        capabilities: List[AgentCapability]
    ):
        super().__init__(name=name, capabilities=capabilities)
        self.llm_config = llm_config
        self.llm_client = LLMClient(llm_config)
        self.register_handler("generate", self.generate)
        self.register_handler("analyze", self.analyze)
        self.register_handler("stream_generate", self.stream_generate)

    async def stream_generate(self, parameters: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream generated code or text using the LLM"""
        if not self.context:
            raise ValueError("No context provided")

        messages = [
            Message(role="system", content=parameters.get("system_prompt", "You are a helpful coding assistant.")),
            Message(role="user", content=parameters.get("prompt", ""))
        ]

        self.logger.debug(f"Starting stream_generate with messages: {messages}")
        try:
            current_position = 0
            async for chunk in self.llm_client.stream_complete(messages):
                self.logger.debug(f"Received chunk: {chunk}")
                if chunk and chunk.response:
                    response_dict = {
                        "partial_response": {
                            "changes": [{
                                "type": "insertion",
                                "position": current_position,
                                "content": chunk.response
                            }]
                        }
                    }
                    self.logger.debug(f"Yielding response: {response_dict}")
                    yield response_dict
                    current_position += len(chunk.response)
        except Exception as e:
            self.logger.error(f"Error in stream_generate: {str(e)}", exc_info=True)
            raise

    async def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code or text using the LLM (non-streaming)"""
        if not self.context:
            raise ValueError("No context provided")

        messages = [
            Message(role="system", content=parameters.get("system_prompt", "You are a helpful coding assistant.")),
            Message(role="user", content=parameters.get("prompt", ""))
        ]

        response = await self.llm_client.complete(messages)

        return {
            "changes": [{
                "type": "insertion",
                "position": self.context.cursor_position,
                "content": response.response
            }],
            "suggestions": None
        }

    async def analyze(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code using the LLM"""
        if not self.context:
            raise ValueError("No context provided")

        messages = [
            Message(role="system", content="You are a code analysis expert."),
            Message(
                role="user",
                content=f"Analyze this code and provide suggestions:\n\n{self.context.content}"
            )
        ]

        response = await self.llm_client.complete(messages)

        return {
            "changes": None,
            "suggestions": [response.response]
        }

    async def test_connection(self) -> bool:
        """Test the LLM connection"""
        return await self.llm_client.test_connection()

    async def cleanup(self):
        """Cleanup resources"""
        if self.llm_client:
            await self.llm_client.cleanup()
