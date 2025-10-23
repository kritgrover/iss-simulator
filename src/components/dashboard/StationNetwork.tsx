import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, ChevronDown, ChevronRight, ArrowRight, Package, Zap } from "lucide-react";
import { GroundStation } from "@/types/groundStation";
import { useState, useEffect } from "react";

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
  current_custodian: string;
  forwarded_to: string | null;
  age_seconds: number;
}

interface StationNetworkProps {
  stations: GroundStation[];
  onStationSelect: (stationId: string) => void;
  onAddStation?: () => void;
  dtnQueues?: Record<string, DTNBundle[]>;
  visibleStationsCount?: number;
  handoffInProgress?: boolean;  // NEW
  activeStationId?: string;      // NEW
}

const StationNetwork = ({ 
  stations, 
  onStationSelect, 
  onAddStation,
  dtnQueues = {},
  visibleStationsCount = 0,
  handoffInProgress = false,    // NEW
  activeStationId = ''          // NEW
}: StationNetworkProps) => {
  const [expandedStation, setExpandedStation] = useState<string | null>(null);
  const [highlightStation, setHighlightStation] = useState<string | null>(null);

  // Highlight active station during handoff
  useEffect(() => {
    if (activeStationId) {
      setHighlightStation(activeStationId);
      const timer = setTimeout(() => {
        setHighlightStation(null);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [activeStationId]);

  const toggleExpand = (stationId: string) => {
    setExpandedStation(expandedStation === stationId ? null : stationId);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "EXPEDITED": return "#ef4444";
      case "NORMAL": return "#00d4ff";
      case "BULK": return "#6b7280";
      default: return "#00d4ff";
    }
  };

  const getQueueStats = (stationId: string) => {
    const queue = dtnQueues[stationId] || [];
    const queued = queue.filter(b => b.status === "QUEUED").length;
    const forwarding = queue.filter(b => b.status === "FORWARDED").length;
    const transmitting = queue.filter(b => b.status === "TRANSMITTING").length;
    
    return { queued, forwarding, transmitting, total: queue.length };
  };

  const getNextHandoffStation = (currentStation: GroundStation) => {
    const otherStations = stations.filter(s => s.id !== currentStation.id);
    const nextStation = otherStations.reduce((closest, station) => {
      const closestTime = closest.nextPassTime === '--:--' ? 999999 : 
        parseInt(closest.nextPassTime.split(':')[0]) * 60 + parseInt(closest.nextPassTime.split(':')[1]);
      const stationTime = station.nextPassTime === '--:--' ? 999999 :
        parseInt(station.nextPassTime.split(':')[0]) * 60 + parseInt(station.nextPassTime.split(':')[1]);
      
      return stationTime < closestTime ? station : closest;
    }, otherStations[0]);

    return nextStation;
  };

  return (
    <Card className="p-4">
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
            GROUND STATION NETWORK
          </h3>
          {visibleStationsCount > 0 && (
            <div className="flex items-center gap-1 bg-success/20 rounded-full px-2 py-0.5">
              <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[10px] font-mono text-success">
                {visibleStationsCount} ACTIVE
              </span>
            </div>
          )}
        </div>
        {onAddStation && (
          <Button 
            variant="outline" 
            size="sm" 
            className="h-6 px-2 text-[10px]"
            onClick={onAddStation}
          >
            <Plus className="h-3 w-3 mr-1" />
            ADD
          </Button>
        )}
      </div>

      <div className="space-y-2">
        {stations.map((station) => {
          const queueStats = getQueueStats(station.id);
          const isExpanded = expandedStation === station.id;
          const stationQueue = dtnQueues[station.id] || [];
          const nextHandoff = getNextHandoffStation(station);
          const isHighlighted = highlightStation === station.id;

          return (
            <div
              key={station.id}
              className={`rounded border transition-all ${
                isHighlighted
                  ? 'border-amber-500 bg-amber-500/20 shadow-lg animate-pulse'  // NEW: Handoff highlight
                  : station.isActive
                  ? 'border-primary/50 bg-primary/5'
                  : 'border-border hover:border-border/60 hover:bg-muted/50'
              }`}
            >
              {/* Handoff Indicator Banner */}
              {isHighlighted && (
                <div className="flex items-center gap-2 bg-amber-500/30 px-2 py-1 border-b border-amber-500/50">
                  <Zap className="w-3 h-3 text-amber-500 animate-pulse" />
                  <span className="text-[10px] font-mono font-semibold text-amber-500 uppercase">
                    Handoff Active
                  </span>
                </div>
              )}

              {/* Station Header */}
              <div
                onClick={() => onStationSelect(station.id)}
                className="flex items-center justify-between p-2 cursor-pointer"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      station.isActive ? 'animate-pulse' : ''
                    }`}
                    style={{
                      backgroundColor: station.isActive ? station.color : '#6b7280',
                      boxShadow: station.isActive ? `0 0 8px ${station.color}` : 'none'
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold truncate">
                        {station.name}
                      </span>
                      {queueStats.total > 0 && (
                        <div className="flex items-center gap-1 bg-background/80 rounded px-1.5 py-0.5">
                          <Package className="w-2.5 h-2.5 text-cyan-500" />
                          <span className="text-[10px] font-mono text-cyan-500">
                            {queueStats.total}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="text-[10px] text-secondary truncate">
                      {station.location}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-[10px] text-secondary">
                      {station.isActive ? 'ACTIVE' : 'IDLE'}
                    </div>
                    {station.isActive ? (
                      <div className="text-xs font-mono">
                        Elev: {station.elevation.toFixed(1)}°
                      </div>
                    ) : (
                      <div className="text-xs font-mono text-secondary/60">
                        Next: {station.nextPassTime}
                      </div>
                    )}
                  </div>
                  
                  {queueStats.total > 0 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleExpand(station.id);
                      }}
                      className="p-1 hover:bg-background/50 rounded transition-colors"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3 text-secondary" />
                      ) : (
                        <ChevronRight className="w-3 h-3 text-secondary" />
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* Queue Progress Bar */}
              {queueStats.total > 0 && (
                <div className="px-2 pb-2">
                  <div className="relative h-2 bg-background rounded-full overflow-hidden">
                    {stationQueue
                      .filter(b => b.status === "QUEUED")
                      .map((bundle, idx) => (
                        <div
                          key={bundle.bundle_id}
                          className="absolute top-0 h-full transition-all duration-500"
                          style={{
                            left: `${(idx / queueStats.queued) * 100}%`,
                            width: `${(1 / queueStats.queued) * 100}%`,
                            backgroundColor: getPriorityColor(bundle.priority),
                            opacity: 0.8
                          }}
                          title={`${bundle.priority}: ${bundle.payload.substring(0, 30)}`}
                        />
                      ))}
                  </div>
                  
                  <div className="flex justify-between items-center mt-1">
                    <div className="text-[9px] font-mono text-secondary">
                      Bundles: 
                      {queueStats.queued > 0 && (
                        <span className="text-cyan-500 ml-1">
                          {queueStats.queued} queued
                        </span>
                      )}
                      {queueStats.transmitting > 0 && (
                        <span className="text-amber-500 ml-1">
                          {queueStats.transmitting} transmitting
                        </span>
                      )}
                      {queueStats.forwarding > 0 && (
                        <span className="text-purple-500 ml-1">
                          {queueStats.forwarding} forwarding
                        </span>
                      )}
                    </div>
                    
                    {!station.isActive && queueStats.queued > 0 && nextHandoff && (
                      <div className="flex items-center gap-1 text-[9px] font-mono text-secondary">
                        <span>Next hop:</span>
                        <ArrowRight className="w-2.5 h-2.5" />
                        <span className="text-primary">{nextHandoff.name}</span>
                        <span>({nextHandoff.nextPassTime})</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Expanded Bundle Queue Details */}
              {isExpanded && stationQueue.length > 0 && (
                <div className="px-2 pb-2 border-t border-border/50 mt-1 pt-2">
                  <div className="text-[9px] font-semibold tracking-wider uppercase text-secondary mb-2">
                    BUNDLE QUEUE DETAILS
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {stationQueue.map((bundle) => (
                      <div
                        key={bundle.bundle_id}
                        className="flex items-start gap-2 p-1.5 rounded bg-background/50 hover:bg-background/80 transition-colors"
                      >
                        <div
                          className="w-1 h-full rounded-full flex-shrink-0 mt-1"
                          style={{ backgroundColor: getPriorityColor(bundle.priority) }}
                        />
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
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
                            <span className={`text-[9px] font-mono ${
                              bundle.status === "DELIVERED" ? "text-success" :
                              bundle.status === "TRANSMITTING" ? "text-amber-500" :
                              "text-secondary"
                            }`}>
                              {bundle.status}
                            </span>
                          </div>
                          <div className="text-[10px] text-secondary truncate">
                            {bundle.payload}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5 text-[9px] text-secondary">
                            <span>Age: {Math.floor(bundle.age_seconds)}s</span>
                            <span>TTL: {bundle.ttl_hours}h</span>
                            {bundle.forwarded_to && (
                              <span className="text-purple-500">
                                → {bundle.forwarded_to}
                              </span>
                            )}
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
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Network Summary */}
      <div className="mt-3 pt-3 border-t border-border">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-xs font-mono font-semibold text-foreground">
              {Object.values(dtnQueues).reduce((sum, queue) => sum + queue.length, 0)}
            </div>
            <div className="text-[9px] text-secondary uppercase tracking-wide">
              Total Bundles
            </div>
          </div>
          <div>
            <div className="text-xs font-mono font-semibold text-cyan-500">
              {Object.values(dtnQueues).reduce((sum, queue) => 
                sum + queue.filter(b => b.status === "QUEUED").length, 0
              )}
            </div>
            <div className="text-[9px] text-secondary uppercase tracking-wide">
              Queued
            </div>
          </div>
          <div>
            <div className="text-xs font-mono font-semibold text-success">
              {Object.values(dtnQueues).reduce((sum, queue) => 
                sum + queue.filter(b => b.status === "DELIVERED").length, 0
              )}
            </div>
            <div className="text-[9px] text-secondary uppercase tracking-wide">
              Delivered
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default StationNetwork;