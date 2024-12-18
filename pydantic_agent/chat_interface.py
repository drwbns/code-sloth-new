import asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.live import Live
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from typing import List, Optional
import os
from .base import BaseAgent, AgentCapability, CodeContext
from .llm_integration import LLMConfig, Message

class ChatMessage:
    def __init__(self, role: str, content: str, code_context: Optional[CodeContext] = None):
        self.role = role
        self.content = content
        self.code_context = code_context

class CodeChatInterface:
    def __init__(self, agent: BaseAgent, console: Optional[Console] = None):
        self.agent = agent
        self.console = console or Console()
        self.messages: List[ChatMessage] = []
        self.style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'user-input': '#ffffff',
        })
        self.session = PromptSession(style=self.style)

    def _format_message(self, message: ChatMessage) -> Panel:
        """Format a chat message with proper styling"""
        content = []
        
        # Add code context if present
        if message.code_context:
            if message.code_context.content:
                syntax = Syntax(
                    message.code_context.content,
                    message.code_context.language,
                    theme="monokai",
                    line_numbers=True
                )
                content.append(Panel(syntax, title=message.code_context.file_path))
        
        # Add message content as markdown
        content.append(Markdown(message.content))
        
        return Panel(
            *content,
            title=f"[bold]{message.role}[/bold]",
            border_style="green" if message.role == "Assistant" else "blue"
        )

    async def display_streaming_response(self, response_gen, code_context: Optional[CodeContext] = None):
        """Display a streaming response with a loading indicator"""
        buffer = []
        
        with Live(refresh_per_second=4) as live:
            async for chunk in response_gen:
                content = chunk["partial_response"]["changes"][0]["content"]
                buffer.append(content)
                message = ChatMessage("Assistant", "".join(buffer), code_context)
                live.update(self._format_message(message))
        
        # Store the complete message
        self.messages.append(message)

    def display_messages(self, start_idx: int = 0):
        """Display all messages from start_idx"""
        for message in self.messages[start_idx:]:
            self.console.print(self._format_message(message))

    async def start_chat(self):
        """Start the chat interface"""
        self.console.clear()
        self.console.print("[bold green]Code Chat Interface[/bold green]")
        self.console.print("Type 'quit' to exit, 'clear' to clear chat, 'context' to set code context")
        
        while True:
            try:
                # Get user input
                user_input = await self.session.prompt_async(
                    [('class:prompt', '>>> '), ('class:user-input', '')],
                    multiline=False
                )
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'clear':
                    self.console.clear()
                    self.messages.clear()
                    continue
                elif user_input.lower() == 'context':
                    # Get file path
                    file_path = await self.session.prompt_async("Enter file path: ")
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            content = f.read()
                        context = CodeContext(
                            file_path=file_path,
                            content=content,
                            language=os.path.splitext(file_path)[1][1:]  # Get extension without dot
                        )
                        self.agent.update_context(context)
                        self.console.print("[green]Context updated![/green]")
                    else:
                        self.console.print("[red]File not found![/red]")
                    continue

                # Create and store user message
                user_message = ChatMessage("User", user_input, self.agent.context)
                self.messages.append(user_message)
                self.console.print(self._format_message(user_message))

                # Generate response
                messages = [
                    Message(role="system", content=(
                        "You are a helpful coding assistant. "
                        "If code context is provided, refer to it in your responses. "
                        "Be concise but informative."
                    )),
                    *[Message(role=m.role.lower(), content=m.content) 
                      for m in self.messages[-4:]]  # Include last 4 messages for context
                ]

                # Stream the response
                stream_gen = self.agent.stream_generate({
                    "messages": messages,
                    "system_prompt": "You are a helpful coding assistant."
                })
                
                await self.display_streaming_response(stream_gen, self.agent.context)

            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
