import { Card } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";
import { ArrowRight, CheckCircle } from "lucide-react";

interface DTNBundle {
  bundle_id: string;
  bundle_id_short: string;
  priority: "EXPEDITED" | "NORMAL" | "BULK";
  status: string;
  age_seconds: number;
  hops: string[];
  current_custodian: string;
  created_at: string;
  delivered_at?: string | null;
}

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
  } | null;
  activeStationQueue?: DTNBundle[];
  allQueues?: Record<string, DTNBundle[]>;
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
}

interface StationSignalHistory {
  [stationId: string]: boolean[]; // Last 1800 samples (30 minutes at 1 sample/sec)
}

const TrafficFlowMonitor = ({ 
  linkStatus,
  allQueues = {},
  stations = [],
  isConnected = false 
}: TrafficFlowMonitorProps) => {
  const [uplinkBandwidth, setUplinkBandwidth] = useState(0);
  const [downlinkBandwidth, setDownlinkBandwidth] = useState(0);
  const [throughputData, setThroughputData] = useState<Array<{time: string, uplink: number, downlink: number}>>([]);
  const [queueStats, setQueueStats] = useState({ avgTime: 0, maxDepth: 0 });
  const [bundleJourneys, setBundleJourneys] = useState<BundleJourney[]>([]);
  const [signalHistory, setSignalHistory] = useState<StationSignalHistory>({});

  // Initialize signal history for all stations
  useEffect(() => {
    if (stations.length > 0) {
      const initialHistory: StationSignalHistory = {};
      stations.forEach(station => {
        if (!signalHistory[station.id]) {
          initialHistory[station.id] = Array(1800).fill(false); // 30 minutes
        }
      });
      setSignalHistory(prev => ({ ...prev, ...initialHistory }));
    }
  }, [stations]);

  // Update signal history every second
  useEffect(() => {
    const interval = setInterval(() => {
      setSignalHistory(prev => {
        const updated = { ...prev };
        stations.forEach(station => {
          if (updated[station.id]) {
            // Shift array and add new sample
            updated[station.id] = [...updated[station.id].slice(1), station.is_visible];
          } else {
            updated[station.id] = Array(1800).fill(false); // 30 minutes
          }
        });
        return updated;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [stations]);

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

  // Calculate realistic bandwidth based on link quality
  useEffect(() => {
    console.log('Link Status Update:', {
      linkStatus,
      isConnected,
      connectionState: linkStatus?.connection_state,
      snr: linkStatus?.snr_db
    });

    if (!linkStatus || linkStatus.connection_state === "IDLE") {
      console.log('Setting bandwidth to 0 - IDLE or no link status');
      setUplinkBandwidth(0);
      setDownlinkBandwidth(0);
      return;
    }

    const { connection_state, snr_db } = linkStatus;

    let uplinkRate = 0;
    let downlinkRate = 0;

    if (connection_state === "ACQUIRED") {
      // SNR ≥ 10 dB - Good connection
      const snrFactor = Math.min((snr_db - 10) / 30, 1);
      uplinkRate = 1.2 + (snrFactor * 8.8);
      downlinkRate = 3 + (snrFactor * 22);
      
      // Add some realistic variation
      uplinkRate += (Math.random() - 0.5) * 0.5;
      downlinkRate += (Math.random() - 0.5) * 1.5;
      
      console.log('ACQUIRED - Calculated rates:', { uplinkRate, downlinkRate, snr_db, snrFactor });
    } else if (connection_state === "DEGRADED") {
      // SNR 3-10 dB - Marginal connection
      const snrFactor = Math.min((snr_db - 3) / 7, 1);
      uplinkRate = 0.3 + (snrFactor * 0.9);
      downlinkRate = 0.8 + (snrFactor * 2.2);
      
      // More variation for degraded link
      uplinkRate += (Math.random() - 0.5) * 0.3;
      downlinkRate += (Math.random() - 0.5) * 0.8;
      
      console.log('DEGRADED - Calculated rates:', { uplinkRate, downlinkRate, snr_db, snrFactor });
    }

    setUplinkBandwidth(Math.max(0, uplinkRate));
    setDownlinkBandwidth(Math.max(0, downlinkRate));

  }, [linkStatus, isConnected]);

  // Update throughput graph
  useEffect(() => {
    const interval = setInterval(() => {
      setThroughputData(prev => {
        const newData = [...prev.slice(1), {
          time: '0s',
          uplink: uplinkBandwidth,
          downlink: downlinkBandwidth,
        }];
        return newData;
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [uplinkBandwidth, downlinkBandwidth]);

  // In the component, calculate ALL bundles across network
  const allBundles = Object.values(allQueues).flat();
  const allQueuedBundles = allBundles.filter(b => b.status === "QUEUED");

  // Update queue stats to use all bundles
  useEffect(() => {
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
  }, [allQueues]); // Changed dependency

  // Track bundle journeys (delivered and in-progress)
  useEffect(() => {
    const allBundles: DTNBundle[] = Object.values(allQueues).flat();
    
    // Get delivered bundles and recently created bundles
    const journeys = allBundles
      .filter(b => b.status === "DELIVERED" || b.hops.length > 0)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5)
      .map(b => ({
        bundle_id_short: b.bundle_id_short,
        payload: "payload" in b ? (b as any).payload?.substring(0, 20) || "data" : "data",
        hops: b.hops,
        priority: b.priority,
        status: b.status,
        created_at: b.created_at,
        delivered_at: b.delivered_at
      }));
    
    setBundleJourneys(journeys);
  }, [allQueues]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'EXPEDITED': return '#ef4444';
      case 'NORMAL': return '#00d4ff';
      case 'BULK': return '#6b7280';
      default: return '#6b7280';
    }
  };

  // Calculate uptime percentage for a station
  const calculateUptime = (history: boolean[]) => {
    const activeCount = history.filter(v => v).length;
    return Math.round((activeCount / history.length) * 100);
  };

  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-secondary mb-4">
        TRAFFIC FLOW MONITOR
      </h3>

      {/* 1. Uplink/Downlink Bandwidth Usage */}
      <div className="mb-4 space-y-3">
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">UPLINK</span>
            <span className="text-xs font-mono text-muted-foreground">
              {uplinkBandwidth.toFixed(1)} Mbps / 10 Mbps
            </span>
          </div>
          <div className="h-3 bg-[#1a1d29] rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300 ease-out"
              style={{ width: `${(uplinkBandwidth / 10) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">DOWNLINK</span>
            <span className="text-xs font-mono text-muted-foreground">
              {downlinkBandwidth.toFixed(1)} Mbps / 25 Mbps
            </span>
          </div>
          <div className="h-3 bg-[#1a1d29] rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all duration-300 ease-out"
              style={{ width: `${(downlinkBandwidth / 25) * 100}%` }}
            />
          </div>
        </div>
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

      {/* 3. Throughput Graph Over Time */}
      <div className="mb-4 p-3 bg-[#1a1d29] rounded-lg">
        <div className="flex justify-between items-center mb-2">
          <div className="text-[10px] font-mono text-muted-foreground space-y-0.5">
            <div className="text-cyan-400">Uplink: {uplinkBandwidth.toFixed(1)} Mbps</div>
            <div className="text-green-400">Downlink: {downlinkBandwidth.toFixed(1)} Mbps</div>
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
              domain={[0, 30]}
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

      {/* Signal Quality Heatmap */}
      <div className="mb-4 p-3 bg-[#1a1d29] rounded-lg">
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-3">
          SIGNAL QUALITY (LAST 30 MIN)
        </div>
        <div className="space-y-2">
          {stations.slice(0, 6).map((station) => {
            const history = signalHistory[station.id] || Array(1800).fill(false);
            const uptime = calculateUptime(history);
            
            return (
              <div key={station.id} className="flex items-center gap-2">
                <div className="flex-shrink-0 w-20 text-[10px] font-mono text-secondary">
                  {station.name}
                </div>
                <div className="flex-1 flex gap-[1px]">
                  {history.map((active, idx) => (
                    <div
                      key={idx}
                      className="flex-1 h-4 rounded-[1px]"
                      style={{
                        backgroundColor: active ? '#22c55e' : '#1e293b',
                      }}
                    />
                  ))}
                </div>
                <div className="flex-shrink-0 w-10 text-right text-[10px] font-mono text-secondary">
                  {uptime}%
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
};

export default TrafficFlowMonitor;