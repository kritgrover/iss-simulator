import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useISSMessages, ISSMessage } from "@/hooks/useISSMessages";
import { Mail, Clock, CheckCircle, Package, Zap } from "lucide-react";
import { useState } from "react";

interface MessageInboxProps {
  onMessageSelect?: (message: ISSMessage) => void;
  selectedMessage?: ISSMessage | null;
}

const MessageInbox = ({ onMessageSelect, selectedMessage: externalSelectedMessage }: MessageInboxProps) => {
  const { messages, loading } = useISSMessages();
  const [internalSelectedMessage, setInternalSelectedMessage] = useState<ISSMessage | null>(null);
  
  const selectedMessage = externalSelectedMessage !== undefined ? externalSelectedMessage : internalSelectedMessage;
  const setSelectedMessage = (msg: ISSMessage | null) => {
    if (onMessageSelect && msg) {
      onMessageSelect(msg);
    } else {
      setInternalSelectedMessage(msg);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "EXPEDITED":
        return "bg-red-500/20 text-red-400 border-red-500/50";
      case "NORMAL":
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/50";
      case "BULK":
        return "bg-gray-500/20 text-gray-400 border-gray-500/50";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/50";
    }
  };

  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return "N/A";
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="w-4 h-4" />
            Message Inbox
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-secondary">Loading messages...</div>
        </CardContent>
      </Card>
    );
  }

  // Group messages by parent_bundle_id to avoid duplicates
  const uniqueMessages = new Map<string, ISSMessage>();
  messages.forEach(msg => {
    const key = msg.parent_bundle_id || msg.bundle_id;
    if (!uniqueMessages.has(key) || (msg.is_complete && !uniqueMessages.get(key)?.is_complete)) {
      uniqueMessages.set(key, msg);
    }
  });

  const messageList = Array.from(uniqueMessages.values());

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="w-4 h-4" />
          Message Inbox
        </CardTitle>
        <CardDescription>
          {messageList.length} message{messageList.length !== 1 ? 's' : ''} received
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {messageList.length === 0 ? (
            <div className="text-sm text-secondary text-center py-8">
              No messages received yet
            </div>
          ) : (
            messageList.map((message) => (
              <div
                key={message.bundle_id}
                onClick={() => setSelectedMessage(message)}
                className={`p-3 rounded-lg border cursor-pointer transition-all hover:bg-background/50 ${
                  selectedMessage?.bundle_id === message.bundle_id
                    ? "bg-primary/10 border-primary/50"
                    : "bg-background/30 border-border"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold">
                        {message.source_station.toUpperCase()}
                      </span>
                      <Badge className={getPriorityColor(message.priority)}>
                        {message.priority}
                      </Badge>
                      {message.is_complete ? (
                        <CheckCircle className="w-4 h-4 text-success" />
                      ) : (
                        <Clock className="w-4 h-4 text-amber-500" />
                      )}
                    </div>
                    <div className="text-xs text-secondary font-mono mb-1">
                      Bundle: {message.bundle_id_short}
                    </div>
                    {message.fragments_total > 1 && (
                      <div className="flex items-center gap-2 text-xs text-secondary">
                        <Package className="w-3 h-3" />
                        <span>
                          {message.fragments_received}/{message.fragments_total} fragments
                        </span>
                        {!message.is_complete && (
                          <span className="text-amber-500">(Incomplete)</span>
                        )}
                      </div>
                    )}
                    {message.decrypted_payload && (
                      <div className="mt-2 text-sm text-terminal-text font-mono bg-background/50 p-2 rounded border border-border">
                        {message.decrypted_payload.substring(0, 100)}
                        {message.decrypted_payload.length > 100 ? "..." : ""}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-secondary flex-shrink-0">
                    {formatTime(message.delivered_at)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default MessageInbox;

