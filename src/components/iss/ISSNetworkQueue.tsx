import { Card } from "@/components/ui/card";
import { Package, Radio, Megaphone } from "lucide-react";
import { DTNBundle } from "@/types/dtnBundle";
import { GroundStation } from "@/types/groundStation";

interface ISSNetworkQueueProps {
  bundles?: DTNBundle[];
  stations?: GroundStation[];
}

const ISSNetworkQueue = ({ bundles = [], stations = [] }: ISSNetworkQueueProps) => {
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "EXPEDITED": return "#ef4444";
      case "NORMAL": return "#00d4ff";
      case "BULK": return "#6b7280";
      default: return "#00d4ff";
    }
  };

  const getDestinationDisplay = (bundle: DTNBundle) => {
    if (bundle.destination_station.toUpperCase() === "BROADCAST") {
      return {
        text: "BROADCAST",
        icon: <Megaphone className="w-3 h-3" />,
        color: "#a855f7"
      };
    }
    
    const station = stations.find(s => s.id === bundle.destination_station);
    if (station) {
      return {
        text: station.name,
        icon: (
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: station.color }}
          />
        ),
        color: station.color
      };
    }
    
    return {
      text: bundle.destination_station,
      icon: <Radio className="w-3 h-3" />,
      color: "#00d4ff"
    };
  };

  return (
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
          <Package className="w-3 h-3" />
          NETWORK QUEUE
        </h3>
        <div className="text-[11px] font-mono text-secondary mt-1">
          Bundles queued for transmission from ISS
        </div>
      </div>

      {bundles.length === 0 ? (
        <div className="text-[11px] text-secondary font-mono py-4 text-center">
          No bundles in queue
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary mb-2">
            QUEUED BUNDLES ({bundles.length})
          </div>
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {bundles.map((bundle) => {
              const destination = getDestinationDisplay(bundle);
              
              return (
                <div
                  key={bundle.bundle_id}
                  className="flex items-start gap-2 p-1.5 rounded bg-background/50 hover:bg-background/80 transition-colors"
                >
                  <div
                    className="w-1 h-full rounded-full flex-shrink-0 mt-1"
                    style={{ backgroundColor: getPriorityColor(bundle.priority) }}
                  />
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="text-[13px] font-mono text-foreground font-semibold">
                        {bundle.bundle_id_short}
                      </span>
                      <span
                        className="text-[12px] font-mono px-1 py-0.5 rounded"
                        style={{
                          color: getPriorityColor(bundle.priority),
                          backgroundColor: `${getPriorityColor(bundle.priority)}20`
                        }}
                      >
                        {bundle.priority}
                      </span>
                      <span className={`text-[12px] font-mono ${
                        bundle.status === "DELIVERED" ? "text-success" :
                        bundle.status === "TRANSMITTING" ? "text-amber-500" :
                        "text-secondary"
                      }`}>
                        {bundle.status}
                      </span>
                    </div>
                    
                    {/* Destination Station */}
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-[10px] font-semibold tracking-wider uppercase text-secondary">
                        TO:
                      </span>
                      <div 
                        className="flex items-center gap-1 text-[12px] font-mono font-semibold"
                        style={{ color: destination.color }}
                      >
                        {destination.icon}
                        {destination.text}
                      </div>
                    </div>
                    
                    <div className="text-[13px] text-secondary truncate font-mono">
                      🔐 {bundle.payload_hash_short || bundle.payload || 'encrypted'}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-[12px] text-secondary flex-wrap">
                      <span>Size: {bundle.size_bytes} bytes ({(bundle.size_bytes / 1024).toFixed(1)} KB)</span>
                      <span>Age: {Math.floor(bundle.age_seconds)}s</span>
                      <span>TTL: {bundle.ttl_hours}h</span>
                    </div>
                  </div>

                  <div className="flex-shrink-0">
                    {bundle.status === "QUEUED" && (
                      <div className="w-2 h-2 rounded-full bg-cyan-500" />
                    )}
                    {bundle.status === "TRANSMITTING" && (
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                    )}
                    {bundle.status === "DELIVERED" && (
                      <div className="w-2 h-2 rounded-full bg-success" />
                    )}
                    {bundle.status === "FORWARDED" && (
                      <div className="w-2 h-2 rounded-full bg-purple-500" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
};

export default ISSNetworkQueue;
