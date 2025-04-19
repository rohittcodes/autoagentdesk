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

    // Handle WebSocket connection for live tab
    if (tabName === 'live' && document.visibilityState === 'visible') {
        if (!logWebSocket) {
            logWebSocket = new LogWebSocket();
        }
        logWebSocket.connect();
    } else if (logWebSocket) {
        logWebSocket.disconnect();
        logWebSocket = null;
    }
}

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.classList.remove('hidden', 'bg-green-500', 'bg-red-500');
    notification.classList.add(type === 'success' ? 'bg-green-500' : 'bg-red-500');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    
    try {
        const response = await fetch('/ingest/file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(result.message);
        } else {
            showNotification(result.detail || 'Error uploading file', 'error');
        }
    } catch (error) {
        showNotification('Error uploading file: ' + error.message, 'error');
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

document.getElementById('query-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const query = e.target.query.value;
    const resultsDiv = document.getElementById('query-results');
    resultsDiv.innerHTML = '<div class="text-center"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/queries/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                max_logs: 100
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            let html = `
                <div class="mb-4 p-4 bg-gray-50 rounded-md">
                    <h3 class="font-medium text-gray-900">Analysis</h3>
                    <div class="mt-2 text-gray-600 markdown-content">${renderMarkdown(result.analysis)}</div>
                </div>
                <div>
                    <h3 class="font-medium text-gray-900 mb-2">Logs</h3>
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
                            <span class="text-gray-500 text-sm">${new Date(log.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="mt-1 text-gray-900 markdown-content">${renderMarkdown(log.message)}</div>
                    </div>
                `;
            });
            
            html += '</div></div>';
            resultsDiv.innerHTML = html;
        } else {
            resultsDiv.innerHTML = `<div class="text-red-600">${result.detail || 'Error querying logs'}</div>`;
        }
    } catch (error) {
        resultsDiv.innerHTML = `<div class="text-red-600">Error querying logs: ${error.message}</div>`;
    }
});

class LogWebSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }

    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            this.socket = new WebSocket('ws://localhost:8000/logs/ws');
            this.socket.onopen = this._onOpen.bind(this);
            this.socket.onclose = this._onClose.bind(this);
            this.socket.onerror = this._onError.bind(this);
            this.socket.onmessage = this._onMessage.bind(this);
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this._scheduleReconnect();
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.reconnectAttempts = 0;
    }

    _onOpen() {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
    }

    _onClose() {
        console.log('WebSocket closed');
        this._scheduleReconnect();
    }

    _onError(error) {
        console.error('WebSocket error:', error);
        this._scheduleReconnect();
    }

    _onMessage(event) {
        try {
            const log = JSON.parse(event.data);
            const logsDiv = document.getElementById('live-logs');
            
            const level = log.level || 'INFO';
            const levelClass = {
                'ERROR': 'text-red-500',
                'WARN': 'text-yellow-500',
                'INFO': 'text-blue-500',
                'DEBUG': 'text-gray-500'
            }[level] || 'text-gray-500';
            
            const logEntry = document.createElement('div');
            logEntry.className = 'mb-2';
            logEntry.innerHTML = `
                <span class="text-gray-400">${new Date(log.timestamp).toLocaleString()}</span>
                <span class="${levelClass}">[${level}]</span>
                <div class="text-white markdown-content">${renderMarkdown(log.message)}</div>
            `;
            
            logsDiv.appendChild(logEntry);
            
            const isAtBottom = logsDiv.scrollHeight - logsDiv.clientHeight <= logsDiv.scrollTop + 50;
            if (isAtBottom) {
                logsDiv.scrollTop = logsDiv.scrollHeight;
            }
            
            while (logsDiv.children.length > 1000) {
                logsDiv.removeChild(logsDiv.firstChild);
            }
        } catch (error) {
            console.error('Error processing log message:', error);
        }
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
            logsDiv.innerHTML += '<div class="text-red-500">Error: Connection lost. Please refresh the page to try again.</div>';
        }
    }
}

let logWebSocket = null;

document.addEventListener('visibilitychange', () => {
    const liveTab = document.getElementById('live-tab');
    if (document.visibilityState === 'visible' && !liveTab.classList.contains('hidden')) {
        if (!logWebSocket) {
            logWebSocket = new LogWebSocket();
        }
        logWebSocket.connect();
    } else if (logWebSocket) {
        logWebSocket.disconnect();
        logWebSocket = null;
    }
});