from pydantic import BaseModel, HttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Optional
import json
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file explicitly
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Settings(BaseSettings):
    """Application settings loaded from environment variables or VS Code configuration"""
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://glhf.chat/api/openai/v1")
    llm_model: str = Field(default="hf:Qwen/QwQ-32B-Preview")
    llm_temperature: float = Field(default=0.7)
    
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        env_prefix="LLM_"  # This will match LLM_API_KEY, LLM_BASE_URL etc.
    )
    
    @classmethod
    def from_vscode_settings(cls):
        """Load settings from VS Code configuration passed via environment variables"""
        # First try environment variables
        env_settings = cls()
        logger.debug(f"Loaded settings from environment: api_key_length={len(env_settings.llm_api_key)}")
        logger.debug(f"Environment variables: {dict(os.environ)}")
        
        # Then try VS Code settings
        settings_json = os.environ.get("VSCODE_SETTINGS", "{}")
        logger.debug(f"Loading VS Code settings from environment: {settings_json}")
        try:
            vscode_settings = json.loads(settings_json)
            logger.debug(f"Parsed VS Code settings: {vscode_settings}")
            
            # Create settings from VS Code if available, otherwise use env settings
            settings = cls(
                llm_api_key=vscode_settings.get("pydanticAgent.llm.apiKey", "") or env_settings.llm_api_key,
                llm_base_url=vscode_settings.get("pydanticAgent.llm.baseUrl", env_settings.llm_base_url),
                llm_model=vscode_settings.get("pydanticAgent.llm.model", env_settings.llm_model),
                llm_temperature=float(vscode_settings.get("pydanticAgent.llm.temperature", env_settings.llm_temperature))
            )
            
            logger.debug(f"Final settings: api_key_length={len(settings.llm_api_key)}, base_url={settings.llm_base_url}")
            return settings
        except Exception as e:
            logger.error(f"Error loading VS Code settings: {e}")
            # Fall back to environment variables
            return env_settings

# Create settings instance
settings = Settings.from_vscode_settings()
