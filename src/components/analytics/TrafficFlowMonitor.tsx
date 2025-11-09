import { Card } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";
import { ArrowRight, CheckCircle, Clock } from "lucide-react";
import { DTNBundle } from "@/types/dtnBundle";

interface Station {
  id: string;
  name: string;
  is_visible: boolean;
}

interface TrafficFlowMonitorProps {
  linkStatus?: {
    connection_state: "ACQUIRED" | "DEGRADED" | "IDLE";
    snr_db: number;
    range_km: number;
    data_rate_bps?: number;
    data_rate_kbps?: number;
  } | null;
  visibleLinks?: Array<{
    station_id: string;
    station_name: string;
    signal_strength_dbm: number;
    connection_state: string;
    snr_db: number;
    data_rate_kbps: number;
  }>;
  allQueues?: Record<string, DTNBundle[]>;
  deliveredBundles?: DTNBundle[];
  stations?: Station[];
  isConnected?: boolean;
}

interface BundleJourney {
  bundle_id_short: string;
  payload: string;
  hops: string[];
  priority: string;
  status: string;
  created_at: string;
  delivered_at?: string | null;
  size_bytes: number;
  delivery_time_sec?: number;
}

const TrafficFlowMonitor = ({ 
  linkStatus,
  allQueues = {},
  deliveredBundles = [],
  visibleLinks = [],
  stations = [],
  isConnected = false 
}: TrafficFlowMonitorProps) => {
  const [uplinkBandwidth, setUplinkBandwidth] = useState(0);
  const [downlinkBandwidth, setDownlinkBandwidth] = useState(0);
  const [throughputData, setThroughputData] = useState<Array<{time: string, uplink: number, downlink: number}>>([]);
  const [queueStats, setQueueStats] = useState({ avgTime: 0, maxDepth: 0 });
  const [bundleHistory, setBundleHistory] = useState<BundleJourney[]>([]);

  // Initialize throughput data
  useEffect(() => {
    const initialData = [];
    for (let i = 60; i >= 0; i -= 5) {
      initialData.push({
        time: `-${i}s`,
        uplink: 0,
        downlink: 0,
      });
    }
    setThroughputData(initialData);
  }, []);

  // Update queue stats
  useEffect(() => {
    const allBundles = Object.values(allQueues).flat();
    const allQueuedBundles = allBundles.filter(b => b.status === "QUEUED");
    
    if (allBundles.length === 0) {
      setQueueStats({ avgTime: 0, maxDepth: 0 });
      return;
    }

    const avgAge = allQueuedBundles.length > 0 
      ? allQueuedBundles.reduce((sum, b) => sum + b.age_seconds, 0) / allQueuedBundles.length 
      : 0;
    
    setQueueStats({
      avgTime: Math.floor(avgAge * 1000),
      maxDepth: allBundles.length
    });
  }, [allQueues]);

  // Calculate ALL bundles across network (for rendering)
  const allBundles = Object.values(allQueues).flat();
  const allQueuedBundles = allBundles.filter(b => b.status === "QUEUED");

  // Update bandwidth based on visible links or link status
  // Priority: visibleLinks > linkStatus > 0
  useEffect(() => {
    let dataRateKbps = 0;
    
    // First priority: Use visibleLinks (all stations that can see ISS)
    // Backend already filters to only include visible stations, so we trust the data_rate_kbps values
    if (visibleLinks && visibleLinks.length > 0) {
      // Sum up data rates from all visible stations
      // Include all visible links - backend ensures they're actually visible
      dataRateKbps = visibleLinks.reduce((sum, link) => {
        const rate = link.data_rate_kbps || 0;
        // Only include positive data rates (stations with actual connection)
        return sum + (rate > 0 ? rate : 0);
      }, 0);
    } 
    // Fallback: Use linkStatus from active station
    else if (linkStatus && linkStatus.connection_state !== "IDLE" && linkStatus.data_rate_kbps) {
      dataRateKbps = linkStatus.data_rate_kbps || 0;
    }
    
    // If we have a valid data rate, calculate uplink/downlink
    if (dataRateKbps > 0) {
      // Add small variation for visual interest (but keep it stable)
      const variation = (Math.random() - 0.5) * 0.3; // Reduced variation for more stable display
      
      const uplinkRate = Math.max(0, dataRateKbps + variation);
      const downlinkRate = Math.max(0, dataRateKbps * 1.2 + variation); // Slightly higher downlink
      
      setUplinkBandwidth(uplinkRate);
      setDownlinkBandwidth(downlinkRate);
    } else {
      // No connection - set to 0
      setUplinkBandwidth(0);
      setDownlinkBandwidth(0);
    }
    
    // Debug logging (development only)
    // Check if we're in development mode using a safe method
    const isDev = typeof window !== 'undefined' && 
                  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
    
    if (isDev && dataRateKbps > 0) {
      console.log('[TrafficFlowMonitor] Bandwidth update:', {
        visibleLinksCount: visibleLinks?.length || 0,
        dataRateKbps: dataRateKbps.toFixed(2),
        linkStatusState: linkStatus?.connection_state,
        hasVisibleLinks: (visibleLinks && visibleLinks.length > 0),
        visibleLinksData: visibleLinks?.map(l => ({ 
          station: l.station_name, 
          rate: l.data_rate_kbps,
          state: l.connection_state 
        }))
      });
    }
  }, [linkStatus, visibleLinks]);

  // Update throughput graph - runs more frequently to catch ISS visibility changes
  useEffect(() => {
    // Immediately update the graph when bandwidth changes (don't wait for interval)
    setThroughputData(prev => {
      const newData = [...prev.slice(1), {
        time: '0s',
        uplink: uplinkBandwidth,
        downlink: downlinkBandwidth,
      }];
      return newData;
    });

    // Also update periodically to keep the graph moving
    const interval = setInterval(() => {
      setThroughputData(prev => {
        const newData = [...prev.slice(1), {
          time: '0s',
          uplink: uplinkBandwidth,
          downlink: downlinkBandwidth,
        }];
        return newData;
      });
    }, 1000); // Update every second

    return () => clearInterval(interval);
  }, [uplinkBandwidth, downlinkBandwidth]);

  // Track last 5 delivered bundles
  useEffect(() => {
    console.log('Delivered bundles prop:', deliveredBundles);
    
    const journeys = deliveredBundles
      .slice(0, 5)
      .map(b => {
        const createdTime = new Date(b.created_at).getTime();
        const deliveredTime = b.delivered_at ? new Date(b.delivered_at).getTime() : createdTime;
        const deliveryTimeSec = (deliveredTime - createdTime) / 1000;
        
        return {
          bundle_id_short: b.bundle_id_short,
          payload: b.payload,
          hops: b.hops,
          priority: b.priority,
          status: b.status,
          created_at: b.created_at,
          delivered_at: b.delivered_at,
          size_bytes: b.size_bytes,
          delivery_time_sec: deliveryTimeSec
        };
      });
    
    console.log('Bundle history to display:', journeys);
    setBundleHistory(journeys);
  }, [deliveredBundles]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'EXPEDITED': return '#ef4444';
      case 'NORMAL': return '#00d4ff';
      case 'BULK': return '#6b7280';
      default: return '#6b7280';
    }
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-secondary mb-4">
        TRAFFIC FLOW MONITOR
      </h3>

      {/* 1. Uplink/Downlink Bandwidth Usage - NOW IN KBPS */}
      <div className="mb-4 space-y-3">
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">UPLINK</span>
            <span className="text-xs font-mono text-muted-foreground">
              {uplinkBandwidth.toFixed(1)} kbps / 200 kbps
            </span>
          </div>
          <div className="h-3 bg-[#1a1d29] rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300 ease-out"
              style={{ width: `${(uplinkBandwidth / 200) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">DOWNLINK</span>
            <span className="text-xs font-mono text-muted-foreground">
              {downlinkBandwidth.toFixed(1)} kbps / 200 kbps
            </span>
          </div>
          <div className="h-3 bg-[#1a1d29] rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all duration-300 ease-out"
              style={{ width: `${(downlinkBandwidth / 200) * 100}%` }}
            />
          </div>
        </div>

        {visibleLinks && visibleLinks.length > 1 && (
          <div className="pt-2 border-t border-border/30">
            <div className="text-[9px] text-secondary/80 mb-1">
              Active Links ({visibleLinks.length} stations):
            </div>
            <div className="space-y-1">
              {visibleLinks.map(link => (
                <div key={link.station_id} className="flex justify-between items-center text-[9px]">
                  <span className="text-secondary uppercase font-mono">{link.station_name}</span>
                  <span className="text-cyan-400 font-mono">{link.data_rate_kbps.toFixed(1)} kbps</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 2. Bundle Queue Visualization - NETWORK-WIDE */}
      <div className="mb-4 p-3 bg-[#1a1d29] rounded-lg">
        <div className="flex justify-between items-center mb-2">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">NETWORK BUNDLE QUEUE</span>
          <span className="text-xs font-mono text-muted-foreground">
            Queue: {allQueuedBundles.length} bundles
          </span>
        </div>
        <div className="flex gap-1 mb-2 h-5 items-center flex-wrap">
          {allQueuedBundles
            .slice(0, 15)
            .map((bundle) => (
              <div
                key={bundle.bundle_id}
                className="w-[30px] h-5 rounded animate-fade-in"
                style={{
                  backgroundColor: getPriorityColor(bundle.priority),
                  boxShadow: `0 0 8px ${getPriorityColor(bundle.priority)}50`,
                }}
                title={`${bundle.priority}: ${bundle.bundle_id_short} @ ${bundle.current_custodian}`}
              />
            ))}
          {allQueuedBundles.length === 0 && (
            <span className="text-xs text-muted-foreground/50 italic">No bundles in queue</span>
          )}
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>Avg Queue Time: {queueStats.avgTime} ms</span>
          <span>Network Depth: {queueStats.maxDepth} bundles</span>
        </div>
      </div>

      {/* 3. Throughput Graph Over Time - NOW IN KBPS */}
      <div className="mb-4 p-3 bg-[#1a1d29] rounded-lg">
        <div className="flex justify-between items-center mb-2">
          <div className="text-[10px] font-mono text-muted-foreground space-y-0.5">
            <div className="text-cyan-400">Uplink: {uplinkBandwidth.toFixed(1)} kbps</div>
            <div className="text-green-400">Downlink: {downlinkBandwidth.toFixed(1)} kbps</div>
          </div>
          <div className="flex gap-3 text-[10px]">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-cyan-500 rounded-sm" />
              <span className="text-muted-foreground">Uplink</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-green-500 rounded-sm" />
              <span className="text-muted-foreground">Downlink</span>
            </span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={throughputData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3f4b" />
            <XAxis 
              dataKey="time" 
              stroke="#6b7280" 
              style={{ fontSize: '10px' }}
              tick={{ fill: '#6b7280' }}
            />
            <YAxis 
              stroke="#6b7280" 
              style={{ fontSize: '10px' }}
              tick={{ fill: '#6b7280' }}
              domain={[0, 200]}
              label={{ value: 'kbps', angle: -90, position: 'insideLeft', style: { fontSize: '10px', fill: '#6b7280' } }}
            />
            <Line 
              type="monotone" 
              dataKey="uplink" 
              stroke="#00d4ff" 
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line 
              type="monotone" 
              dataKey="downlink" 
              stroke="#4ade80" 
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Last 5 Delivered Bundles History */}
      <div className="p-3 bg-[#1a1d29] rounded-lg">
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-3">
          TRANSMISSION HISTORY (LAST 5 DELIVERED)
        </div>
        <div className="space-y-3">
          {bundleHistory.length === 0 ? (
            <div className="text-xs text-muted-foreground/50 text-center py-2">
              No delivered bundles yet
            </div>
          ) : (
            bundleHistory.map((bundle) => (
              <div 
                key={`${bundle.bundle_id_short}-${bundle.delivered_at}`}
                className="p-2 rounded bg-background/50 hover:bg-background/80 transition-colors border border-border/50"
              >
                {/* Header: ID, Priority, Status */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span 
                      className="w-2 h-2 rounded-full" 
                      style={{ backgroundColor: getPriorityColor(bundle.priority) }}
                    />
                    <span className="text-[10px] font-mono text-foreground font-semibold">
                      {bundle.bundle_id_short}
                    </span>
                    <span
                      className="text-[9px] font-mono px-1 py-0.5 rounded"
                      style={{
                        color: getPriorityColor(bundle.priority),
                        backgroundColor: `${getPriorityColor(bundle.priority)}20`
                      }}
                    >
                      {bundle.priority}
                    </span>
                  </div>
                  <CheckCircle className="w-3 h-3 text-success" />
                </div>

                {/* Message Payload */}
                <div className="mb-2 text-[10px] text-secondary italic truncate">
                  "{bundle.payload}"
                </div>

                {/* Path Visualization */}
                <div className="flex items-center gap-1 mb-2 flex-wrap">
                  {bundle.hops.map((hop, idx) => (
                    <div key={idx} className="flex items-center gap-1">
                      <span className="text-[9px] text-foreground uppercase font-mono bg-background/80 px-1.5 py-0.5 rounded">
                        {hop}
                      </span>
                      {idx < bundle.hops.length - 1 && (
                        <ArrowRight className="w-2.5 h-2.5 text-secondary" />
                      )}
                    </div>
                  ))}
                </div>

                {/* Stats: Size, Time, Created */}
                <div className="grid grid-cols-3 gap-2 text-[9px] text-secondary">
                  <div className="flex items-center gap-1">
                    <span className="text-secondary/60">Size:</span>
                    <span className="text-foreground font-mono">
                      {(bundle.size_bytes / 1024).toFixed(2)} KB
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5 text-secondary/60" />
                    <span className="text-foreground font-mono">
                      {bundle.delivery_time_sec !== undefined 
                        ? formatDuration(bundle.delivery_time_sec)
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-secondary/60">Created:</span>
                    <span className="text-foreground font-mono">
                      {formatTime(bundle.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Card>
  );
};

export default TrafficFlowMonitor;