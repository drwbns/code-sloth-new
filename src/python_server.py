# Python server for the Pydantic Agent VS Code extension
import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import Dict, Any
import openai
from aiohttp import web
from dotenv import load_dotenv
from pathlib import Path

from pydantic_agent.base import CodeContext, AgentCapability
from pydantic_agent.llm_integration import LLMConfig
from pydantic_agent.llm_agent import LLMAgent
from pydantic_agent.config import settings

# Initialize global variables
agent = None
client = None
logger = None  # Will initialize after configuring logging

# Configure version
VERSION = "1.0.0"
BUILD_NUMBER = "001"  # Keep in sync with version.ts

# Load environment variables from .env file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Configure logging
class VersionFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, version=None, build=None):
        super().__init__(fmt, datefmt)
        self.version = version
        self.build = build

    def format(self, record):
        record.version = f'v{self.version} (build {self.build})'
        return super().format(record)

# Create handlers
file_handler = logging.FileHandler(os.path.join(project_root, "pydantic_agent_debug.log"), mode='w', encoding='utf-8')
console_handler = logging.StreamHandler()

# Create formatter
formatter = VersionFormatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - [%(version)s] %(message)s',
    datefmt=None,
    version=VERSION,
    build=BUILD_NUMBER
)

# Configure handlers
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Always use DEBUG level for now
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Get our module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure module logger is also at DEBUG level

logger.info("Starting Pydantic Agent")

# Add the project root directory to Python path
sys.path.insert(0, project_root)
logger.debug(f"Added {project_root} to Python path")
logger.debug(f"Python path is now: {sys.path}")

def write_port_file(port: int):
    """Write the port number to a temp file that the extension can read"""
    port_file = os.path.join(tempfile.gettempdir(), 'pydantic_agent_port.txt')
    try:
        # First ensure any old port file is removed
        if os.path.exists(port_file):
            os.remove(port_file)
            logger.info(f"Removed old port file: {port_file}")
        
        # Write new port file
        with open(port_file, 'w') as f:
            f.write(str(port))
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
        
        # Verify the file was written correctly
        with open(port_file, 'r') as f:
            content = f.read().strip()
            if content != str(port):
                raise ValueError(f"Port file verification failed. Expected {port}, got {content}")
        
        logger.info(f"Successfully wrote and verified port {port} to {port_file}")
    except Exception as e:
        logger.error(f"Error writing port file: {e}")
        raise

async def initialize_llm_agent(settings_json: str) -> LLMAgent:
    """Initialize the LLM agent with the given settings"""
    global agent, client
    try:
        # Setup logging first
        workspace_path = os.path.dirname(os.path.dirname(__file__))
        logger = logging.getLogger(__name__)
        
        logger.debug(f"VS Code settings: {settings_json}")
        
        # Parse settings from VS Code
        try:
            settings_dict = json.loads(settings_json) if settings_json else {}
            logger.debug(f"Parsed VS Code settings: {settings_dict}")
            
            # Get settings with fallbacks
            api_key = settings_dict.get("pydanticAgent.llm.apiKey") or os.getenv('LLM_API_KEY', '')
            base_url = settings_dict.get("pydanticAgent.llm.baseUrl") or os.getenv('LLM_BASE_URL', 'https://glhf.chat/api/openai/v1')
            model = settings_dict.get("pydanticAgent.llm.model") or os.getenv('LLM_MODEL', 'hf:Qwen/Qwen2.5-Coder-32B-Instruct')
            temperature = float(settings_dict.get("pydanticAgent.llm.temperature") or os.getenv('LLM_TEMPERATURE', '0.7'))
            
            # Format API key correctly for GLHF
            if api_key:
                # Remove any existing prefixes
                api_key = api_key.replace('Bearer ', '').strip()
                if not api_key.startswith('glhf_'):
                    api_key = f'glhf_{api_key}'
            
            # Log settings (masking API key)
            masked_api_key = '***' + api_key[-4:] if api_key else 'not set'
            logger.debug(f"Using settings: base_url={base_url}, model={model}, temperature={temperature}, api_key_present={bool(api_key)}")
            logger.debug(f"API Key: {masked_api_key}")
            
            # Initialize OpenAI client with headers
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers={
                    "Authorization": f"Bearer {api_key}"
                }
            )
            
            # Test connection
            try:
                models = client.models.list()
                logger.debug(f"Successfully connected to API. Available models: {models}")
            except Exception as e:
                logger.error(f"Failed to list models: {str(e)}")
                raise
            
            # Initialize LLM client with VS Code settings
            config = LLMConfig(
                base_url=base_url,
                api_key=api_key,
                model=model,
                temperature=temperature
            )
            logger.debug(f"Created LLM config with api_key present: {bool(config.api_key)}, base_url: {config.base_url}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse VS Code settings: {str(e)}")
            raise
        
        agent = LLMAgent(
            name="PydanticAgent",
            llm_config=config,
            capabilities=[
                AgentCapability.CODE_COMPLETION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.REFACTORING,
                AgentCapability.DOCUMENTATION,
                AgentCapability.TESTING
            ]
        )
        
        return agent
    except Exception as e:
        logger.error(f"Failed to initialize LLM agent: {str(e)}")
        raise

async def handle_message(request: web.Request) -> web.StreamResponse:
    """Handle incoming chat messages"""
    global agent, client
    logger = logging.getLogger(__name__)
    
    try:
        # Parse the incoming message
        data = await request.json()
        message = data.get('message', '')
        context = data.get('context', {})
        is_system = data.get('isSystemMessage', False)
        logger.info(f"Chat endpoint called with message: {message}")
        
        if not message.strip():
            raise ValueError("Empty message received")

        # Handle welcome message specially
        if is_system and message == 'WELCOME_MESSAGE':
            logger.info("Processing system message")
            response = web.StreamResponse(
                status=200,
                reason='OK',
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                }
            )
            logger.info("Preparing welcome message response")
            await response.prepare(request)
            
            welcome_msg = f"Welcome to Pydantic Agent v{VERSION}! I'm ready to help you with your coding tasks."
            data = json.dumps({"text": welcome_msg})
            logger.info(f"Sending welcome message data: {data}")
            await response.write(f"data: {data}\n\n".encode('utf-8'))
            await response.write(b"data: {\"done\": true}\n\n")
            logger.info("Welcome message sent successfully")
            return response

        # Check if agent and client are initialized
        if not agent or not client:
            error_data = json.dumps({"error": "LLM agent not initialized"})
            return web.Response(
                status=500,
                text=error_data,
                content_type='application/json'
            )

        # Prepare the response
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        )
        await response.prepare(request)

        # Stream the response
        try:
            # Initialize agent context
            cursor_pos = context.get('cursorPosition', [0, 0])
            if not isinstance(cursor_pos, list):
                cursor_pos = [0, 0]
            
            agent.context = CodeContext(
                content=context.get('content', ''),
                language=context.get('language', ''),
                cursor_position=tuple(cursor_pos),
                file_path=context.get('fileName', '')
            )
            logger.debug(f"Updated agent context with cursor position: {cursor_pos}")
            
            # Create chat completion with streaming
            completion = client.chat.completions.create(
                stream=True,
                model=agent.llm_config.model,
                messages=[
                    {"role": "system", "content": "You are a helpful coding assistant in VS Code."},
                    {"role": "user", "content": message}
                ],
                temperature=agent.llm_config.temperature
            )
            
            # Send start message
            start_data = json.dumps({"startNewMessage": True})
            await response.write(f"data: {start_data}\n\n".encode('utf-8'))

            try:
                logger.debug("Starting to stream response chunks")
                for chunk in completion:
                    logger.debug(f"Raw chunk: {chunk}")
                    if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta and hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        logger.debug(f"Received chunk: {text}")
                        # Send the chunk in SSE format
                        response_data = json.dumps({
                            "type": "chunk",
                            "content": text
                        })
                        logger.debug(f"Sending response data: {response_data}")
                        await response.write(f"data: {response_data}\n\n".encode('utf-8'))
                        logger.debug("Response written")

                # Send done message
                logger.debug("Sending done message")
                done_data = json.dumps({"type": "done"})
                await response.write(f"data: {done_data}\n\n".encode('utf-8'))
            except Exception as e:
                logger.error(f"Error processing stream: {str(e)}", exc_info=True)
                error_data = json.dumps({"error": str(e)})
                logger.debug(f"Sending error data: {error_data}")
                await response.write(f"data: {error_data}\n\n".encode('utf-8'))
        finally:
            await response.write_eof()
            return response
        
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        return web.Response(
            status=500,
            text=json.dumps({"error": str(e)}),
            content_type='application/json'
        )

async def test_llm_connection():
    """Test the LLM connection on startup"""
    global agent, client
    logger = logging.getLogger(__name__)
    try:
        if not agent or not client:
            logger.error("LLM agent or client not initialized!")
            return False
            
        success = True
        try:
            models = client.models.list()
            logger.debug(f"Successfully connected to API. Available models: {models}")
        except Exception as e:
            logger.error(f"Failed to list models: {str(e)}")
            success = False
        
        return success
    except Exception as e:
        logger.error(f"Error during LLM connection test: {str(e)}")
        return False

async def cleanup():
    """Cleanup resources on server shutdown"""
    if 'agent' in globals():
        await agent.cleanup()

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text='OK')

async def start_server():
    app = web.Application()
    app.router.add_post('/chat', handle_message)
    app.router.add_get('/health', health_check)
    app.on_shutdown.append(lambda _: cleanup())
    
    # Let the OS choose an available port
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 0)
    await site.start()
    
    # Get the port that was assigned and write it IMMEDIATELY
    port = site._server.sockets[0].getsockname()[1]
    write_port_file(port)
    logger.info(f"Server started on http://localhost:{port}")
    
    # Now do the LLM connection tests
    logger.info("Testing LLM connection...")
    await test_llm_connection()
    logger.info("LLM connection test successful!")
    
    return runner, port

async def main():
    try:
        runner, port = await start_server()
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await runner.cleanup()

async def startup():
    """Startup function"""
    try:
        settings_json = os.environ.get("VSCODE_SETTINGS", "{}")
        logger.debug(f"VS Code settings received: {settings_json}")
        
        await initialize_llm_agent(settings_json)
        await main()
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(startup())
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
