from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from datetime import datetime

class AgentCapability(str, Enum):
    CODE_COMPLETION = "code_completion"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"

class CodeContext(BaseModel):
    file_path: str
    content: str
    language: str
    cursor_position: Optional[tuple[int, int]] = None
    selected_text: Optional[str] = None

class AgentAction(BaseModel):
    action_type: str
    parameters: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

class AgentResponse(BaseModel):
    success: bool
    message: str
    changes: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None

class BaseAgent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    capabilities: List[AgentCapability]
    context: Optional[CodeContext] = None
    handlers: Dict[str, Callable] = Field(default_factory=dict)

    def register_handler(self, action_type: str, handler: Callable):
        """Register a handler for a specific action type"""
        self.handlers[action_type] = handler

    async def process_action(self, action: AgentAction) -> AgentResponse:
        """Process an incoming action and return a response"""
        if action.action_type not in self.handlers:
            return AgentResponse(
                success=False,
                message=f"No handler registered for action type: {action.action_type}"
            )
        
        try:
            handler = self.handlers[action.action_type]
            result = await handler(action.parameters)
            return AgentResponse(
                success=True,
                message="Action processed successfully",
                changes=result.get("changes"),
                suggestions=result.get("suggestions")
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error processing action: {str(e)}"
            )

    def update_context(self, context: CodeContext):
        """Update the agent's current context"""
        self.context = context
