function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.add('hidden');
    });
    
    document.getElementById(`${tabName}-tab`).classList.remove('hidden');
    
    document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('onclick').includes(tabName)) {
            link.classList.add('text-gray-900', 'border-indigo-500');
            link.classList.remove('text-gray-500', 'border-transparent', 'hover:border-gray-300');
        } else {
            link.classList.remove('text-gray-900', 'border-indigo-500');
            link.classList.add('text-gray-500', 'border-transparent', 'hover:border-gray-300');
        }
    });

    // Handle WebSocket connection for live tab - keep connection alive once established
    if (tabName === 'live') {
        if (!logWebSocket) {
            logWebSocket = new LogWebSocket();
            logWebSocket.connect();
        }
    }
    // Don't disconnect when switching tabs - this keeps the connection alive during app navigation
}

// Enhanced tab switching function to load agent state
const originalShowTab = showTab;
showTab = function(tabName) {
    originalShowTab(tabName);
    
    // When switching to the agent tab, refresh the state
    if (tabName === 'agent') {
        refreshAgentState();
    }
};

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.classList.remove('hidden', 'bg-green-500', 'bg-red-500');
    notification.classList.add(type === 'success' ? 'bg-green-500' : 'bg-red-500');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

function updateFileName(input) {
    const filenameElement = document.getElementById('selected-filename');
    if (input.files && input.files[0]) {
        filenameElement.textContent = `Selected file: ${input.files[0].name}`;
        filenameElement.classList.remove('hidden');
    } else {
        filenameElement.classList.add('hidden');
    }
}

function setUploadingState(isUploading) {
    const button = document.getElementById('upload-button');
    const spinner = document.getElementById('upload-spinner');
    const text = document.getElementById('upload-text');
    
    button.disabled = isUploading;
    if (isUploading) {
        spinner.classList.remove('hidden');
        text.textContent = 'Uploading...';
        button.classList.add('opacity-75', 'cursor-not-allowed');
    } else {
        spinner.classList.add('hidden');
        text.textContent = 'Upload and Process';
        button.classList.remove('opacity-75', 'cursor-not-allowed');
    }
}

document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    
    try {
        setUploadingState(true);
        const response = await fetch('/ingest/file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(result.message);
            e.target.reset();
            document.getElementById('selected-filename').classList.add('hidden');
        } else {
            showNotification(result.detail || 'Error uploading file', 'error');
        }
    } catch (error) {
        showNotification('Error uploading file: ' + error.message, 'error');
    } finally {
        setUploadingState(false);
    }
});

marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
    sanitize: true
});

function renderMarkdown(text) {
    try {
        return marked.parse(text);
    } catch (error) {
        console.error('Error parsing markdown:', error);
        return text;
    }
}

// Query form submission handling
document.getElementById('query-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    updateAgentStateIndicator('analyzing');
    
    const query = e.target.query.value;
    const includeContext = document.getElementById('include-context').checked;
    const includeLogs = document.getElementById('include-logs').checked;
    const resultsDiv = document.getElementById('query-results');
    
    const queryButton = document.getElementById('query-button');
    const querySpinner = document.getElementById('query-spinner');
    const queryText = document.getElementById('query-text');
    
    queryButton.disabled = true;
    querySpinner.classList.remove('hidden');
    queryText.textContent = 'Analyzing...';
    
    resultsDiv.innerHTML = '<div class="text-center py-6"><div class="inline-block animate-spin h-8 w-8 border-4 border-indigo-500 border-t-transparent rounded-full"></div><p class="mt-2 text-gray-600">AI is analyzing your query...</p></div>';
    
    try {
        const response = await fetch('/queries/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                max_logs: 100,
                include_context: includeContext
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            let html = `
                <div class="mb-4 p-4 bg-gray-50 rounded-md">
                    <h3 class="font-medium text-gray-900">Analysis</h3>
                    <div class="mt-2 text-gray-600 markdown-content">${renderMarkdown(result.analysis)}</div>
                </div>
            `;
            
            if (includeLogs && result.logs && result.logs.length > 0) {
                html += `
                    <div>
                        <h3 class="font-medium text-gray-900 mb-2">Logs (${result.logs.length})</h3>
                        <div class="space-y-2">
                `;
                
                result.logs.forEach(log => {
                    const level = log.level || 'INFO';
                    const levelClass = {
                        'ERROR': 'text-red-600',
                        'WARN': 'text-yellow-600',
                        'INFO': 'text-blue-600',
                        'DEBUG': 'text-gray-600'
                    }[level] || 'text-gray-600';
                    
                    html += `
                        <div class="p-3 bg-white shadow-sm rounded-md">
                            <div class="flex justify-between items-start">
                                <span class="${levelClass} font-medium">${level}</span>
                                <div class="flex flex-col items-end">
                                    <span class="text-gray-500 text-sm">${new Date(log.timestamp).toLocaleString()}</span>
                                    <span class="text-gray-400 text-xs">${log.service || 'unknown'}</span>
                                </div>
                            </div>
                            <div class="mt-1 text-gray-900 markdown-content">${renderMarkdown(log.message)}</div>
                        </div>
                    `;
                });
                
                html += '</div></div>';
            }
            
            resultsDiv.innerHTML = html;
            
            // After query completes, refresh agent state
            setTimeout(refreshAgentState, 1000);
        } else {
            resultsDiv.innerHTML = `<div class="text-red-600">${result.detail || 'Error querying logs'}</div>`;
            updateAgentStateIndicator('error');
        }
    } catch (error) {
        resultsDiv.innerHTML = `<div class="text-red-600">Error querying logs: ${error.message}</div>`;
        updateAgentStateIndicator('error');
    } finally {
        queryButton.disabled = false;
        querySpinner.classList.add('hidden');
        queryText.textContent = 'Search';
    }
});

class LogWebSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.msgCount = 0;
        this.isReconnecting = false;
    }

    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected, reusing connection");
            return;
        }
        
        if (this.isReconnecting) {
            console.log("Already attempting to reconnect, skipping duplicate request");
            return;
        }

        this.isReconnecting = true;
        
        try {
            // Clear the logs div first, but only if there are no logs yet
            const logsDiv = document.getElementById('live-logs');
            if (logsDiv && (logsDiv.children.length === 0 || !this.msgCount)) {
                logsDiv.innerHTML = '<div class="text-center py-6"><div class="inline-block animate-spin h-8 w-8 border-4 border-indigo-500 border-t-transparent rounded-full"></div><p class="mt-2 text-gray-400">Connecting to log stream...</p></div>';
            }
            
            // Create a new WebSocket connection
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/logs/ws`;
            console.log(`Attempting to connect to WebSocket at ${wsUrl}`);
            
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = this._onOpen.bind(this);
            this.socket.onclose = this._onClose.bind(this);
            this.socket.onerror = this._onError.bind(this);
            this.socket.onmessage = this._onMessage.bind(this);
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this._handleError(error);
            this._scheduleReconnect();
        } finally {
            this.isReconnecting = false;
        }
    }

    disconnect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            console.log("Explicitly closing WebSocket connection");
            // Use a clean close reason
            this.socket.close(1000, "Normal closure");
            this.socket = null;
        }
        this.reconnectAttempts = 0;
    }

    _onOpen(event) {
        console.log('WebSocket connected successfully');
        const logsDiv = document.getElementById('live-logs');
        logsDiv.innerHTML = '<div class="text-sm text-gray-400 mb-4">Connected to log stream. Waiting for logs...</div>';
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        // Add a status indicator
        const statusDiv = document.createElement('div');
        statusDiv.id = 'ws-status';
        statusDiv.className = 'fixed top-4 right-4 bg-green-500 text-white px-3 py-1 text-xs rounded-full';
        statusDiv.textContent = 'Live: Connected';
        document.body.appendChild(statusDiv);
    }

    _onClose(event) {
        console.log(`WebSocket closed, code: ${event.code}, reason: ${event.reason}`);
        const statusDiv = document.getElementById('ws-status');
        if (statusDiv) {
            statusDiv.className = 'fixed top-4 right-4 bg-red-500 text-white px-3 py-1 text-xs rounded-full';
            statusDiv.textContent = 'Live: Disconnected';
        }
        this._scheduleReconnect();
    }

    _onError(error) {
        console.error('WebSocket error:', error);
        this._handleError(error);
        this._scheduleReconnect();
    }

    _onMessage(event) {
        this.msgCount++;
        try {
            console.log(`Received WebSocket message #${this.msgCount}: ${event.data.substring(0, 50)}...`);
            const log = JSON.parse(event.data);
            const logsDiv = document.getElementById('live-logs');
            
            // Remove the "waiting for logs" message on first log
            if (this.msgCount === 1) {
                logsDiv.innerHTML = '';
            }
            
            // Update the status indicator
            const statusDiv = document.getElementById('ws-status');
            if (statusDiv) {
                statusDiv.textContent = `Live: ${this.msgCount} logs`;
            }
            
            const level = log.level || 'INFO';
            const levelClass = {
                'ERROR': 'text-red-500',
                'WARN': 'text-yellow-500',
                'INFO': 'text-blue-500',
                'DEBUG': 'text-gray-500'
            }[level] || 'text-gray-500';
            
            const logEntry = document.createElement('div');
            logEntry.className = 'mb-4 p-2 border-l-4 border-gray-700';
            
            // Determine if this is a markdown-formatted log or a simple log
            const isMarkdownLog = log.message && (
                log.message.includes('#') || 
                log.message.includes('```') || 
                log.message.includes('|') ||
                log.message.includes('- ') ||
                log.message.includes('> ')
            );
            
            // Create header with metadata
            const header = document.createElement('div');
            header.className = 'flex justify-between items-start mb-2';
            
            // Left side: level and service
            const leftSide = document.createElement('div');
            leftSide.className = 'flex items-center';
            leftSide.innerHTML = `
                <span class="${levelClass} font-medium mr-2">[${level}]</span>
                <span class="text-gray-300">${log.service || 'unknown'}</span>
            `;
            
            // Right side: timestamp and producer
            const rightSide = document.createElement('div');
            rightSide.className = 'text-right';
            rightSide.innerHTML = `
                <div class="text-gray-400 text-xs">${new Date(log.timestamp).toLocaleString()}</div>
                <div class="text-gray-500 text-xs">${log.producer_id || 'unknown'}</div>
            `;
            
            header.appendChild(leftSide);
            header.appendChild(rightSide);
            logEntry.appendChild(header);
            
            // Content with special handling for markdown
            const content = document.createElement('div');
            if (isMarkdownLog) {
                content.className = 'text-white markdown-content bg-gray-800 p-3 rounded-md overflow-auto';
                content.innerHTML = renderMarkdown(log.message);
                
                // Add a special indicator for markdown logs
                const markdownBadge = document.createElement('div');
                markdownBadge.className = 'text-xs text-gray-400 mt-1 mb-2';
                markdownBadge.textContent = '✨ Markdown formatted log';
                logEntry.insertBefore(markdownBadge, content);
            } else {
                content.className = 'text-white';
                content.textContent = log.message;
            }
            
            logEntry.appendChild(content);
            
            // Add metadata section if present
            if (log.metadata && Object.keys(log.metadata).length > 0) {
                const metadataToggle = document.createElement('button');
                metadataToggle.className = 'text-xs text-gray-400 mt-2 hover:text-gray-300';
                metadataToggle.textContent = 'Show metadata';
                
                const metadataContent = document.createElement('pre');
                metadataContent.className = 'text-xs text-gray-400 mt-1 hidden';
                metadataContent.textContent = JSON.stringify(log.metadata, null, 2);
                
                metadataToggle.addEventListener('click', () => {
                    if (metadataContent.classList.contains('hidden')) {
                        metadataContent.classList.remove('hidden');
                        metadataToggle.textContent = 'Hide metadata';
                    } else {
                        metadataContent.classList.add('hidden');
                        metadataToggle.textContent = 'Show metadata';
                    }
                });
                
                logEntry.appendChild(metadataToggle);
                logEntry.appendChild(metadataContent);
            }
            
            logsDiv.appendChild(logEntry);
            
            // Scroll to the bottom if we're already at the bottom
            const isAtBottom = logsDiv.scrollHeight - logsDiv.clientHeight <= logsDiv.scrollTop + 50;
            if (isAtBottom) {
                logsDiv.scrollTop = logsDiv.scrollHeight;
            }
            
            // Limit the number of logs to keep memory usage reasonable
            while (logsDiv.children.length > 300) {
                logsDiv.removeChild(logsDiv.firstChild);
            }
        } catch (error) {
            console.error('Error processing log message:', error, event.data);
            this._handleError(error);
        }
    }
    
    _handleError(error) {
        const logsDiv = document.getElementById('live-logs');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-500 p-2 mb-2 bg-red-100 bg-opacity-20 rounded';
        errorDiv.textContent = `WebSocket error: ${error.message || 'Unknown error'}`;
        logsDiv.appendChild(errorDiv);
        
        // Add "Retry" button
        const retryBtn = document.createElement('button');
        retryBtn.className = 'mt-2 bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded text-sm';
        retryBtn.textContent = 'Retry Connection';
        retryBtn.onclick = () => this.connect();
        errorDiv.appendChild(document.createElement('br'));
        errorDiv.appendChild(retryBtn);
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
                console.log(`Attempting to reconnect (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})...`);
                this.connect();
                this.reconnectAttempts++;
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000); // Exponential backoff, max 10 seconds
            }, this.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
            const logsDiv = document.getElementById('live-logs');
            logsDiv.innerHTML += `
                <div class="text-red-500 p-4 border border-red-300 rounded-md my-4">
                    <p class="font-medium">Connection lost</p>
                    <p class="text-sm mt-1">Max reconnection attempts reached (${this.maxReconnectAttempts}).</p>
                    <button id="force-reconnect" class="mt-2 bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded text-sm">
                        Try Again
                    </button>
                </div>
            `;
            
            document.getElementById('force-reconnect').addEventListener('click', () => {
                this.reconnectAttempts = 0;
                this.connect();
            });
        }
    }
}

let logWebSocket = null;

document.addEventListener('visibilitychange', () => {
    // Only reconnect if the page becomes visible and we're on the live tab
    const liveTab = document.getElementById('live-tab');
    
    // Check if live tab exists before accessing it
    if (document.visibilityState === 'visible' && liveTab && !liveTab.classList.contains('hidden')) {
        if (!logWebSocket) {
            logWebSocket = new LogWebSocket();
            logWebSocket.connect();
        }
    }
    // Don't disconnect when the page becomes hidden - this keeps the connection alive
    // when switching tabs in the browser
});

// Agent state management
let currentAgentState = null;
let isAgentStateRefreshing = false;

// Initialize when document is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize toggle button for raw state
    document.getElementById('toggle-raw-state').addEventListener('click', (e) => {
        const rawStateDiv = document.getElementById('raw-agent-state');
        const button = e.target;
        
        if (rawStateDiv.classList.contains('hidden')) {
            rawStateDiv.classList.remove('hidden');
            button.textContent = 'Hide';
        } else {
            rawStateDiv.classList.add('hidden');
            button.textContent = 'Show';
        }
    });
    
    // Set up model selector dropdown
    setupModelSelector();
    
    // Initial agent state fetch
    refreshAgentState();
});

// Model selector functionality
function setupModelSelector() {
    const modelButton = document.getElementById('model-selector-button');
    const modelDropdown = document.getElementById('model-selector-dropdown');
    
    // Toggle dropdown when button is clicked
    modelButton.addEventListener('click', () => {
        modelDropdown.classList.toggle('hidden');
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!modelButton.contains(e.target) && !modelDropdown.contains(e.target)) {
            modelDropdown.classList.add('hidden');
        }
    });
    
    // Add click handlers to all model options
    document.querySelectorAll('.model-option').forEach(option => {
        option.addEventListener('click', async (e) => {
            e.preventDefault();
            modelDropdown.classList.add('hidden');
            
            const provider = option.dataset.provider;
            const model = option.dataset.model;
            
            await switchModel(provider, model);
        });
    });
    
    // Get current model on load
    getCurrentModel();
}

async function getCurrentModel() {
    try {
        const response = await fetch('/queries/current-model');
        if (!response.ok) {
            throw new Error('Failed to get current model');
        }
        
        const data = await response.json();
        updateCurrentModelDisplay(data.provider, data.model);
    } catch (error) {
        console.error('Error getting current model:', error);
        showNotification('Error getting current model', 'error');
    }
}

async function switchModel(provider, model) {
    const button = document.getElementById('model-selector-button');
    const originalContent = button.innerHTML;
    
    try {
        // Show loading state
        button.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Switching...
        `;
        button.disabled = true;
        
        const response = await fetch('/queries/set-model', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model_id: model,
                provider: provider
            })
        });
        
        // Parse response but don't throw yet
        const result = await response.json();
        
        if (!response.ok) {
            // Handle API error
            throw new Error(result.detail || 'Failed to switch model');
        }
        
        // If successful, update the UI
        updateCurrentModelDisplay(provider, model);
        showNotification(`Model switched to ${getModelDisplayName(provider, model)}`);
        
        // After model change, refresh agent state
        await refreshAgentState();
        
    } catch (error) {
        console.error('Error switching model:', error);
        
        // Check if it's an authentication error
        if (error.message.includes('API key') || error.message.includes('Authentication')) {
            // Show error notification with fallback message
            showNotification(`Error with ${provider} API key. System will fall back to Google provider for queries.`, 'error');
            
            // Update UI to indicate fallback behavior
            const displayElement = document.getElementById('current-model-display');
            if (displayElement) {
                displayElement.innerHTML = `<span class="text-yellow-600">⚠️ ${getModelDisplayName(provider, model)}</span>
                                           <span class="text-xs block">(Will use Google for queries)</span>`;
            }
        } else {
            // Generic error
            showNotification(`Error switching model: ${error.message}`, 'error');
        }
        
        // Refresh the agent state to make sure UI is in sync with backend
        await refreshAgentState();
    } finally {
        // Restore button
        button.innerHTML = originalContent;
        button.disabled = false;
    }
}

function updateCurrentModelDisplay(provider, model) {
    const displayElement = document.getElementById('current-model-display');
    
    // Check if display element exists before trying to update it
    if (!displayElement) {
        console.warn('Model display element not found. This may happen if switching models from a different tab.');
        return;
    }
    
    displayElement.textContent = getModelDisplayName(provider, model);
    
    // Update the active class on the selected model in the dropdown
    document.querySelectorAll('.model-option').forEach(option => {
        if (option.dataset.provider === provider && option.dataset.model === model) {
            option.classList.add('bg-indigo-50', 'text-indigo-700');
        } else {
            option.classList.remove('bg-indigo-50', 'text-indigo-700');
        }
    });
}

function getModelDisplayName(provider, model) {
    // Map of provider+model to display names
    const modelDisplayNames = {
        'google:gemini-1.5-pro': 'Gemini 1.5 Pro',
        'google:gemini-pro': 'Gemini Pro',
        'openai:gpt-4o': 'GPT-4o',
        'openai:gpt-4-turbo': 'GPT-4 Turbo',
        'openai:gpt-3.5-turbo': 'GPT-3.5 Turbo',
        'anthropic:claude-3-opus-20240229': 'Claude 3 Opus',
        'anthropic:claude-3-sonnet-20240229': 'Claude 3 Sonnet',
        'anthropic:claude-3-haiku-20240307': 'Claude 3 Haiku',
        'groq:llama3-70b-8192': 'Llama 3 70B',
        'groq:llama3-8b-8192': 'Llama 3 8B',
        'groq:mixtral-8x7b-32768': 'Mixtral 8x7B'
    };
    
    return modelDisplayNames[`${provider}:${model}`] || `${provider} ${model}`;
}

async function refreshAgentState() {
    if (isAgentStateRefreshing) return;
    
    try {
        isAgentStateRefreshing = true;
        updateAgentStateIndicator('refreshing');
        
        const response = await fetch('/queries/insights');
        if (!response.ok) {
            throw new Error(`Failed to fetch agent state: ${response.status}`);
        }
        
        const agentState = await response.json();
        currentAgentState = agentState;
        
        // Update the UI with the new state
        updateAgentStateUI(agentState);
        updateAgentStateIndicator('idle');
    } catch (error) {
        console.error('Error fetching agent state:', error);
        updateAgentStateIndicator('error');
    } finally {
        isAgentStateRefreshing = false;
    }
}

function updateAgentStateUI(state) {
    // Update the raw state JSON view
    const rawStateElement = document.querySelector('#raw-agent-state pre');
    if (rawStateElement) {
        rawStateElement.textContent = JSON.stringify(state, null, 2);
    }
    
    // Update agent status
    const lastActivity = state.conversation_history && state.conversation_history.length > 0 
        ? new Date(state.conversation_history[state.conversation_history.length - 1].timestamp)
        : new Date();
    
    document.getElementById('agent-last-activity').textContent = formatTimeAgo(lastActivity);
    document.getElementById('agent-memory-usage').textContent = calculateMemoryUsage(state);
    
    // Update knowledge stats
    const knownIssuesCount = (state.known_issues || []).length;
    document.getElementById('known-issues-count').textContent = knownIssuesCount;
    
    const patternsCount = Object.keys(state.patterns || {}).length;
    document.getElementById('patterns-count').textContent = patternsCount;
    
    const conversationCount = (state.conversation_history || []).length;
    document.getElementById('conversation-count').textContent = conversationCount;
    
    // Update system health insights
    updateSystemHealthFromState(state);
    
    // Update findings timeline
    updateFindingsTimeline(state);
}

function updateAgentStateIndicator(state) {
    const indicator = document.getElementById('agent-state-indicator');
    const statusDot = indicator.querySelector('span:first-child');
    const statusText = indicator.querySelector('span:last-child');
    
    indicator.classList.remove(
        'bg-blue-100', 'text-blue-800',
        'bg-green-100', 'text-green-800',
        'bg-yellow-100', 'text-yellow-800',
        'bg-red-100', 'text-red-800'
    );
    
    statusDot.classList.remove(
        'bg-blue-600', 'bg-green-500', 'bg-yellow-500', 'bg-red-500'
    );
    
    switch (state) {
        case 'idle':
            indicator.classList.add('bg-blue-100', 'text-blue-800');
            statusDot.classList.add('bg-blue-600');
            statusText.textContent = 'Idle';
            
            // Also update the agent tab status indicator
            document.getElementById('agent-status-indicator').className = 'h-3 w-3 rounded-full bg-blue-500 mr-2';
            document.getElementById('agent-status-text').textContent = 'Idle';
            break;
            
        case 'analyzing':
            indicator.classList.add('bg-green-100', 'text-green-800');
            statusDot.classList.add('bg-green-500');
            statusText.textContent = 'Analyzing';
            
            // Also update the agent tab status indicator
            document.getElementById('agent-status-indicator').className = 'h-3 w-3 rounded-full bg-green-500 mr-2 animate-pulse';
            document.getElementById('agent-status-text').textContent = 'Analyzing';
            break;
            
        case 'refreshing':
            indicator.classList.add('bg-yellow-100', 'text-yellow-800');
            statusDot.classList.add('bg-yellow-500');
            statusText.textContent = 'Refreshing...';
            break;
            
        case 'error':
            indicator.classList.add('bg-red-100', 'text-red-800');
            statusDot.classList.add('bg-red-500');
            statusText.textContent = 'Error';
            
            // Also update the agent tab status indicator
            document.getElementById('agent-status-indicator').className = 'h-3 w-3 rounded-full bg-red-500 mr-2';
            document.getElementById('agent-status-text').textContent = 'Error';
            break;
    }
}

function updateSystemHealthFromState(state) {
    // Count errors and warnings from the findings
    let criticalErrors = 0;
    let warningCount = 0;
    const serviceHealth = {};
    
    // Extract system health information from findings
    if (state.findings && state.findings.length > 0) {
        state.findings.forEach(finding => {
            const lowercaseAnalysis = finding.analysis.toLowerCase();
            
            // Count critical errors
            if (
                lowercaseAnalysis.includes('critical error') || 
                lowercaseAnalysis.includes('severe issue') ||
                lowercaseAnalysis.includes('urgent problem')
            ) {
                criticalErrors++;
            }
            
            // Count warnings
            if (
                lowercaseAnalysis.includes('warning') || 
                lowercaseAnalysis.includes('potential issue') ||
                lowercaseAnalysis.includes('might be problematic')
            ) {
                warningCount++;
            }
            
            // Extract service names and track health
            const serviceMatches = finding.analysis.match(/service[:\s]+([a-zA-Z0-9-_]+)/gi);
            if (serviceMatches) {
                serviceMatches.forEach(match => {
                    const service = match.replace(/service[:\s]+/i, '').trim();
                    if (lowercaseAnalysis.includes('error') && service) {
                        serviceHealth[service] = 'error';
                    } else if (lowercaseAnalysis.includes('warning') && service) {
                        serviceHealth[service] !== 'error' ? 'warning' : serviceHealth[service];
                    } else if (service) {
                        serviceHealth[service] = serviceHealth[service] || 'healthy';
                    }
                });
            }
        });
    }
    
    // Update the UI
    document.getElementById('critical-errors').textContent = criticalErrors;
    document.getElementById('warning-count').textContent = warningCount;
    
    const healthyServices = Object.values(serviceHealth).filter(health => health === 'healthy').length;
    document.getElementById('healthy-services').textContent = 
        healthyServices + '/' + Object.keys(serviceHealth).length;
}

function updateFindingsTimeline(state) {
    const timelineEl = document.getElementById('findings-timeline');
    
    // No findings available
    if (!state.findings || state.findings.length === 0) {
        timelineEl.innerHTML = '<div class="text-sm text-gray-500 text-center py-6">No findings available yet.</div>';
        return;
    }
    
    // Sort findings by timestamp (newest first)
    const sortedFindings = [...state.findings].sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
    );
    
    let timelineHTML = '';
    
    sortedFindings.forEach((finding, index) => {
        // Extract a title from the analysis (first line or sentence)
        let title = finding.query;
        if (title.length > 70) {
            title = title.substring(0, 70) + '...';
        }
        
        const timestamp = new Date(finding.timestamp);
        
        // Create a finding card with time and analysis excerpt
        timelineHTML += `
            <div class="relative pb-4 ${index < sortedFindings.length - 1 ? 'border-l-2 border-gray-200 pl-6' : 'pl-6'}">
                <div class="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-indigo-500"></div>
                <div class="bg-white rounded-lg shadow-sm p-4">
                    <div class="flex justify-between items-start mb-2">
                        <h4 class="text-sm font-medium text-gray-900">${title}</h4>
                        <span class="text-xs text-gray-500">${formatTimeAgo(timestamp)}</span>
                    </div>
                    <div class="text-sm text-gray-600 markdown-content">
                        ${renderMarkdown(truncateAnalysis(finding.analysis, 150))}
                    </div>
                </div>
            </div>
        `;
    });
    
    timelineEl.innerHTML = timelineHTML;
}

function truncateAnalysis(analysis, maxLength) {
    if (analysis.length <= maxLength) return analysis;
    
    // Find a convenient break point
    const breakPoint = analysis.lastIndexOf('.', maxLength);
    if (breakPoint > maxLength * 0.7) {
        return analysis.substring(0, breakPoint + 1) + ' [...]';
    }
    
    return analysis.substring(0, maxLength) + ' [...]';
}

function calculateMemoryUsage(state) {
    let count = 0;
    
    // Count conversation history
    count += (state.conversation_history || []).length;
    
    // Count findings
    count += (state.findings || []).length;
    
    // Count known issues
    count += (state.known_issues || []).length;
    
    // Count patterns
    count += Object.keys(state.patterns || {}).length;
    
    return count;
}

function formatTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHrs = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHrs / 24);
    
    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${diffDays}d ago`;
}

// Initialize the active tab based on URL hash or default to ingest
function initializeActiveTab() {
    const hash = window.location.hash.substring(1);
    if (hash && ['ingest', 'query', 'agent', 'live'].includes(hash)) {
        showTab(hash);
    } else {
        showTab('ingest');
    }
}

// Call on page load
window.addEventListener('DOMContentLoaded', initializeActiveTab);
window.addEventListener('hashchange', initializeActiveTab);

// Database connection and log streaming functionality
class DatabaseLogStreamer {
    constructor() {
        this.connected = false;
        this.paused = false;
        this.connectionConfig = null;
        this.streamInterval = null;
        this.logCount = 0;
        this.lastTimestamp = null;
        this.savedConnections = this.loadSavedConnections();
        this.availableTables = [];
    }

    // Connect to database and start streaming logs
    async connect(config) {
        try {
            this.connectionConfig = config;
            
            // Show connecting state
            const logsContainer = document.getElementById('db-logs-container');
            logsContainer.innerHTML = '<div class="text-center py-6"><div class="inline-block animate-spin h-8 w-8 border-4 border-indigo-500 border-t-transparent rounded-full"></div><p class="mt-2 text-gray-500">Connecting to database...</p></div>';
            
            // Test connection first
            const testResponse = await fetch('/ingest/database/test-connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            if (!testResponse.ok) {
                const error = await testResponse.json();
                throw new Error(error.detail || 'Failed to connect to database');
            }
            
            // Connection successful, set up streaming
            this.connected = true;
            this.paused = false;
            this.logCount = 0;
            this.lastTimestamp = null;
            
            // Start the polling/streaming interval
            this.startStreaming();
            
            // Update UI
            this.updateUIForConnectedState();
            
            // Save the connection if requested
            if (config.save_connection) {
                this.saveConnection(config);
            }
            
            return true;
        } catch (error) {
            console.error('Database connection error:', error);
            const logsContainer = document.getElementById('db-logs-container');
            logsContainer.innerHTML = `<div class="text-red-500 p-4"><p class="font-medium">Connection Error</p><p>${error.message}</p></div>`;
            return false;
        }
    }

    // List available tables in the database
    async listTables(config) {
        try {
            // Show loading state for table list
            const tablesList = document.getElementById('tables-list');
            tablesList.innerHTML = '<div class="text-center py-4"><div class="inline-block animate-spin h-5 w-5 border-2 border-indigo-500 border-t-transparent rounded-full"></div><p class="mt-2 text-sm text-gray-500">Retrieving tables...</p></div>';
            
            // Ensure the table browser section is visible
            document.getElementById('table-browser-section').classList.remove('hidden');
            
            // Fetch tables from the API
            const response = await fetch('/ingest/database/list-tables', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to list tables');
            }
            
            const result = await response.json();
            this.availableTables = result.tables || [];
            
            if (this.availableTables.length === 0) {
                tablesList.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">No tables found in database.</p>';
                return;
            }
            
            // Display the tables with selection buttons
            let html = '<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">';
            
            this.availableTables.forEach(table => {
                html += `
                    <div class="p-2 border border-gray-200 rounded flex justify-between items-center">
                        <span class="text-sm text-gray-700">${table}</span>
                        <button type="button" data-table="${table}" class="select-table-btn px-2 py-1 text-xs text-white bg-indigo-500 hover:bg-indigo-600 rounded">
                            Select
                        </button>
                    </div>
                `;
            });
            
            html += '</div>';
            tablesList.innerHTML = html;
            
            // Add event listeners for table selection
            document.querySelectorAll('.select-table-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const tableName = e.target.dataset.table;
                    this.selectTable(tableName);
                });
            });
            
            return this.availableTables;
        } catch (error) {
            console.error('Error listing tables:', error);
            const tablesList = document.getElementById('tables-list');
            tablesList.innerHTML = `<div class="text-red-500 p-2 text-sm">Error listing tables: ${error.message}</div>`;
            return [];
        }
    }
    
    // Handle table selection
    selectTable(tableName) {
        // Set the selected table in the log_query field
        const queryField = document.querySelector('textarea[name="log_query"]');
        queryField.value = tableName;
        
        // Show a notification
        showNotification(`Selected table: ${tableName}`);
        
        // Suggest field mappings based on table name (if it looks like a logs table)
        this.suggestFieldMappings(tableName);
    }
    
    // Suggest field mappings based on table name
    suggestFieldMappings(tableName) {
        const lowerTableName = tableName.toLowerCase();
        
        // Only make suggestions for tables that seem to be log tables
        if (lowerTableName.includes('log') || lowerTableName.includes('event')) {
            // Common field mapping patterns
            const mappingSuggestions = {
                // For tables named 'logs'
                'logs': {
                    timestamp: 'timestamp',
                    level: 'level',
                    message: 'message',
                    service: 'service'
                },
                // For tables named 'events' or 'log_events'
                'events': {
                    timestamp: 'created_at',
                    level: 'severity',
                    message: 'description',
                    service: 'source'
                },
                'log_events': {
                    timestamp: 'created_at',
                    level: 'level',
                    message: 'message',
                    service: 'service_name'
                },
                // For tables with 'audit' in the name
                'audit': {
                    timestamp: 'timestamp',
                    level: 'action_type',
                    message: 'details',
                    service: 'user_id'
                }
            };
            
            // Find the best matching pattern
            let bestMatch = null;
            
            for (const pattern in mappingSuggestions) {
                if (lowerTableName.includes(pattern)) {
                    bestMatch = pattern;
                    break;
                }
            }
            
            // Apply suggestions if a match was found
            if (bestMatch) {
                const mappings = mappingSuggestions[bestMatch];
                
                document.querySelector('input[name="timestamp_field"]').value = mappings.timestamp;
                document.querySelector('input[name="level_field"]').value = mappings.level;
                document.querySelector('input[name="message_field"]').value = mappings.message;
                document.querySelector('input[name="service_field"]').value = mappings.service;
            }
        }
    }
    
    // Start streaming logs using polling or WebSocket
    startStreaming() {
        // Clear any existing interval
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
        }
        
        // Start with an immediate fetch
        this.fetchLogs();
        
        // Then set up regular polling
        const interval = this.connectionConfig.refresh_interval * 1000 || 10000; // Default to 10 seconds
        this.streamInterval = setInterval(() => {
            if (!this.paused && this.connected) {
                this.fetchLogs();
            }
        }, interval);
    }

    // Fetch logs from the server
    async fetchLogs() {
        if (!this.connected || this.paused) return;
        
        try {
            // Create fetch params including the last timestamp if we have one
            const params = {
                ...this.connectionConfig,
                last_timestamp: this.lastTimestamp
            };
            
            const response = await fetch('/ingest/database/fetch-logs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to fetch logs');
            }
            
            const result = await response.json();
            
            // Process the logs
            if (result.logs && result.logs.length > 0) {
                this.displayLogs(result.logs);
                this.logCount += result.logs.length;
                
                // Update the last timestamp for incremental fetching
                if (result.logs.length > 0) {
                    const lastLog = result.logs[result.logs.length - 1];
                    this.lastTimestamp = lastLog.timestamp;
                }
                
                // Update stats
                this.updateStreamStats();
            }
        } catch (error) {
            console.error('Error fetching logs:', error);
            
            // Only show an error message if we're still connected (to avoid duplicate errors)
            if (this.connected) {
                const logsContainer = document.getElementById('db-logs-container');
                logsContainer.innerHTML += `<div class="text-red-500 p-2 mb-2 border border-red-300 border-opacity-20 rounded"><p>Error fetching logs: ${error.message}</p></div>`;
            }
        }
    }

    // Display logs in the UI
    displayLogs(logs) {
        const logsContainer = document.getElementById('db-logs-container');
        
        // Clear the "connecting" message on first logs
        if (this.logCount === 0) {
            logsContainer.innerHTML = '';
        }
        
        logs.forEach(log => {
            const level = log.level || 'INFO';
            const levelClass = {
                'ERROR': 'text-red-500',
                'WARN': 'text-yellow-500',
                'INFO': 'text-blue-500',
                'DEBUG': 'text-gray-500'
            }[level] || 'text-gray-500';
            
            const logEntry = document.createElement('div');
            logEntry.className = 'mb-4 p-2 border-l-4 border-gray-700';
            
            // Determine if this is a markdown-formatted log or a simple log
            const isMarkdownLog = log.message && (
                log.message.includes('#') || 
                log.message.includes('```') || 
                log.message.includes('|') ||
                log.message.includes('- ') ||
                log.message.includes('> ')
            );
            
            // Create header with metadata
            const header = document.createElement('div');
            header.className = 'flex justify-between items-start mb-2';
            
            // Left side: level and service
            const leftSide = document.createElement('div');
            leftSide.className = 'flex items-center';
            leftSide.innerHTML = `
                <span class="${levelClass} font-medium mr-2">[${level}]</span>
                <span class="text-gray-300">${log.service || 'database'}</span>
            `;
            
            // Right side: timestamp
            const rightSide = document.createElement('div');
            rightSide.className = 'text-right';
            rightSide.innerHTML = `
                <div class="text-gray-400 text-xs">${new Date(log.timestamp).toLocaleString()}</div>
            `;
            
            header.appendChild(leftSide);
            header.appendChild(rightSide);
            logEntry.appendChild(header);
            
            // Content with special handling for markdown
            const content = document.createElement('div');
            if (isMarkdownLog) {
                content.className = 'text-white markdown-content bg-gray-800 p-3 rounded-md overflow-auto';
                content.innerHTML = renderMarkdown(log.message);
                
                // Add a special indicator for markdown logs
                const markdownBadge = document.createElement('div');
                markdownBadge.className = 'text-xs text-gray-400 mt-1 mb-2';
                markdownBadge.textContent = '✨ Markdown formatted log';
                logEntry.insertBefore(markdownBadge, content);
            } else {
                content.className = 'text-white';
                content.textContent = log.message;
            }
            
            logEntry.appendChild(content);
            
            // Add metadata section if present
            if (log.metadata && Object.keys(log.metadata).length > 0) {
                const metadataToggle = document.createElement('button');
                metadataToggle.className = 'text-xs text-gray-400 mt-2 hover:text-gray-300';
                metadataToggle.textContent = 'Show metadata';
                
                const metadataContent = document.createElement('pre');
                metadataContent.className = 'text-xs text-gray-400 mt-1 hidden';
                metadataContent.textContent = JSON.stringify(log.metadata, null, 2);
                
                metadataToggle.addEventListener('click', () => {
                    if (metadataContent.classList.contains('hidden')) {
                        metadataContent.classList.remove('hidden');
                        metadataToggle.textContent = 'Hide metadata';
                    } else {
                        metadataContent.classList.add('hidden');
                        metadataToggle.textContent = 'Show metadata';
                    }
                });
                
                logEntry.appendChild(metadataToggle);
                logEntry.appendChild(metadataContent);
            }
            
            logsContainer.appendChild(logEntry);
            
            // Scroll to the bottom if we're already at the bottom
            const isAtBottom = logsContainer.scrollHeight - logsContainer.clientHeight <= logsContainer.scrollTop + 50;
            if (isAtBottom) {
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
            
            // Limit the number of logs to keep memory usage reasonable
            while (logsContainer.children.length > 300) {
                logsContainer.removeChild(logsContainer.firstChild);
            }
        });
    }

    // Update the stream stats display
    updateStreamStats() {
        const statsDiv = document.getElementById('stream-stats');
        statsDiv.classList.remove('hidden');
        
        document.getElementById('current-db-connection').textContent = this.getConnectionDisplayName();
        document.getElementById('logs-count').textContent = this.logCount;
        document.getElementById('last-update-time').textContent = new Date().toLocaleTimeString();
    }

    // Get a display name for the current connection
    getConnectionDisplayName() {
        const config = this.connectionConfig;
        if (!config) return 'Unknown';
        
        if (config.uri) {
            // Remove password from displayed URI
            const uri = config.uri.replace(/:([^@]+)@/, ':****@');
            return uri;
        } else {
            return `${config.db_type}://${config.username}:****@${config.host}:${config.port}/${config.database}`;
        }
    }

    // Pause streaming
    pause() {
        this.paused = true;
        this.updateUIForPausedState();
    }

    // Resume streaming
    resume() {
        this.paused = false;
        this.updateUIForResumedState();
        
        // Immediately fetch logs
        this.fetchLogs();
    }

    // Disconnect from database
    disconnect() {
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
        
        this.connected = false;
        this.updateUIForDisconnectedState();
    }

    // Update UI elements for connected state
    updateUIForConnectedState() {
        // Show the control buttons
        document.getElementById('pause-stream-button').classList.remove('hidden');
        document.getElementById('disconnect-button').classList.remove('hidden');
        
        // Hide the form or disable inputs
        document.querySelectorAll('#db-connection-form input, #db-connection-form select, #db-connection-form textarea, #db-connection-form button[type="submit"]').forEach(el => {
            el.disabled = true;
        });
        
        // Show stats
        document.getElementById('stream-stats').classList.remove('hidden');
    }

    // Update UI elements for paused state
    updateUIForPausedState() {
        document.getElementById('pause-stream-button').classList.add('hidden');
        document.getElementById('resume-stream-button').classList.remove('hidden');
    }

    // Update UI elements for resumed state
    updateUIForResumedState() {
        document.getElementById('pause-stream-button').classList.remove('hidden');
        document.getElementById('resume-stream-button').classList.add('hidden');
    }

    // Update UI elements for disconnected state
    updateUIForDisconnectedState() {
        // Hide control buttons
        document.getElementById('pause-stream-button').classList.add('hidden');
        document.getElementById('resume-stream-button').classList.add('hidden');
        document.getElementById('disconnect-button').classList.add('hidden');
        
        // Reset form
        document.querySelectorAll('#db-connection-form input, #db-connection-form select, #db-connection-form textarea, #db-connection-form button[type="submit"]').forEach(el => {
            el.disabled = false;
        });
        
        // Reset logs display
        const logsContainer = document.getElementById('db-logs-container');
        logsContainer.innerHTML = '<p class="text-center text-gray-500">Connect to a database to view logs.</p>';
        
        // Hide stats
        document.getElementById('stream-stats').classList.add('hidden');
    }

    // Load saved connections from localStorage
    loadSavedConnections() {
        try {
            const saved = localStorage.getItem('dbConnections');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            console.error('Error loading saved connections:', e);
            return [];
        }
    }

    // Save a connection to localStorage
    saveConnection(config) {
        try {
            // Create a copy of the config without sensitive fields in plain text
            const safeConfig = { ...config };
            
            // Add a display name and ID
            safeConfig.id = Date.now().toString();
            safeConfig.displayName = this.getConnectionDisplayName();
            
            // Use a simple encryption for password
            if (safeConfig.password) {
                safeConfig.password = this.encryptValue(safeConfig.password);
            }
            
            // Add to saved connections
            this.savedConnections.push(safeConfig);
            
            // Store in localStorage
            localStorage.setItem('dbConnections', JSON.stringify(this.savedConnections));
            
            // Update the UI
            this.updateSavedConnectionsList();
            
            return true;
        } catch (e) {
            console.error('Error saving connection:', e);
            return false;
        }
    }

    // Delete a saved connection
    deleteConnection(id) {
        this.savedConnections = this.savedConnections.filter(conn => conn.id !== id);
        localStorage.setItem('dbConnections', JSON.stringify(this.savedConnections));
        this.updateSavedConnectionsList();
    }

    // Update the UI with saved connections
    updateSavedConnectionsList() {
        const container = document.getElementById('connections-list');
        
        if (!this.savedConnections || this.savedConnections.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-500 text-center">No saved connections found.</p>';
            return;
        }
        
        // Create the list
        let html = '<div class="space-y-2">';
        
        this.savedConnections.forEach(conn => {
            html += `
                <div class="flex items-center justify-between p-2 bg-white rounded shadow-sm">
                    <div class="overflow-hidden">
                        <p class="text-sm font-medium text-gray-800 truncate">${conn.displayName}</p>
                        <p class="text-xs text-gray-500">${conn.db_type} • Last used: ${conn.lastUsed || 'Never'}</p>
                    </div>
                    <div class="flex space-x-2">
                        <button data-connection-id="${conn.id}" class="connect-saved text-xs px-2 py-1 bg-indigo-500 text-white rounded hover:bg-indigo-600">
                            Connect
                        </button>
                        <button data-connection-id="${conn.id}" class="delete-saved text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200">
                            Delete
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
        
        // Add event listeners
        document.querySelectorAll('.connect-saved').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.connectionId;
                const connection = this.savedConnections.find(c => c.id === id);
                
                if (connection) {
                    // Decrypt password if it exists
                    if (connection.password) {
                        connection.password = this.decryptValue(connection.password);
                    }
                    
                    // Update the form with connection details
                    this.fillConnectionForm(connection);
                    
                    // Mark the last used date
                    connection.lastUsed = new Date().toISOString();
                    localStorage.setItem('dbConnections', JSON.stringify(this.savedConnections));
                    
                    // Connect automatically
                    document.getElementById('db-connection-form').dispatchEvent(new Event('submit'));
                }
            });
        });
        
        document.querySelectorAll('.delete-saved').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.connectionId;
                
                if (confirm('Are you sure you want to delete this saved connection?')) {
                    this.deleteConnection(id);
                }
            });
        });
    }

    // Fill the connection form with saved connection details
    fillConnectionForm(connection) {
        // Set the database type
        document.getElementById('db-type').value = connection.db_type;
        
        if (connection.uri) {
            // Use URI mode
            document.getElementById('uri-field').classList.remove('hidden');
            document.getElementById('detailed-connection-fields').classList.add('hidden');
            document.querySelector('input[name="uri"]').value = connection.uri;
        } else {
            // Use detailed mode
            document.getElementById('uri-field').classList.add('hidden');
            document.getElementById('detailed-connection-fields').classList.remove('hidden');
            
            // Fill in detailed fields
            document.querySelector('input[name="host"]').value = connection.host || '';
            document.querySelector('input[name="port"]').value = connection.port || '';
            document.querySelector('input[name="database"]').value = connection.database || '';
            document.querySelector('input[name="username"]').value = connection.username || '';
            document.querySelector('input[name="password"]').value = connection.password || '';
        }
        
        // Fill in query and other fields
        document.querySelector('textarea[name="log_query"]').value = connection.log_query || '';
        document.querySelector('input[name="refresh_interval"]').value = connection.refresh_interval || '10';
        
        // Field mappings
        document.querySelector('input[name="timestamp_field"]').value = connection.timestamp_field || '';
        document.querySelector('input[name="message_field"]').value = connection.message_field || '';
        document.querySelector('input[name="level_field"]').value = connection.level_field || '';
        document.querySelector('input[name="service_field"]').value = connection.service_field || '';
    }

    // Very simple "encryption" for storing passwords (not secure, just obscures them)
    encryptValue(value) {
        return btoa(value);
    }

    // Decrypt the encrypted values
    decryptValue(value) {
        return atob(value);
    }
}

// Create DB streamer instance
let dbStreamer = new DatabaseLogStreamer();

// Initialize database log streaming functionality
document.addEventListener('DOMContentLoaded', () => {
    // Initialize the connection form
    const connectionForm = document.getElementById('db-connection-form');
    const toggleConnectionDetails = document.getElementById('toggle-connection-details');
    const useDefaultLogQuery = document.getElementById('use-default-log-query');
    const pauseButton = document.getElementById('pause-stream-button');
    const resumeButton = document.getElementById('resume-stream-button');
    const disconnectButton = document.getElementById('disconnect-button');
    const listTablesButton = document.getElementById('list-tables-button');
    
    // Toggle between URI and detailed connection fields
    toggleConnectionDetails.addEventListener('click', () => {
        const uriField = document.getElementById('uri-field');
        const detailedFields = document.getElementById('detailed-connection-fields');
        
        if (uriField.classList.contains('hidden')) {
            // Switch to URI mode
            uriField.classList.remove('hidden');
            detailedFields.classList.add('hidden');
            toggleConnectionDetails.textContent = 'Use detailed connection fields instead';
        } else {
            // Switch to detailed mode
            uriField.classList.add('hidden');
            detailedFields.classList.remove('hidden');
            toggleConnectionDetails.textContent = 'Use connection URI instead';
        }
    });
    
    // Add event listener for the "Browse Tables" button
    listTablesButton.addEventListener('click', async () => {
        const formData = new FormData(connectionForm);
        const config = {
            db_type: formData.get('db_type')
        };
        
        // Check if we're using URI or detailed fields
        if (!document.getElementById('uri-field').classList.contains('hidden')) {
            config.uri = formData.get('uri');
            
            // Validate that URI is provided
            if (!config.uri) {
                showNotification('Please provide a database URI', 'error');
                return;
            }
        } else {
            config.host = formData.get('host');
            config.port = formData.get('port');
            config.database = formData.get('database');
            config.username = formData.get('username');
            config.password = formData.get('password');
            
            // Validate required fields
            if (!config.host || !config.database || !config.username) {
                showNotification('Please provide host, database, and username', 'error');
                return;
            }
        }
        
        // Show loading state
        const listTablesText = document.getElementById('list-tables-text');
        const listTablesSpinner = document.getElementById('list-tables-spinner');
        
        listTablesButton.disabled = true;
        listTablesSpinner.classList.remove('hidden');
        listTablesText.textContent = 'Loading...';
        
        try {
            // List available tables
            await dbStreamer.listTables(config);
            showNotification('Successfully retrieved database tables');
        } catch (error) {
            console.error('Error listing tables:', error);
            showNotification('Error listing tables: ' + error.message, 'error');
        } finally {
            // Reset button state
            listTablesButton.disabled = false;
            listTablesSpinner.classList.add('hidden');
            listTablesText.textContent = 'Browse Tables';
        }
    });
    
    // Set default log query based on database type
    useDefaultLogQuery.addEventListener('click', () => {
        const dbType = document.getElementById('db-type').value;
        const queryField = document.querySelector('textarea[name="log_query"]');
        
        const defaultQueries = {
            postgresql: 'SELECT created_at as timestamp, log_level as level, message, service_name as service, metadata FROM logs ORDER BY created_at DESC LIMIT 100',
            mysql: 'SELECT created_at as timestamp, log_level as level, message, service_name as service, metadata FROM logs ORDER BY created_at DESC LIMIT 100',
            supabase: 'logs',
            neon: 'SELECT created_at as timestamp, level, message, context as metadata FROM log_events ORDER BY created_at DESC LIMIT 100',
            sqlite: 'SELECT timestamp, level, message, source as service, extra as metadata FROM logs ORDER BY timestamp DESC LIMIT 100'
        };
        
        queryField.value = defaultQueries[dbType] || 'logs';
    });
    
    // Handle form submission
    connectionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Get form data
        const formData = new FormData(e.target);
        const config = {
            db_type: formData.get('db_type')
        };
        
        // Check if we're using URI or detailed fields
        if (!document.getElementById('uri-field').classList.contains('hidden')) {
            config.uri = formData.get('uri');
        } else {
            config.host = formData.get('host');
            config.port = formData.get('port');
            config.database = formData.get('database');
            config.username = formData.get('username');
            config.password = formData.get('password');
        }
        
        // Get other fields
        config.log_query = formData.get('log_query');
        config.refresh_interval = parseInt(formData.get('refresh_interval')) || 10;
        config.save_connection = formData.get('save_connection') === 'on';
        
        // Field mappings
        config.field_mappings = {
            timestamp: formData.get('timestamp_field') || 'timestamp',
            message: formData.get('message_field') || 'message',
            level: formData.get('level_field') || 'level',
            service: formData.get('service_field') || 'service'
        };
        
        // Show connecting state
        const connectButton = document.getElementById('connect-button');
        const connectSpinner = document.getElementById('connect-spinner');
        const connectText = document.getElementById('connect-text');
        
        connectButton.disabled = true;
        connectSpinner.classList.remove('hidden');
        connectText.textContent = 'Connecting...';
        
        try {
            // Connect to the database
            const success = await dbStreamer.connect(config);
            
            if (!success) {
                throw new Error('Failed to connect to database');
            }
            
            // Update the saved connections list
            dbStreamer.updateSavedConnectionsList();
            
            // Show notification
            showNotification('Successfully connected to database');
        } catch (error) {
            console.error('Connection error:', error);
            showNotification('Error connecting to database: ' + error.message, 'error');
            
            // Reset the form state
            connectButton.disabled = false;
            connectSpinner.classList.add('hidden');
            connectText.textContent = 'Connect and Stream Logs';
        }
    });
    
    // Pause button handler
    pauseButton.addEventListener('click', () => {
        dbStreamer.pause();
        showNotification('Stream paused');
    });
    
    // Resume button handler
    resumeButton.addEventListener('click', () => {
        dbStreamer.resume();
        showNotification('Stream resumed');
    });
    
    // Disconnect button handler
    disconnectButton.addEventListener('click', () => {
        dbStreamer.disconnect();
        showNotification('Disconnected from database');
    });
    
    // Initialize saved connections list
    dbStreamer.updateSavedConnectionsList();
});