import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle, Clock } from "lucide-react";
import { DTNBundle } from "@/types/dtnBundle";

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

interface TransmissionHistoryProps {
  deliveredBundles?: DTNBundle[];
}

const TransmissionHistory = ({ deliveredBundles = [] }: TransmissionHistoryProps) => {
  const [bundleHistory, setBundleHistory] = useState<BundleJourney[]>([]);

  // Track last 5 delivered bundles
  useEffect(() => {
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
    <Card className="p-4">
      <div className="text-xs uppercase tracking-wide text-secondary mb-3">
        TRANSMISSION HISTORY (LAST 5 DELIVERED)
      </div>
      <div className="space-y-3">
        {bundleHistory.length === 0 ? (
          <div className="text-xs text-secondary/50 text-center py-2">
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
                  <span className="text-[11px] font-mono text-foreground font-semibold">
                    {bundle.bundle_id_short}
                  </span>
                  <span
                    className="text-[11px] font-mono px-1 py-0.5 rounded"
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

              {/* Message Payload - Show encrypted hash */}
              <div className="mb-2 text-[11px] text-secondary italic truncate font-mono">
                🔐 {bundle.payload_hash_short || bundle.payload || 'encrypted'}
              </div>

              {/* Path Visualization */}
              <div className="flex items-center gap-1 mb-2 flex-wrap">
                {bundle.hops.map((hop, idx) => (
                  <div key={idx} className="flex items-center gap-1">
                    <span className="text-[11px] text-foreground uppercase font-mono bg-background/80 px-1.5 py-0.5 rounded">
                      {hop}
                    </span>
                    {idx < bundle.hops.length - 1 && (
                      <ArrowRight className="w-2.5 h-2.5 text-secondary" />
                    )}
                  </div>
                ))}
              </div>

              {/* Stats: Size, Time, Created */}
              <div className="grid grid-cols-3 gap-2 text-[11px] text-secondary">
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
    </Card>
  );
};

export default TransmissionHistory;

