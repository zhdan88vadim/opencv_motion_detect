// SSE Client Module
class SSEClient {
    constructor(url = '/events') {
        this.url = url;
        this.eventSource = null;
        this.listeners = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isConnected = false;
        this.shouldReconnect = true;
    }

    connect() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        try {
            this.eventSource = new EventSource(this.url);
            
            this.eventSource.onopen = () => {
                console.log('📡 SSE connection established');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected', { status: 'connected' });
            };

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.emit('message', data);
                } catch (err) {
                    console.error('Error parsing SSE data:', err);
                }
            };

            this.eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
                this.isConnected = false;
                this.emit('disconnected', { status: 'disconnected' });
                
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }

                if (this.shouldReconnect) {
                    this.reconnect();
                }
            };

        } catch (err) {
            console.error('SSE initialization error:', err);
            if (this.shouldReconnect) {
                this.reconnect();
            }
        }
    }

    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts), 30000);
            console.log(`🔄 Reconnecting in ${delay}ms... (Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                if (this.shouldReconnect) {
                    this.connect();
                }
            }, delay);
        } else {
            console.error('❌ Max reconnection attempts reached');
            this.emit('error', { message: 'Max reconnection attempts reached' });
        }
    }

    disconnect() {
        this.shouldReconnect = false;
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.isConnected = false;
    }

    on(event, callback) {
        this.listeners.push({ event, callback });
    }

    off(event, callback) {
        this.listeners = this.listeners.filter(
            listener => !(listener.event === event && listener.callback === callback)
        );
    }

    emit(event, data) {
        this.listeners.forEach(listener => {
            if (listener.event === event) {
                try {
                    listener.callback(data);
                } catch (err) {
                    console.error('Error in SSE listener:', err);
                }
            }
        });
    }
}

// Export for use
window.SSEClient = SSEClient;