// Get VS Code API
const vscode = acquireVsCodeApi();

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

console.log('Chat view initialized');

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
let currentMessageDiv = null;
let messageBuffer = '';

function displayMessage(text, isUser) {
    console.log('Displaying message:', { text, isUser });
    
    // Always create new div for each message
    currentMessageDiv = document.createElement('div');
    if (isUser) {
        currentMessageDiv.className = 'user-message';
    } else {
        currentMessageDiv.className = 'assistant-message';
    }
    currentMessageDiv.textContent = text;
    chatMessages.appendChild(currentMessageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update the message event handler
window.addEventListener('message', event => {
    const message = event.data;
    console.log('Received message from extension:', message);

    if (message.type === 'response') {
        const content = message.content;
        
        if (content.error) {
            displayErrorMessage(content.error);
            return;
        }

        if (content.type === 'start') {
            console.log('Start new message');
            removeGeneratingMessage();
            currentMessageDiv = null; // Clear current message div
            return;
        }

        if (content.type === 'done') {
            console.log('Message completed');
            currentMessageDiv = null;
            return;
        }

        if (content.text !== undefined && content.text !== "") {
            if (content.replaceGenerating) {
                removeGeneratingMessage();
            }
            displayMessage(content.text, content.isUser);
        } else {
            console.log('Skipping message with undefined or empty text:', content);
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
