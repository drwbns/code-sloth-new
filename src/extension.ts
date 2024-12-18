import * as vscode from 'vscode';
import { ChatViewProvider } from './chatView';
import * as child_process from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { VERSION, BUILD_NUMBER, getVersionString } from './version';

let pythonProcess: child_process.ChildProcess | undefined;
let currentProvider: ChatViewProvider | undefined;
const outputChannel = vscode.window.createOutputChannel('Pydantic Agent');

async function getAvailablePort(): Promise<number> {
    const port = 8080;
    return port;
}

async function getPythonPath(): Promise<string> {
    let pythonPath = 'python';  // default
    try {
        const pythonConfig = vscode.workspace.getConfiguration('python');
        const configPath = pythonConfig.get<string>('defaultInterpreterPath');
        if (configPath) {
            pythonPath = configPath;
            outputChannel.appendLine(`Using Python path from settings: ${pythonPath}`);
        }
    } catch (error) {
        outputChannel.appendLine(`Error getting Python path: ${error}`);
    }
    return pythonPath;
}

async function getServerPort(): Promise<number> {
    const portFile = path.join(os.tmpdir(), 'pydantic_agent_port.txt');
    let retries = 0;
    const maxRetries = 20;  // Reduced retries since we write port immediately now
    const retryDelay = 500;  // Shorter delay

    while (retries < maxRetries) {
        try {
            if (fs.existsSync(portFile)) {
                const content = fs.readFileSync(portFile, 'utf8').trim();
                outputChannel.appendLine(`Port file content: "${content}"`);
                const port = parseInt(content, 10);
                if (!isNaN(port) && port > 0) {
                    // Verify we can connect to the port
                    try {
                        const response = await fetch(`http://localhost:${port}/health`);
                        if (response.ok) {
                            outputChannel.appendLine(`Server is responsive on port ${port}`);
                            return port;
                        }
                        outputChannel.appendLine(`Server not responsive on port ${port} yet`);
                    } catch (error) {
                        outputChannel.appendLine(`Connection test failed: ${error}`);
                    }
                } else {
                    outputChannel.appendLine(`Invalid port number: ${content}`);
                }
            } else {
                outputChannel.appendLine(`Waiting for server to write port file... (${retries + 1}/${maxRetries})`);
            }
        } catch (error) {
            outputChannel.appendLine(`Error reading port file: ${error}`);
        }
        await new Promise(resolve => setTimeout(resolve, retryDelay));
        retries++;
    }
    throw new Error('Could not determine server port after multiple retries');
}

function killProcess(process: child_process.ChildProcess) {
    return new Promise<void>((resolve) => {
        if (!process) {
            resolve();
            return;
        }

        if (process.killed) {
            resolve();
            return;
        }

        process.once('exit', () => {
            resolve();
        });

        // On Windows, we need to kill the entire process tree
        if (process.pid) {
            try {
                child_process.execSync(`taskkill /pid ${process.pid} /T /F`);
            } catch (error) {
                outputChannel.append(`Error killing process: ${error}`);
            }
        }
    });
}

async function killExistingPythonProcesses() {
    return new Promise<void>((resolve) => {
        try {
            // Kill all python processes running our server
            child_process.exec('taskkill /IM python.exe /F', (error) => {
                if (error) {
                    outputChannel.append(`No existing Python processes found or error killing them: ${error}`);
                } else {
                    outputChannel.append('Killed existing Python processes');
                }
                resolve();
            });
        } catch (error) {
            outputChannel.append(`Error in killExistingPythonProcesses: ${error}`);
            resolve();
        }
    });
}

async function startPythonServer(context: vscode.ExtensionContext): Promise<number> {
    outputChannel.show();
    outputChannel.appendLine(`[${getVersionString()}] Starting Python server...`);

    // Kill any existing processes first
    if (pythonProcess) {
        outputChannel.appendLine('Killing existing Python process');
        await killProcess(pythonProcess);
        pythonProcess = undefined;
    }
    await killExistingPythonProcesses();

    const extensionPath = context.extensionPath;
    const serverPath = path.join(extensionPath, 'src', 'python_server.py');
    outputChannel.appendLine(`Server path: ${serverPath}`);

    // Get Python path
    const pythonPath = await getPythonPath();
    outputChannel.appendLine(`Python path: ${pythonPath}`);

    return new Promise<number>((resolve, reject) => {
        try {
            // Get available port
            const port = getAvailablePort();
            outputChannel.appendLine(`Selected port: ${port}`);

            // Start Python process
            pythonProcess = child_process.spawn(pythonPath, [serverPath], {
                env: {
                    ...process.env,
                    PORT: port.toString(),
                    DEBUG: 'true',
                    LLM_API_KEY: process.env.LLM_API_KEY || '',
                    LLM_BASE_URL: process.env.LLM_BASE_URL || 'https://glhf.chat/api/openai/v1',
                    LLM_MODEL: process.env.LLM_MODEL || 'gpt-4',
                    LLM_TEMPERATURE: process.env.LLM_TEMPERATURE || '0.7'
                }
            });

            if (!pythonProcess.pid) {
                throw new Error('Failed to start Python process');
            }

            outputChannel.appendLine(`Started Python process with PID: ${pythonProcess.pid}`);

            let serverStarted = false;

            pythonProcess.stdout?.on('data', (data) => {
                const output = data.toString();
                outputChannel.append(output);
                
                if (output.includes('Server started')) {
                    serverStarted = true;
                    outputChannel.appendLine('Server started successfully');
                    resolve(port);
                }
            });

            pythonProcess.stderr?.on('data', (data) => {
                outputChannel.append(`Python server error: ${data}`);
            });

            pythonProcess.on('error', (error) => {
                outputChannel.appendLine(`Failed to start Python server: ${error}`);
                reject(error);
            });

            pythonProcess.on('exit', (code, signal) => {
                outputChannel.appendLine(`Python process exited with code ${code} and signal ${signal}`);
                if (!serverStarted) {
                    reject(new Error(`Server failed to start. Exit code: ${code}`));
                }
                pythonProcess = undefined;
            });

            // Set a timeout for server startup
            setTimeout(() => {
                if (!serverStarted) {
                    outputChannel.appendLine('Server startup timed out');
                    reject(new Error('Server startup timed out'));
                }
            }, 10000);
        } catch (error) {
            outputChannel.appendLine(`Error starting Python server: ${error}`);
            reject(error);
        }
    });
}

export async function activate(context: vscode.ExtensionContext) {
    outputChannel.appendLine(`Activating Pydantic Agent ${getVersionString()}...`);

    // Kill any existing Python processes on activation
    await killExistingPythonProcesses();

    // Register cleanup on deactivation
    context.subscriptions.push({
        dispose: async () => {
            outputChannel.appendLine(`[${getVersionString()}] Disposing extension...`);
            if (pythonProcess) {
                outputChannel.appendLine('Cleaning up Python process');
                await killProcess(pythonProcess);
                pythonProcess = undefined;
            }
            if (currentProvider) {
                outputChannel.appendLine('Cleaning up provider');
                currentProvider = undefined;
            }
        }
    });

    try {
        const port = await startPythonServer(context);
        currentProvider = new ChatViewProvider(context.extensionUri, port);

        // Register the webview provider
        context.subscriptions.push(
            vscode.window.registerWebviewViewProvider(
                ChatViewProvider.viewType,
                currentProvider
            )
        );

        outputChannel.appendLine(`[${getVersionString()}] Extension activated successfully`);
    } catch (error) {
        outputChannel.appendLine(`[${getVersionString()}] Failed to activate extension: ${error}`);
        vscode.window.showErrorMessage(`Failed to start Pydantic Agent: ${error}`);
    }
}

export async function deactivate() {
    outputChannel.appendLine('Deactivating extension...');
    
    // Clean up Python process
    if (pythonProcess) {
        outputChannel.appendLine('Killing Python process');
        await killProcess(pythonProcess);
        pythonProcess = undefined;
    }

    // Clean up port file
    try {
        const portFile = path.join(os.tmpdir(), 'pydantic_agent_port.txt');
        if (fs.existsSync(portFile)) {
            outputChannel.appendLine(`Removing port file: ${portFile}`);
            fs.unlinkSync(portFile);
        }
    } catch (error) {
        outputChannel.appendLine(`Error cleaning up port file: ${error}`);
    }

    // Clean up provider
    if (currentProvider) {
        outputChannel.appendLine('Cleaning up provider');
        currentProvider = undefined;
    }

    outputChannel.appendLine('Extension deactivated');
}