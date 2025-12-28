import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useISSMessages } from "@/hooks/useISSMessages";
import { Activity, MessageSquare, Radio, TrendingUp } from "lucide-react";

interface ISSDashboardProps {
  orbitalData?: {
    iss_position: {
      altitude_km: number;
      velocity_kmps: number;
    };
    stations: Array<{
      id: string;
      name: string;
      is_visible: boolean;
      next_pass_minutes: number;
    }>;
    link_status?: {
      connection_state: "ACQUIRED" | "DEGRADED" | "IDLE";
      snr_db: number;
      data_rate_kbps?: number;
    } | null;
  } | null;
}

const ISSDashboard = ({ orbitalData }: ISSDashboardProps) => {
  const { messages } = useISSMessages();

  const visibleStations = orbitalData?.stations?.filter(s => s.is_visible) || [];
  const nextStation = orbitalData?.stations
    ?.filter(s => !s.is_visible && s.next_pass_minutes > 0)
    .sort((a, b) => a.next_pass_minutes - b.next_pass_minutes)[0];

  const completedMessages = messages.filter(m => m.is_complete).length;
  const pendingMessages = messages.filter(m => !m.is_complete).length;

  return (
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
          <Activity className="w-3 h-3" />
          ISS DASHBOARD
        </h3>
      </div>
      <div className="space-y-4">
        {/* Orbital Parameters */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary">Orbital Parameters</div>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-[10px] text-secondary mb-1">Altitude</div>
              <div className="text-[13px] font-mono text-primary">
                {orbitalData?.iss_position?.altitude_km.toFixed(1) || "N/A"} km
              </div>
            </div>
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-[10px] text-secondary mb-1">Velocity</div>
              <div className="text-[13px] font-mono text-primary">
                {orbitalData?.iss_position?.velocity_kmps.toFixed(3) || "N/A"} km/s
              </div>
            </div>
          </div>
        </div>

        {/* Link Status */}
        {orbitalData?.link_status && (
          <div className="space-y-2">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary">Link Status</div>
            <div className="space-y-1">
              <div className="flex justify-between text-[11px]">
                <span className="text-secondary">State:</span>
                <span className={`font-mono ${
                  orbitalData.link_status.connection_state === "ACQUIRED" ? "text-success" :
                  orbitalData.link_status.connection_state === "DEGRADED" ? "text-amber-500" :
                  "text-secondary"
                }`}>
                  {orbitalData.link_status.connection_state}
                </span>
              </div>
              {orbitalData.link_status.data_rate_kbps !== undefined && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-secondary">Data Rate:</span>
                  <span className="font-mono text-primary">
                    {orbitalData.link_status.data_rate_kbps.toFixed(1)} kbps
                  </span>
                </div>
              )}
              <div className="flex justify-between text-[11px]">
                <span className="text-secondary">SNR:</span>
                <span className="font-mono text-primary">
                  {orbitalData.link_status.snr_db.toFixed(1)} dB
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Visible Stations */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
            <Radio className="w-3 h-3" />
            Visible Stations
          </div>
          {visibleStations.length > 0 ? (
            <div className="space-y-1">
              {visibleStations.map(station => (
                <div key={station.id} className="text-[11px] p-2 bg-success/10 rounded border border-success/50">
                  <div className="font-mono font-semibold text-success">{station.name.toUpperCase()}</div>
                  <div className="text-[10px] text-secondary">In contact</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-secondary p-2 bg-background/50 rounded border border-border">
              No stations currently visible
            </div>
          )}
        </div>

        {/* Next Contact */}
        {nextStation && (
          <div className="space-y-2">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary">Next Contact</div>
            <div className="text-[11px] p-2 bg-background/50 rounded border border-border">
              <div className="font-mono font-semibold">{nextStation.name.toUpperCase()}</div>
              <div className="text-[10px] text-secondary">
                In {nextStation.next_pass_minutes.toFixed(0)} minutes
              </div>
            </div>
          </div>
        )}

        {/* Message Statistics */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
            <MessageSquare className="w-3 h-3" />
            Messages
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-[10px] text-secondary mb-1">Received</div>
              <div className="text-[13px] font-mono text-primary">
                {messages.length}
              </div>
            </div>
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-[10px] text-secondary mb-1">Complete</div>
              <div className="text-[13px] font-mono text-success">
                {completedMessages}
              </div>
            </div>
          </div>
          {pendingMessages > 0 && (
            <div className="text-[11px] text-amber-500 p-2 bg-amber-500/10 rounded border border-amber-500/50">
              {pendingMessages} message{pendingMessages !== 1 ? 's' : ''} pending reassembly
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

export default ISSDashboard;

