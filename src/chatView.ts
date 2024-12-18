import * as vscode from 'vscode';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { getVersionString } from './version';

interface ChatResponse {
    text: string;
    [key: string]: any;
}

export class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'pydanticAgent.chatView';
    private _view?: vscode.WebviewView;
    private readonly _extensionUri: vscode.Uri;
    private readonly _serverPort: number;
    private messages: any[] = [];
    private currentMessage: string = '';
    private version = '1.0.0';
    private isAborting: boolean = false;

    constructor(
        extensionUri: vscode.Uri,
        serverPort: number
    ) {
        this._extensionUri = extensionUri;
        this._serverPort = serverPort;
        console.log(`[${getVersionString()}] ChatViewProvider initialized`);
    }

    private async getServerPort(): Promise<number> {
        const portFile = path.join(os.tmpdir(), 'pydantic_agent_port.txt');
        try {
            const port = parseInt(fs.readFileSync(portFile, 'utf8'), 10);
            console.log(`[${getVersionString()}] Read port from file: ${port}`);
            return port;
        } catch (error) {
            console.error(`[${getVersionString()}] Error reading port file: ${error}`);
            return this._serverPort;
        }
    }

    private async sendWelcomeMessage() {
        console.log(`[${getVersionString()}] Starting welcome message flow`);
        try {
            const port = await this.getServerPort();
            console.log(`[${getVersionString()}] Using server port: ${port}`);

            const response = await fetch(`http://localhost:${port}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    isSystemMessage: true,
                    message: 'WELCOME_MESSAGE'
                })
            });

            console.log(`[${getVersionString()}] Welcome message response status:`, response.status);
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
            }

            const data = await response.json() as ChatResponse;
            console.log(`[${getVersionString()}] Welcome message response data:`, data);

            if (this._view) {
                console.log(`[${getVersionString()}] Sending welcome message to webview`);
                this._view.webview.postMessage({
                    type: 'response',
                    content: {
                        text: data.text,
                        isUser: false
                    }
                });
            } else {
                console.error(`[${getVersionString()}] No webview available to send welcome message`);
            }
        } catch (error) {
            console.error(`[${getVersionString()}] Error in welcome message flow:`, error);
            if (this._view) {
                this._view.webview.postMessage({
                    type: 'response',
                    content: {
                        text: 'Failed to connect to server. Please try again later.',
                        isError: true
                    }
                });
            }
        }
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        console.log(`[${getVersionString()}] Resolving webview view`);
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        console.log(`[${getVersionString()}] Webview HTML set`);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async message => {
            console.log(`[${getVersionString()}] Received message from webview:`, message);
            
            if (message.type === 'ready') {
                console.log(`[${getVersionString()}] Received ready message, sending welcome message`);
                await this.sendWelcomeMessage();
            } else if (message.type === 'sendMessage') {
                console.log(`[${getVersionString()}] Received chat message:`, message);
                await this.handleMessage(webviewView, message);
            }
        });

        // Send initial message to verify webview communication
        webviewView.webview.postMessage({ type: 'init' });
        console.log(`[${getVersionString()}] Sent init message to webview`);

        // Register webview state change handler
        webviewView.onDidChangeVisibility(() => {
            console.log(`[${getVersionString()}] Webview visibility changed. Visible:`, webviewView.visible);
            if (webviewView.visible) {
                console.log(`[${getVersionString()}] Webview became visible, sending welcome message`);
                this.sendWelcomeMessage();
            }
        });
    }

    private async handleMessage(webviewView: vscode.WebviewView, message: any) {
        console.log(`[${getVersionString()}] Handling message:`, message);
        switch (message.type) {
            case 'sendMessage':
                try {
                    const userMessage = message.message;
                    if (!userMessage) return;

                    console.log(`[${getVersionString()}] Processing user message:`, userMessage);

                    // Display user message
                    webviewView.webview.postMessage({ 
                        type: 'response',
                        content: { text: userMessage, isUser: true }
                    });

                    // Add a small delay before showing generating message
                    await new Promise(resolve => setTimeout(resolve, 100));

                    // Show generating message
                    console.log(`[${getVersionString()}] Showing generating message`);
                    webviewView.webview.postMessage({
                        type: 'response',
                        content: { isGenerating: true }
                    });

                    // Send to server
                    const port = await this.getServerPort();
                    console.log(`[${getVersionString()}] Sending request to server on port ${port}`);
                    const response = await fetch(`http://localhost:${port}/chat`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ message: userMessage })
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const reader = response.body?.getReader();
                    if (!reader) {
                        throw new Error('No response body reader available');
                    }

                    // Initialize response
                    let isFirstChunk = true;
                    let isStreaming = true;

                    while (isStreaming) {
                        const { done, value } = await reader.read();
                        if (done) {
                            console.log(`[${getVersionString()}] Stream complete`);
                            isStreaming = false;
                            break;
                        }

                        // Convert the chunk to text
                        const chunk = new TextDecoder().decode(value);
                        console.log(`[${getVersionString()}] Received chunk:`, chunk);
                        const lines = chunk.split('\n');

                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    console.log(`[${getVersionString()}] Parsed data:`, data);
                                    if (isFirstChunk) {
                                        data.replaceGenerating = true;
                                        isFirstChunk = false;
                                    }
                                    if (data.choices && data.choices.length > 0) {
                                        console.log(`[${getVersionString()}] Sending response data to webview:`, data);
                                        webviewView.webview.postMessage({
                                            type: 'response',
                                            content: {
                                                text: data.choices[0].delta.content,
                                                isUser: false
                                            }
                                        });
                                    } else {
                                        console.log(`[${getVersionString()}] Empty choices array, skipping`);
                                    }
                                } catch (e) {
                                    console.error(`[${getVersionString()}] Error parsing SSE data:`, e);
                                    webviewView.webview.postMessage({
                                        type: 'response',
                                        content: { error: 'Error parsing response' }
                                    });
                                }
                            }
                        }
                    }
                } catch (error) {
                    console.error(`[${getVersionString()}] Error:`, error);
                    webviewView.webview.postMessage({
                        type: 'response',
                        content: { 
                            error: error instanceof Error ? error.message : 'An unknown error occurred',
                            isUser: false 
                        }
                    });
                }
                break;
        }
    }

    private handleNewMessage(data: any) {
        if (!this._view) return;

        try {
            if (data.text !== undefined) {
                // First message from server, replace generating message
                if (this.currentMessage === '') {
                    this._view.webview.postMessage({
                        type: 'response',
                        content: { text: data.text, isUser: false, replaceGenerating: true }
                    });
                } else {
                    this._view.webview.postMessage({
                        type: 'response',
                        content: { text: this.currentMessage + data.text, isUser: false }
                    });
                }
                this.currentMessage += data.text;
            }

            if (data.error) {
                console.error(`[${getVersionString()}] Error from server:`, data.error);
                this._view.webview.postMessage({
                    type: 'response',
                    content: { error: data.error }
                });
            }

            if (data.done) {
                this.messages.push({ role: 'assistant', content: this.currentMessage });
                this._view.webview.postMessage({
                    type: 'response',
                    content: { done: true }
                });
                this.currentMessage = '';
            }
        } catch (error) {
            console.error(`[${getVersionString()}] Error handling message:`, error);
            this._view.webview.postMessage({
                type: 'response',
                content: { error: 'Error processing message' }
            });
        }
    }

    private updateLastMessage(text: string) {
        const messages = this.getMessages();
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            if (lastMessage.role === 'assistant') {
                lastMessage.content = text;
                this._view?.webview.postMessage({
                    type: 'response',
                    content: { text, isUser: false }
                });
            }
        }
    }

    private getMessages(): Array<{ role: string, content: string }> {
        return this.messages;
    }

    private updateMessages(messages: Array<{ role: string, content: string }>) {
        this.messages = messages;
        this._view?.webview.postMessage({
            type: 'updateMessages',
            content: messages
        });
    }

    private appendMessage(message: { role: string, content: string }) {
        this.messages.push(message);
        this._view?.webview.postMessage({
            type: 'response',
            content: { text: message.content, isUser: message.role === 'user' }
        });
    }

    private appendErrorMessage(error: string) {
        this.appendMessage({ role: 'error', content: `Error: ${error}` });
    }

    private appendDoneMessage() {
        // Optional: Add any completion indicators or cleanup here
        console.log(`[${getVersionString()}] Message stream complete`);
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'style.css'));

        console.log(`[${getVersionString()}] Loading webview resources:`, {
            scriptUri: scriptUri.toString(),
            styleUri: styleUri.toString()
        });

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="${styleUri}" rel="stylesheet">
                <title>Pydantic Agent Chat</title>
            </head>
            <body>
                <div class="chat-container">
                    <div id="chat-messages" class="messages"></div>
                    <div class="input-container">
                        <input type="text" id="message-input" placeholder="Type your message...">
                        <button id="send-button">Send</button>
                    </div>
                </div>
                <script>
                    // Initialize VS Code API before any other scripts
                    const vscode = acquireVsCodeApi();
                    console.log('VS Code API initialized');
                </script>
                <script src="${scriptUri}"></script>
            </body>
            </html>`;
    }

    private _getCurrentFileContext() {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const position = editor.selection.active;
            const cursorPosition = {
                line: position.line,
                character: position.character
            };
            
            return {
                fileName: editor.document.fileName,
                content: editor.document.getText(),
                language: editor.document.languageId,
                cursorPosition: [cursorPosition.line, cursorPosition.character]
            };
        }
        return {
            fileName: '',
            content: '',
            language: '',
            cursorPosition: [0, 0]
        };
    }
}