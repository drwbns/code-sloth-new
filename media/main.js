// Get VS Code API
const vscode = acquireVsCodeApi();

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

console.log('Chat view initialized');

function displayMessage(text, isUser) {
    console.log('Displaying message:', { text, isUser });
    const messageDiv = document.createElement('div');
    messageDiv.className = isUser ? 'user-message' : 'assistant-message';
    messageDiv.textContent = text || '';
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function displayGeneratingMessage() {
    console.log('Displaying generating message');
    const generatingDiv = document.createElement('div');
    generatingDiv.className = 'message system generating';
    generatingDiv.id = 'generating-message';
    generatingDiv.textContent = 'Generating...';
    chatMessages.appendChild(generatingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeGeneratingMessage() {
    console.log('Removing generating message');
    const generatingMessage = document.getElementById('generating-message');
    if (generatingMessage) {
        generatingMessage.remove();
    }
}

function displayErrorMessage(error) {
    console.error('Displaying error message:', error);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error';
    errorDiv.textContent = `Error: ${error}`;
    chatMessages.appendChild(errorDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Send ready message when DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, sending ready message');
    vscode.postMessage({ type: 'ready' });
});

// Handle messages from the extension
window.addEventListener('message', event => {
    const message = event.data;
    console.log('Received message from extension:', message);

    if (message.type === 'init') {
        console.log('Received init message, sending ready');
        vscode.postMessage({ type: 'ready' });
        return;
    }

    if (message.type === 'response') {
        const content = message.content;
        console.log('Processing response content:', content);
        
        if (content.error) {
            console.error('Displaying error:', content.error);
            displayErrorMessage(content.error);
            return;
        }

        if (content.isGenerating) {
            console.log('Displaying generating message');
            displayGeneratingMessage();
            return;
        }

        if (content.done) {
            console.log('Removing generating message');
            removeGeneratingMessage();
            return;
        }

        if (content.text !== undefined) {
            console.log('Displaying message:', content.text);
            if (content.replaceGenerating) {
                console.log('Replacing generating message');
                removeGeneratingMessage();
            }
            displayMessage(content.text, content.isUser);
        } else {
            console.warn('Received response with no text:', content);
        }
    }
});

// Send message to extension
function sendMessage() {
    const messageText = userInput.value.trim();
    if (messageText) {
        console.log('Sending message to extension:', messageText);
        vscode.postMessage({ 
            type: 'sendMessage',
            message: messageText
        });
        userInput.value = '';
    }
}

// Event listeners
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Verify elements are found
console.log('Elements found:', {
    chatMessages: !!chatMessages,
    userInput: !!userInput,
    sendButton: !!sendButton
});
