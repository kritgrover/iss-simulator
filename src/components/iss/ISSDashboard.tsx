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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-4 h-4" />
          ISS Dashboard
        </CardTitle>
        <CardDescription>
          Operational status and metrics
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Orbital Parameters */}
        <div className="space-y-2">
          <div className="text-sm font-semibold">Orbital Parameters</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-secondary">Altitude</div>
              <div className="font-mono text-primary">
                {orbitalData?.iss_position?.altitude_km.toFixed(1) || "N/A"} km
              </div>
            </div>
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-secondary">Velocity</div>
              <div className="font-mono text-primary">
                {orbitalData?.iss_position?.velocity_kmps.toFixed(3) || "N/A"} km/s
              </div>
            </div>
          </div>
        </div>

        {/* Link Status */}
        {orbitalData?.link_status && (
          <div className="space-y-2">
            <div className="text-sm font-semibold">Link Status</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
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
                <div className="flex justify-between">
                  <span className="text-secondary">Data Rate:</span>
                  <span className="font-mono text-primary">
                    {orbitalData.link_status.data_rate_kbps.toFixed(1)} kbps
                  </span>
                </div>
              )}
              <div className="flex justify-between">
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
          <div className="text-sm font-semibold flex items-center gap-2">
            <Radio className="w-3 h-3" />
            Visible Stations
          </div>
          {visibleStations.length > 0 ? (
            <div className="space-y-1">
              {visibleStations.map(station => (
                <div key={station.id} className="text-xs p-2 bg-success/10 rounded border border-success/50">
                  <div className="font-semibold text-success">{station.name}</div>
                  <div className="text-secondary">In contact</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-secondary p-2 bg-background/50 rounded border border-border">
              No stations currently visible
            </div>
          )}
        </div>

        {/* Next Contact */}
        {nextStation && (
          <div className="space-y-2">
            <div className="text-sm font-semibold">Next Contact</div>
            <div className="text-xs p-2 bg-background/50 rounded border border-border">
              <div className="font-semibold">{nextStation.name}</div>
              <div className="text-secondary">
                In {nextStation.next_pass_minutes.toFixed(0)} minutes
              </div>
            </div>
          </div>
        )}

        {/* Message Statistics */}
        <div className="space-y-2">
          <div className="text-sm font-semibold flex items-center gap-2">
            <MessageSquare className="w-3 h-3" />
            Messages
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-secondary">Received</div>
              <div className="font-mono text-primary text-lg">
                {messages.length}
              </div>
            </div>
            <div className="p-2 bg-background/50 rounded border border-border">
              <div className="text-secondary">Complete</div>
              <div className="font-mono text-success text-lg">
                {completedMessages}
              </div>
            </div>
          </div>
          {pendingMessages > 0 && (
            <div className="text-xs text-amber-500 p-2 bg-amber-500/10 rounded border border-amber-500/50">
              {pendingMessages} message{pendingMessages !== 1 ? 's' : ''} pending reassembly
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default ISSDashboard;

