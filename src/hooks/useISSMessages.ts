import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = 'http://localhost:8000';

export interface ISSFragment {
  fragment_number: number;
  fragment_id: string;
  status: "DELIVERED" | "PENDING";
  delivered_at: string | null;
}

export interface ISSFragmentStatus {
  bundle_id: string;
  fragments: ISSFragment[];
  fragments_received: number;
  fragments_total: number;
  is_complete: boolean;
}

export interface ISSMessage {
  bundle_id: string;
  bundle_id_short: string;
  source_station: string;
  parent_bundle_id?: string;
  fragments_received: number;
  fragments_total: number;
  is_complete: boolean;
  delivered_at: string | null;
  priority: "EXPEDITED" | "NORMAL" | "BULK";
  decrypted_payload?: string;
  reassembled_at?: string;
}

export interface ReassembledMessage {
  bundle_id: string;
  decrypted_payload: string;
  source_station: string;
  reassembled_at: string;
  fragments_count: number;
}

export const useISSMessages = () => {
  const [messages, setMessages] = useState<ISSMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/iss/messages`);
      if (!response.ok) throw new Error('Failed to fetch messages');
      const data = await response.json();
      setMessages(data.messages || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error fetching ISS messages:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const getFragmentStatus = useCallback(async (bundleId: string): Promise<ISSFragmentStatus | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/iss/fragments/${bundleId}`);
      if (!response.ok) throw new Error('Failed to fetch fragment status');
      const data = await response.json();
      return data.error ? null : data;
    } catch (err) {
      console.error('Error fetching fragment status:', err);
      return null;
    }
  }, []);

  const reassembleMessage = useCallback(async (bundleId: string): Promise<ReassembledMessage | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/iss/messages/${bundleId}/reassemble`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to reassemble message');
      const data = await response.json();
      if (data.success && data.message) {
        // Update local state
        setMessages(prev => prev.map(msg => 
          msg.bundle_id === bundleId || msg.parent_bundle_id === bundleId
            ? { ...msg, ...data.message, is_complete: true }
            : msg
        ));
        return data.message;
      }
      return null;
    } catch (err) {
      console.error('Error reassembling message:', err);
      return null;
    }
  }, []);

  const sendReply = useCallback(async (
    destinationStation: string,
    payload: string,
    priority: "EXPEDITED" | "NORMAL" | "BULK" = "NORMAL"
  ): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/iss/messages/reply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          destination_station: destinationStation,
          payload,
          priority,
        }),
      });
      if (!response.ok) throw new Error('Failed to send reply');
      const data = await response.json();
      return data.success === true;
    } catch (err) {
      console.error('Error sending reply:', err);
      return false;
    }
  }, []);

  useEffect(() => {
    fetchMessages();
    // Poll for updates every 2 seconds
    const interval = setInterval(fetchMessages, 2000);
    return () => clearInterval(interval);
  }, [fetchMessages]);

  return {
    messages,
    loading,
    error,
    fetchMessages,
    getFragmentStatus,
    reassembleMessage,
    sendReply,
  };
};

