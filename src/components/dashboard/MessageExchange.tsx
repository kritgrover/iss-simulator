import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, CheckCircle, XCircle, Clock, Package, Zap } from "lucide-react";
import { useState, useEffect } from "react";
import ProtocolStack from "./ProtocolStack";

interface DTNBundle {
  bundle_id: string;
  bundle_id_short: string;
  source_station: string;
  destination_station: string;
  payload: string;
  priority: "EXPEDITED" | "NORMAL" | "BULK";
  status: "QUEUED" | "TRANSMITTING" | "DELIVERED" | "FORWARDED" | "EXPIRED";
  created_at: string;
  ttl_hours: number;
  age_seconds: number;
}

interface CustodyAck {
  type: "custody_ack";
  bundle_id: string;
  bundle_id_short: string;
  from_station: string;
  to_station: string;
  ack_type: "custody_accepted" | "delivered";
  timestamp: string;
}

interface MessageExchangeProps {
  activeStationId: string;
  stationColor: string;
  handoffCount: number;
  linkStatus?: {
    connection_state: "ACQUIRED" | "DEGRADED" | "IDLE";
  } | null;
  dtnQueues?: Record<string, DTNBundle[]>;
  custodyAcks?: CustodyAck[];
}

type MessageMode = "TCP" | "DTN";

interface Message {
  text: string;
  success: boolean;
  time: string;
  station: string;
  mode: MessageMode;
  bundleId?: string;
  priority?: string;
  status?: string;
  isAck?: boolean;  // NEW
  ackType?: "custody_accepted" | "delivered";  // NEW
}

const API_BASE_URL = 'http://localhost:8000';

const MessageExchange = ({ 
  activeStationId, 
  stationColor, 
  handoffCount,
  linkStatus,
  dtnQueues,
  custodyAcks = []
}: MessageExchangeProps) => {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { text: "ISS> Telemetry packet received", success: true, time: "14:30:12", station: "Toronto", mode: "TCP" },
    { text: "GND> Command acknowledged", success: true, time: "14:30:15", station: "Toronto", mode: "TCP" },
    { text: "ISS> System status nominal", success: true, time: "14:31:02", station: "Toronto", mode: "TCP" },
  ]);
  const [protocolDirection, setProtocolDirection] = useState<'uplink' | 'downlink' | null>(null);
  const [mode, setMode] = useState<MessageMode>("TCP");
  const [bundlePriority, setBundlePriority] = useState<"EXPEDITED" | "NORMAL" | "BULK">("NORMAL");

  const isConnected = linkStatus?.connection_state === "ACQUIRED" || linkStatus?.connection_state === "DEGRADED";
  const isTorontoActive = activeStationId === "toronto" && isConnected;
  
  // Get current station's bundle queue
  const stationQueue = dtnQueues?.[activeStationId] || [];
  const queuedBundles = stationQueue.filter(b => b.status === "QUEUED").slice(0, 5);

  // Add handoff message when handoff occurs
  useEffect(() => {
    if (handoffCount > 0) {
      setMessages(prev => [...prev, {
        text: `○ Handoff completed to ${activeStationId.toUpperCase()}`,
        success: true,
        time: new Date().toLocaleTimeString('en-US', { hour12: false }),
        station: activeStationId,
        mode: "TCP"
      }]);
    }
  }, [handoffCount, activeStationId]);

  // Simulate DTN bundle delivery
  useEffect(() => {
    if (mode === "DTN" && stationQueue.length > 0) {
      const interval = setInterval(() => {
        const deliveredBundles = stationQueue.filter(b => 
          b.status === "DELIVERED" && 
          !messages.some(m => m.bundleId === b.bundle_id)
        );

        deliveredBundles.forEach(bundle => {
          setMessages(prev => [...prev, {
            text: `[${bundle.source_station.toUpperCase()}] Bundle delivered: ${bundle.payload}`,
            success: true,
            time: new Date().toLocaleTimeString('en-US', { hour12: false }),
            station: bundle.source_station,
            mode: "DTN",
            bundleId: bundle.bundle_id_short,
            priority: bundle.priority,
            status: "DELIVERED"
          }]);
        });
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [mode, stationQueue, messages]);

  // NEW: Process custody ACKs
  useEffect(() => {
    if (custodyAcks && custodyAcks.length > 0) {
      custodyAcks.forEach(ack => {
        // Only show ACK if it's relevant to currently displayed stations
        const ackText = ack.ack_type === "delivered"
          ? `◀ ACK: Bundle ${ack.bundle_id_short} delivered to ${ack.from_station.toUpperCase()}`
          : `◀ ACK: ${ack.from_station.toUpperCase()} accepted custody of ${ack.bundle_id_short}`;
        
        setMessages(prev => {
          // Avoid duplicate ACKs
          if (prev.some(m => m.isAck && m.bundleId === ack.bundle_id_short && m.time === new Date(ack.timestamp).toLocaleTimeString('en-US', { hour12: false }))) {
            return prev;
          }
          
          return [...prev, {
            text: ackText,
            success: true,
            time: new Date(ack.timestamp).toLocaleTimeString('en-US', { hour12: false }),
            station: ack.to_station,
            mode: "DTN",
            bundleId: ack.bundle_id_short,
            isAck: true,
            ackType: ack.ack_type
          }];
        });
      });
    }
  }, [custodyAcks]);

  const handleSend = async () => {
    if (!message.trim()) return;

    const stationName = activeStationId.charAt(0).toUpperCase() + activeStationId.slice(1);
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });

    if (mode === "TCP") {
      // TCP Mode - requires Toronto to be active
      if (!isTorontoActive) {
        setMessages(prev => [...prev, {
          text: `[${stationName}] GND> ${message}`,
          success: false,
          time: timestamp,
          station: activeStationId,
          mode: "TCP"
        }]);
        setMessage("");
        return;
      }

      setProtocolDirection('uplink');
      
      setMessages(prev => [...prev, {
        text: `[${stationName}] GND> ${message}`,
        success: true,
        time: timestamp,
        station: activeStationId,
        mode: "TCP"
      }]);
      setMessage("");

      setTimeout(() => {
        setProtocolDirection('downlink');
        setMessages(prev => [...prev, {
          text: `[${stationName}] ISS> ACK: ${message.substring(0, 20)}...`,
          success: true,
          time: new Date().toLocaleTimeString('en-US', { hour12: false }),
          station: activeStationId,
          mode: "TCP"
        }]);
      }, 1200);

      setTimeout(() => {
        setProtocolDirection(null);
      }, 2500);

    } else {
      // DTN Mode - create bundle via API
      try {
        const response = await fetch(`${API_BASE_URL}/api/bundle/create`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            source_station: activeStationId,
            destination: "ISS",
            payload: message,
            priority: bundlePriority,
            ttl_hours: 24
          })
        });

        const result = await response.json();

        if (result.success) {
          const bundle = result.bundle;
          setMessages(prev => [...prev, {
            text: `[${stationName}] Bundle created: ${message}`,
            success: true,
            time: timestamp,
            station: activeStationId,
            mode: "DTN",
            bundleId: bundle.bundle_id_short,
            priority: bundle.priority,
            status: isConnected ? "TRANSMITTING" : "QUEUED"
          }]);
        } else {
          setMessages(prev => [...prev, {
            text: `[${stationName}] Failed to create bundle: ${result.error}`,
            success: false,
            time: timestamp,
            station: activeStationId,
            mode: "DTN"
          }]);
        }
      } catch (error) {
        console.error('Error creating bundle:', error);
        setMessages(prev => [...prev, {
          text: `[${stationName}] Error creating bundle`,
          success: false,
          time: timestamp,
          station: activeStationId,
          mode: "DTN"
        }]);
      }
      
      setMessage("");
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "EXPEDITED": return "text-red-500";
      case "NORMAL": return "text-cyan-500";
      case "BULK": return "text-gray-500";
      default: return "text-cyan-500";
    }
  };

  const getPriorityBg = (priority: string) => {
    switch (priority) {
      case "EXPEDITED": return "bg-red-500/20 border-red-500/50";
      case "NORMAL": return "bg-cyan-500/20 border-cyan-500/50";
      case "BULK": return "bg-gray-500/20 border-gray-500/50";
      default: return "bg-cyan-500/20 border-cyan-500/50";
    }
  };

  const getStatusIcon = (msg: Message) => {
    if (msg.isAck) {
      return <CheckCircle className="w-3 h-3 text-cyan-400" />;  // Cyan for ACKs
    }

    if (msg.mode === "DTN") {
      if (msg.status === "DELIVERED") return <CheckCircle className="w-3 h-3 text-success" />;
      if (msg.status === "TRANSMITTING") return <Zap className="w-3 h-3 text-amber-500 animate-pulse" />;
      if (msg.status === "QUEUED") return <Clock className="w-3 h-3 text-secondary" />;
    }
    return msg.success ? 
      <CheckCircle className="w-3 h-3 text-terminal-text" /> : 
      <XCircle className="w-3 h-3 text-destructive" />;
  };

  return (
    <Card className="p-4 flex h-[640px]">
      {/* Protocol Stack - Left side */}
      <div className="w-32 flex-shrink-0 border-r border-border pr-3 mr-3">
        <div className="text-[9px] font-semibold tracking-wider uppercase text-secondary mb-2">
          PROTOCOL
        </div>
        <ProtocolStack direction={protocolDirection} mode={mode} />
      </div>

      {/* Message Terminal - Right side */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mode Toggle */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex gap-1 bg-background/50 rounded p-1">
            <button
              onClick={() => setMode("TCP")}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                mode === "TCP"
                  ? "bg-primary text-primary-foreground"
                  : "text-secondary hover:text-foreground"
              }`}
            >
              TCP MODE
            </button>
            <button
              onClick={() => setMode("DTN")}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                mode === "DTN"
                  ? "bg-primary text-primary-foreground"
                  : "text-secondary hover:text-foreground"
              }`}
            >
              DTN MODE
            </button>
          </div>
          
          <div className="flex items-center gap-2">
            {mode === "TCP" && (
              <div className={`flex items-center gap-1 text-xs font-mono ${
                isTorontoActive ? "text-success" : "text-destructive"
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isTorontoActive ? "bg-success animate-pulse" : "bg-destructive"
                }`} />
                {isTorontoActive ? "ONLINE" : "OFFLINE"}
              </div>
            )}
            {mode === "DTN" && (
              <div className="flex items-center gap-1 text-xs font-mono text-cyan-500">
                <Package className="w-3 h-3" />
                Queue: {queuedBundles.length}
              </div>
            )}
          </div>
        </div>

        {/* Message Log - DOUBLED IN SIZE */}
        <div className="flex-1 terminal p-3 overflow-y-auto space-y-2 mb-3">
          {messages.map((msg, idx) => (
            <div 
              key={idx} 
              className="flex items-start gap-2 text-sm font-mono"
            >
              {getStatusIcon(msg)}
              <div className="flex-1 min-w-0">
                <span className={`${
                  msg.isAck ? 'text-cyan-400' :
                  msg.success ? 'text-terminal-text' : 'text-destructive'
                }`}>
                  {msg.text}
                </span>
                {/* Only show bundle details for non-ACK messages */}
                {msg.bundleId && !msg.isAck && (
                  <div className="text-xs text-secondary mt-1">
                    [Bundle: {msg.bundleId}] [Priority: {msg.priority}] [TTL: 24h]
                    {msg.status && ` [${msg.status}]`}
                  </div>
                )}
              </div>
              <span className="text-terminal-text/60 text-xs flex-shrink-0">{msg.time}</span>
            </div>
          ))}
        </div>

        {/* DTN Bundle Queue */}
        {mode === "DTN" && queuedBundles.length > 0 && (
          <div className="mb-3 p-2 bg-background/50 rounded border border-border">
            <div className="text-[9px] font-semibold tracking-wider uppercase text-secondary mb-2">
              BUNDLE QUEUE ({queuedBundles.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {queuedBundles.map((bundle) => (
                <div
                  key={bundle.bundle_id}
                  className={`px-2 py-1 rounded-full text-[10px] font-mono border ${getPriorityBg(bundle.priority)}`}
                  title={bundle.payload}
                >
                  <span className={getPriorityColor(bundle.priority)}>
                    {bundle.bundle_id_short}
                  </span>
                  <span className="text-secondary ml-1">
                    ({Math.floor(bundle.age_seconds)}s)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Priority Selection for DTN */}
        {mode === "DTN" && (
          <div className="flex gap-1 mb-2">
            <button
              onClick={() => setBundlePriority("EXPEDITED")}
              className={`flex-1 px-2 py-1.5 text-xs font-mono rounded transition-colors ${
                bundlePriority === "EXPEDITED"
                  ? "bg-red-500/30 border border-red-500 text-red-500"
                  : "bg-background/50 border border-border text-secondary hover:text-foreground"
              }`}
            >
              EXPEDITED
            </button>
            <button
              onClick={() => setBundlePriority("NORMAL")}
              className={`flex-1 px-2 py-1.5 text-xs font-mono rounded transition-colors ${
                bundlePriority === "NORMAL"
                  ? "bg-cyan-500/30 border border-cyan-500 text-cyan-500"
                  : "bg-background/50 border border-border text-secondary hover:text-foreground"
              }`}
            >
              NORMAL
            </button>
            <button
              onClick={() => setBundlePriority("BULK")}
              className={`flex-1 px-2 py-1.5 text-xs font-mono rounded transition-colors ${
                bundlePriority === "BULK"
                  ? "bg-gray-500/30 border border-gray-500 text-gray-500"
                  : "bg-background/50 border border-border text-secondary hover:text-foreground"
              }`}
            >
              BULK
            </button>
          </div>
        )}

        {/* Input Area */}
        <div className="flex gap-2 mb-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder={mode === "TCP" ? "Enter uplink message..." : "Enter bundle payload..."}
            className="flex-1 h-9 text-sm font-mono bg-terminal-bg text-terminal-text border-muted"
            disabled={mode === "TCP" && !isTorontoActive}
          />
          <Button 
            onClick={handleSend}
            variant="outline" 
            size="sm" 
            className="h-9 px-4 text-sm"
            disabled={mode === "TCP" && !isTorontoActive}
          >
            <Send className="h-4 w-4 mr-1" />
            {mode === "TCP" ? "SEND" : "QUEUE"}
          </Button>
        </div>

        {/* Status Messages */}
        {mode === "TCP" && !isTorontoActive && (
          <div className="text-xs text-destructive font-mono">
            ⚠ TCP connection only established if current station is Toronto
          </div>
        )}
        {mode === "DTN" && (
          <div className="text-xs text-cyan-500 font-mono">
            ✓ Bundle will be queued and forwarded when contact available
          </div>
        )}
      </div>
    </Card>
  );
};

export default MessageExchange;