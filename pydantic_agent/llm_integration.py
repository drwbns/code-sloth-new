from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, AsyncGenerator, Literal
import aiohttp
import json
import asyncio
import logging
from async_timeout import timeout as async_timeout
from .config import settings
import instructor
from instructor import OpenAISchema

class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str = settings.llm_model
    temperature: float = settings.llm_temperature
    max_tokens: Optional[int] = None
    stream: bool = True

class Message(OpenAISchema):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatResponse(OpenAISchema):
    """Chat response from the LLM"""
    response: str = Field(description="The response text")
    type: Literal["text", "code"] = Field(
        default="text",
        description="The type of response"
    )

class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.session = None
        self.logger = logging.getLogger(__name__)
        if not config.api_key:
            self.logger.error("No API key provided in configuration")
        self.logger.debug(f"Initialized LLM client with base URL: {config.base_url}")

    async def ensure_session(self):
        """Ensure we have an active session"""
        if self.session is not None:
            if self.session.closed:
                await self.cleanup()
            else:
                return

        if not self.config.api_key:
            raise ValueError("API key is required but not provided")

        self.session = aiohttp.ClientSession()
        self.logger.debug(f"Initialized session")

    async def _process_stream(self, response) -> AsyncGenerator[ChatResponse, None]:
        """Process the SSE stream from the response"""
        try:
            async for line in response.content:
                if not line:
                    continue
                    
                try:
                    line = line.decode('utf-8').strip()
                    if not line.startswith('data: '):
                        continue

                    data = line[6:]  # Remove 'data: ' prefix
                    if data == '[DONE]':
                        self.logger.debug("Received [DONE] token")
                        continue

                    json_data = json.loads(data)
                    if not isinstance(json_data, dict):
                        self.logger.warning(f"Unexpected JSON format: {json_data}")
                        continue

                    # Handle both OpenAI-style and Qwen-style responses
                    content = None
                    if 'choices' in json_data:
                        delta = json_data['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                    elif 'output' in json_data:
                        content = json_data.get('output', {}).get('text', '')
                    
                    if content:
                        self.logger.debug(f"Extracted content: {content}")
                        yield ChatResponse(
                            response=content.strip(),  # Remove any whitespace
                            type="text"
                        )
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse JSON: {data} - {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing stream chunk: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error in _process_stream: {e}", exc_info=True)
            raise

    async def _make_request(self, messages: List[Message], max_retries: int = 3, retry_delay: float = 2.0) -> aiohttp.ClientResponse:
        """Make the actual HTTP request with proper timeout handling and retries"""
        await self.ensure_session()
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        
        payload = {
            'model': self.config.model,
            'messages': [{'role': msg.role, 'content': msg.content} for msg in messages],
            'temperature': self.config.temperature,
            'stream': self.config.stream
        }
        if self.config.max_tokens:
            payload['max_tokens'] = self.config.max_tokens
            
        self.logger.debug(f"Making request to {url}")
        self.logger.debug(f"Request headers: Authorization: Bearer ***{self.config.api_key[-4:] if self.config.api_key else ''}")
        self.logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        
        last_error = None
        for attempt in range(max_retries):
            try:
                async with async_timeout(30):
                    response = await self.session.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.config.api_key.strip()}"
                        }
                    )
                    if response.status == 502:
                        self.logger.warning(f"Received 502 error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    elif response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"Error from LLM service ({response.status}): {error_text}")
                        raise ValueError(f"Error from LLM service: {error_text}")
                    return response
            except asyncio.TimeoutError:
                last_error = "Request timed out"
                self.logger.warning(f"Request timed out (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        
        error_msg = f"Failed after {max_retries} attempts. Last error: {last_error}"
        self.logger.error(error_msg)
        raise ValueError(error_msg)

    async def stream_complete(self, messages: List[Message]) -> AsyncGenerator[ChatResponse, None]:
        """Stream completion responses from the LLM service"""
        try:
            async with async_timeout(30):  # 30 second timeout
                response = await self._make_request(messages)
                self.logger.debug("Got response from LLM service")
                async for chunk in self._process_stream(response):
                    self.logger.debug(f"Raw response chunk: {chunk}")
                    try:
                        if chunk:
                            self.logger.debug(f"Processed chunk: {chunk}")
                            yield chunk
                    except Exception as e:
                        self.logger.error(f"Error processing chunk: {e}", exc_info=True)
                        yield ChatResponse(response=str(e), type="text")
        except Exception as e:
            self.logger.error(f"Error in stream_complete: {str(e)}", exc_info=True)
            raise

    async def complete(self, messages: List[Message]) -> ChatResponse:
        """Non-streaming completion"""
        async for response in self.stream_complete(messages):
            return response

    async def test_connection(self) -> bool:
        """Test the LLM connection with a simple Hello World prompt"""
        try:
            self.logger.info("Testing LLM connection...")
            self.logger.debug(f"Using base URL: {self.config.base_url}")
            self.logger.debug(f"Using model: {self.config.model}")
            
            messages = [Message(role="user", content="Say 'Hello World'")]
            async for response in self.stream_complete(messages):
                self.logger.info(f"Received response: {response.response}")
                return True
                
        except Exception as e:
            self.logger.error(f"LLM Test Failed: {str(e)}")
            return False

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None
