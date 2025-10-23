import { useEffect, useState, useRef, useCallback } from 'react';

interface UseWebSocketReturn {
  isConnected: boolean;
  connectionError: string | null;
  lastMessage: any;
  sendMessage: (message: any) => void;
}

export const useWebSocket = (url: string): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('✅ WebSocket connected:', url);
          setIsConnected(true);
          setConnectionError(null);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setLastMessage(data);
            
            // Log different message types
            if (data.type === 'orbital_update') {
              // Don't log every update (too verbose)
            } else {
              console.log('📨 Received:', data.type);
            }
          } catch (e) {
            console.error('Failed to parse message:', e);
          }
        };

        ws.onerror = (error) => {
          console.error('❌ WebSocket error:', error);
          setConnectionError('Connection error');
        };

        ws.onclose = () => {
          console.log('🔌 WebSocket disconnected');
          setIsConnected(false);
          
          // Attempt to reconnect after 3 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('🔄 Attempting to reconnect...');
            connect();
          }, 3000);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        setConnectionError('Failed to establish connection');
        setIsConnected(false);
      }
    };

    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url]);

  return { isConnected, connectionError, lastMessage, sendMessage };
};