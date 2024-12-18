"""Pydantic Agent package for VS Code extension"""

from .base import BaseAgent, AgentCapability, AgentAction, AgentResponse, CodeContext
from .llm_agent import LLMAgent
from .llm_integration import LLMConfig, LLMClient, Message, ChatResponse
from .config import settings

__version__ = "0.1.0"
