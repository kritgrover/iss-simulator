import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, CheckCircle, XCircle, Clock, Package, Zap } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import ProtocolStack from "./ProtocolStack";
import { DTNBundle } from "@/types/dtnBundle";
import { InfoTooltip } from "@/components/ui/info-tooltip";

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
  stationDecryptedMessages?: Record<string, Array<{
    bundle_id: string;
    decrypted_payload: string;
    source_station: string;
    destination_station: string;
    reassembled_at: string;
    fragments_count: number;
    is_broadcast?: boolean;
  }>>;
}

type MessageMode = "TCP" | "DTN";

interface Message {
  id: number;
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
  custodyAcks = [],
  stationDecryptedMessages = {}
}: MessageExchangeProps) => {
  const [message, setMessage] = useState("");
  // Initialize with empty array - will be populated on mount with current time
  const [messages, setMessages] = useState<Message[]>([]);
  const [typingProgress, setTypingProgress] = useState<Record<number, number>>({});
  const [isInitialized, setIsInitialized] = useState(false);
  const messageIdCounter = useRef(0);
  const messagesRef = useRef<Message[]>([]);
  const initializedMessageIds = useRef<Set<number>>(new Set());
  const displayedBundleIds = useRef<Set<string>>(new Set()); // Track displayed ISS messages
  const [protocolDirection, setProtocolDirection] = useState<'uplink' | 'downlink' | null>(null);
  const [mode, setMode] = useState<MessageMode>("TCP");
  const [bundlePriority, setBundlePriority] = useState<"EXPEDITED" | "NORMAL" | "BULK">("NORMAL");

  const isConnected = linkStatus?.connection_state === "ACQUIRED" || linkStatus?.connection_state === "DEGRADED";
  const isTorontoActive = activeStationId === "toronto" && isConnected;
  
  // Get current station's bundle queue
  const stationQueue = dtnQueues?.[activeStationId] || [];
  const queuedBundles = stationQueue.filter(b => b.status === "QUEUED").slice(0, 5);

  // Initialize first 3 messages on mount with current time
  useEffect(() => {
    if (!isInitialized) {
      const currentTime = new Date().toLocaleTimeString('en-US', { hour12: false });
      const initialMessages: Message[] = [
        { 
          id: messageIdCounter.current++, 
          text: "ISS> Telemetry packet received", 
          success: true, 
          time: currentTime, 
          station: "Toronto", 
          mode: "TCP" 
        },
        { 
          id: messageIdCounter.current++, 
          text: "GND> Command acknowledged", 
          success: true, 
          time: currentTime, 
          station: "Toronto", 
          mode: "TCP" 
        },
        { 
          id: messageIdCounter.current++, 
          text: "ISS> System status nominal", 
          success: true, 
          time: currentTime, 
          station: "Toronto", 
          mode: "TCP" 
        },
      ];
      setMessages(initialMessages);
      messagesRef.current = initialMessages;
      setIsInitialized(true);
      
      // Mark initial messages as initialized and stagger the typing start
      initialMessages.forEach((msg, idx) => {
        initializedMessageIds.current.add(msg.id);
        setTimeout(() => {
          setTypingProgress(prev => ({
            ...prev,
            [msg.id]: 0
          }));
        }, idx * 200 * (idx + 1)); // Stagger: 0ms, 400ms, 1200ms
      });
    }
  }, [isInitialized]);

  // Handle typing animations for all messages
  useEffect(() => {
    const typingSpeed = 30; // milliseconds per character
    let interval: NodeJS.Timeout | null = null;

    // Initialize typing for new messages
    messages.forEach(msg => {
      if (!initializedMessageIds.current.has(msg.id)) {
        initializedMessageIds.current.add(msg.id);
        setTypingProgress(prev => ({
          ...prev,
          [msg.id]: 0
        }));
      }
    });

    // Check if any message needs typing
    const needsTyping = messages.some(msg => {
      const currentProgress = typingProgress[msg.id] ?? 0;
      return currentProgress < msg.text.length;
    });

    if (needsTyping) {
      interval = setInterval(() => {
        setTypingProgress(prev => {
          const updated = { ...prev };
          let hasUpdates = false;

          messages.forEach(msg => {
            const current = updated[msg.id] ?? 0;
            if (current < msg.text.length) {
              updated[msg.id] = current + 1;
              hasUpdates = true;
            }
          });

          return hasUpdates ? updated : prev;
        });
      }, typingSpeed);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [messages, typingProgress]);

  // Add handoff message when handoff occurs
  useEffect(() => {
    if (handoffCount > 0) {
      const newMessage: Message = {
        id: messageIdCounter.current++,
        text: `○ Handoff completed to ${activeStationId.toUpperCase()}`,
        success: true,
        time: new Date().toLocaleTimeString('en-US', { hour12: false }),
        station: activeStationId,
        mode: "TCP"
      };
      setMessages(prev => {
        const updated = [...prev, newMessage];
        messagesRef.current = updated;
        return updated;
      });
    }
  }, [handoffCount, activeStationId]);

  // Simulate DTN bundle delivery
  useEffect(() => {
    if (mode === "DTN" && stationQueue.length > 0) {
      const interval = setInterval(() => {
        const deliveredBundles = stationQueue.filter(b => 
          b.status === "DELIVERED" && 
          !messagesRef.current.some(m => m.bundleId === b.bundle_id)
        );

        deliveredBundles.forEach(bundle => {
          const newMessage: Message = {
            id: messageIdCounter.current++,
            text: `[${bundle.source_station.toUpperCase()}] Bundle delivered: 🔐 ${bundle.payload_hash_short || bundle.payload || 'encrypted'}`,
            success: true,
            time: new Date().toLocaleTimeString('en-US', { hour12: false }),
            station: bundle.source_station,
            mode: "DTN",
            bundleId: bundle.bundle_id_short,
            priority: bundle.priority,
            status: "DELIVERED"
          };
          setMessages(prev => {
            const updated = [...prev, newMessage];
            messagesRef.current = updated;
            return updated;
          });
        });
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [mode, stationQueue]);

  // Process ISS decrypted messages for this station
  useEffect(() => {
    const stationMessages = stationDecryptedMessages[activeStationId] || [];
    stationMessages.forEach(msg => {
      // Only display if not already displayed
      if (!displayedBundleIds.current.has(msg.bundle_id)) {
        displayedBundleIds.current.add(msg.bundle_id);
        
        // Determine message prefix based on message type
        let messageText = "";
        if (msg.is_broadcast === true || msg.destination_station === "BROADCAST") {
          // Broadcast message
          messageText = `BROADCAST Message Received: ${msg.decrypted_payload}`;
        } else {
          // Specific station message
          messageText = `Message Received from ISS: ${msg.decrypted_payload}`;
        }
        
        const newMessage: Message = {
          id: messageIdCounter.current++,
          text: messageText,
          success: true,
          time: new Date(msg.reassembled_at).toLocaleTimeString('en-US', { hour12: false }),
          station: activeStationId,
          mode: "DTN",
          bundleId: msg.bundle_id.substring(0, 8),
          status: "DELIVERED"
        };
        
        setMessages(prev => {
          const updated = [...prev, newMessage];
          messagesRef.current = updated;
          return updated;
        });
      }
    });
  }, [stationDecryptedMessages, activeStationId]);

  // Process custody ACKs
  useEffect(() => {
    if (custodyAcks && custodyAcks.length > 0) {
      custodyAcks.forEach(ack => {
        const ackText = ack.ack_type === "delivered"
          ? `◀ ACK: Bundle ${ack.bundle_id_short} delivered to ${ack.from_station.toUpperCase()}`
          : `◀ ACK: ${ack.from_station.toUpperCase()} accepted custody of ${ack.bundle_id_short}`;
        
        setMessages(prev => {
          // Avoid duplicate ACKs
          const ackTime = new Date(ack.timestamp).toLocaleTimeString('en-US', { hour12: false });
          if (prev.some(m => m.isAck && m.bundleId === ack.bundle_id_short && m.time === ackTime)) {
            return prev;
          }
          
          const newMessage: Message = {
            id: messageIdCounter.current++,
            text: ackText,
            success: true,
            time: ackTime,
            station: ack.to_station,
            mode: "DTN",
            bundleId: ack.bundle_id_short,
            isAck: true,
            ackType: ack.ack_type
          };
          const updated = [...prev, newMessage];
          messagesRef.current = updated;
          return updated;
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
        const newMessage: Message = {
          id: messageIdCounter.current++,
          text: `[${stationName}] GND> ${message}`,
          success: false,
          time: timestamp,
          station: activeStationId,
          mode: "TCP"
        };
        setMessages(prev => {
          const updated = [...prev, newMessage];
          messagesRef.current = updated;
          return updated;
        });
        setMessage("");
        return;
      }

      setProtocolDirection('uplink');
      
      const uplinkMessage: Message = {
        id: messageIdCounter.current++,
        text: `[${stationName}] GND> ${message}`,
        success: true,
        time: timestamp,
        station: activeStationId,
        mode: "TCP"
      };
      setMessages(prev => {
        const updated = [...prev, uplinkMessage];
        messagesRef.current = updated;
        return updated;
      });
      setMessage("");

      setTimeout(() => {
        setProtocolDirection('downlink');
        const ackMessage: Message = {
          id: messageIdCounter.current++,
          text: `[${stationName}] ISS> ACK: ${message.substring(0, 20)}...`,
          success: true,
          time: new Date().toLocaleTimeString('en-US', { hour12: false }),
          station: activeStationId,
          mode: "TCP"
        };
        setMessages(prev => {
          const updated = [...prev, ackMessage];
          messagesRef.current = updated;
          return updated;
        });
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
          const newMessage: Message = {
            id: messageIdCounter.current++,
            text: `[${stationName}] Bundle created: 🔐 ${bundle.payload_hash_short || bundle.payload_hash || 'encrypted'}`,
            success: true,
            time: timestamp,
            station: activeStationId,
            mode: "DTN",
            bundleId: bundle.bundle_id_short,
            priority: bundle.priority,
            status: isConnected ? "TRANSMITTING" : "QUEUED"
          };
          setMessages(prev => {
            const updated = [...prev, newMessage];
            messagesRef.current = updated;
            return updated;
          });
        } else {
          const newMessage: Message = {
            id: messageIdCounter.current++,
            text: `[${stationName}] Failed to create bundle: ${result.error}`,
            success: false,
            time: timestamp,
            station: activeStationId,
            mode: "DTN"
          };
          setMessages(prev => {
            const updated = [...prev, newMessage];
            messagesRef.current = updated;
            return updated;
          });
        }
      } catch (error) {
        console.error('Error creating bundle:', error);
        const newMessage: Message = {
          id: messageIdCounter.current++,
          text: `[${stationName}] Error creating bundle`,
          success: false,
          time: timestamp,
          station: activeStationId,
          mode: "DTN"
        };
        setMessages(prev => {
          const updated = [...prev, newMessage];
          messagesRef.current = updated;
          return updated;
        });
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
        <div className="flex items-center gap-1.5 mb-2">
          <div className="text-[9px] font-semibold tracking-wider uppercase text-secondary">
            PROTOCOL
          </div>
          <InfoTooltip
            content={
              <div className="space-y-2">
                <div>
                  <strong>Protocol Stack</strong>
                </div>
                <div className="text-xs space-y-1.5">
                  <p>Shows the layered protocol architecture during message transmission.</p>
                  <p><strong>TCP Mode Stack:</strong></p>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>Application: HTTP payload</li>
                    <li>Transport: TCP (reliable delivery)</li>
                    <li>Network: IP (routing)</li>
                    <li>Physical: RF transmission</li>
                  </ul>
                  <p><strong>DTN Mode Stack:</strong></p>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>Application: HTTP payload</li>
                    <li>Bundle: DTN layer (store-and-forward)</li>
                    <li>Transport: TCP</li>
                    <li>Network: IP</li>
                    <li>Physical: RF</li>
                  </ul>
                  <p><strong>Animation:</strong> Shows packet moving through layers during transmission. Uplink = down arrow, Downlink = up arrow.</p>
                  <p><strong>DTN Layer (Red):</strong> Unique to DTN mode. Handles bundle encapsulation, routing, and custody transfer.</p>
                  <p><strong>Understanding:</strong> Each layer adds headers and handles specific functions. The stack ensures reliable data delivery across the network.</p>
                </div>
              </div>
            }
          />
        </div>
        <ProtocolStack direction={protocolDirection} mode={mode} />
      </div>

      {/* Message Terminal - Right side */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mode Toggle */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
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
            <InfoTooltip
              content={
                <div className="space-y-2">
                  <div>
                    <strong>Communication Modes</strong>
                  </div>
                  <div className="text-xs space-y-1.5">
                    <p><strong>TCP Mode:</strong> Traditional connection-oriented protocol. Requires continuous connection.</p>
                    <ul className="list-disc list-inside space-y-0.5 ml-2">
                      <li>Only works when Toronto station is active and connected</li>
                      <li>Real-time bidirectional communication</li>
                      <li>Immediate acknowledgments</li>
                      <li>Fails if connection is interrupted</li>
                    </ul>
                    <p><strong>DTN Mode:</strong> Delay-Tolerant Networking for intermittent connectivity.</p>
                    <ul className="list-disc list-inside space-y-0.5 ml-2">
                      <li>Works even when station is not in contact</li>
                      <li>Bundles are stored and forwarded when contact available</li>
                      <li>Supports custody transfer between stations</li>
                      <li>Handles network disruptions gracefully</li>
                    </ul>
                    <p><strong>Use Case:</strong> TCP for real-time commands, DTN for reliable data delivery in intermittent networks.</p>
                  </div>
                </div>
              }
            />
          </div>
          
          <div className="flex items-center gap-4">
            {/* Station indicator */}
            <div className="flex items-center gap-2 text-xs font-mono">
              <div 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: stationColor }}
              />
              <span className="text-secondary">
                Controlling: <span className="text-foreground font-semibold uppercase">
                  {activeStationId}
                </span>
              </span>
            </div>
            
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
                Network Queue: {queuedBundles.length} bundles
              </div>
            )}
          </div>
        </div>

        {/* Message Log */}
        <div className="flex-1 terminal p-3 overflow-y-auto space-y-2 mb-3">
          {messages.map((msg, idx) => {
            const displayedText = typingProgress[msg.id] !== undefined 
              ? msg.text.substring(0, typingProgress[msg.id])
              : '';
            const isTyping = typingProgress[msg.id] !== undefined && typingProgress[msg.id] < msg.text.length;
            
            return (
              <div 
                key={msg.id} 
                className="flex items-start gap-2 text-sm font-mono"
              >
                {getStatusIcon(msg)}
                <div className="flex-1 min-w-0">
                  <span className={`${
                    msg.isAck ? 'text-cyan-400' :
                    msg.success ? 'text-terminal-text' : 'text-destructive'
                  }`}>
                    {displayedText}
                    {isTyping && (
                      <span className="inline-block w-2 h-4 bg-current animate-pulse ml-0.5" />
                    )}
                  </span>
                  {/* Only show bundle details for non-ACK messages */}
                  {msg.bundleId && !msg.isAck && !isTyping && (
                    <div className="text-xs text-secondary mt-1">
                      [Bundle: {msg.bundleId}] [Priority: {msg.priority}] [TTL: 24h]
                      {msg.status && ` [${msg.status}]`}
                    </div>
                  )}
                </div>
                <span className="text-terminal-text/60 text-xs flex-shrink-0">{msg.time}</span>
              </div>
            );
          })}
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
                  title={`Encrypted payload: ${bundle.payload_hash_short || bundle.payload || 'encrypted'}`}
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
          <div className="space-y-1.5 mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-secondary uppercase">Bundle Priority</span>
              <InfoTooltip
                content={
                  <div className="space-y-2">
                    <div>
                      <strong>Bundle Priority Levels</strong>
                    </div>
                    <div className="text-xs space-y-1.5">
                      <p><strong>EXPEDITED (Red):</strong> Highest priority bundles</p>
                      <ul className="list-disc list-inside space-y-0.5 ml-2">
                        <li>Transmitted first when contact available</li>
                        <li>Used for urgent commands or critical data</li>
                        <li>May preempt lower priority bundles</li>
                      </ul>
                      <p><strong>NORMAL (Cyan):</strong> Standard priority</p>
                      <ul className="list-disc list-inside space-y-0.5 ml-2">
                        <li>Default for most communications</li>
                        <li>Transmitted after expedited bundles</li>
                        <li>Balanced throughput and fairness</li>
                      </ul>
                      <p><strong>BULK (Gray):</strong> Lowest priority</p>
                      <ul className="list-disc list-inside space-y-0.5 ml-2">
                        <li>Transmitted when bandwidth available</li>
                        <li>Used for large data transfers</li>
                        <li>May be delayed during high traffic</li>
                      </ul>
                      <p><strong>Routing:</strong> Priority affects forwarding order in DTN network. Higher priority bundles are routed first through the mesh.</p>
                    </div>
                  </div>
                }
              />
            </div>
            <div className="flex gap-1">
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