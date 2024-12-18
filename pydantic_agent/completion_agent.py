from typing import Dict, Any
from .base import BaseAgent, AgentCapability, CodeContext

class CompletionRequest(CodeContext):
    prefix: str
    max_tokens: int = 50
    temperature: float = 0.7

class CompletionAgent(BaseAgent):
    def __init__(self, name: str = "CompletionAgent"):
        super().__init__(
            name=name,
            capabilities=[AgentCapability.CODE_COMPLETION]
        )
        self.register_handler("generate_completion", self.generate_completion)

    async def generate_completion(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code completion based on the current context"""
        if not self.context:
            raise ValueError("No context provided")

        # Here you would implement your actual completion logic
        # This is just a simple example
        completion = f"# Generated completion for {parameters.get('prefix', '')}\n"
        completion += "def example_function():\n    pass"

        return {
            "changes": [{
                "type": "insertion",
                "position": self.context.cursor_position,
                "content": completion
            }],
            "suggestions": [
                "Consider adding docstring",
                "Add type hints for better code clarity"
            ]
        }
