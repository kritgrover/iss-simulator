import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ArrowRight, Loader2 } from "lucide-react";

interface ActiveTransmission {
  bundle_id_short: string;
  from_station: string;
  to_station: string;
  progress_percent: number;
  bytes_transmitted: number;
  size_bytes: number;
  data_rate_kbps: number;
  time_remaining_sec: number;
}

interface TransmissionMonitorProps {
  activeTransmissions: ActiveTransmission[];
}

const TransmissionMonitor = ({ activeTransmissions }: TransmissionMonitorProps) => {
  if (activeTransmissions.length === 0) {
    return null; // Don't show if no active transmissions
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
          ACTIVE TRANSMISSIONS
        </h3>
        <div className="flex items-center gap-1">
          <Loader2 className="w-3 h-3 text-amber-500 animate-spin" />
          <span className="text-xs font-mono text-amber-500">
            {activeTransmissions.length} IN PROGRESS
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {activeTransmissions.map((tx) => (
          <div key={tx.bundle_id_short} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-foreground font-semibold">
                  {tx.bundle_id_short}
                </span>
                <ArrowRight className="w-3 h-3 text-secondary" />
                <span className="text-xs font-mono text-secondary uppercase">
                  {tx.from_station} → {tx.to_station}
                </span>
              </div>
              <span className="text-xs font-mono text-amber-500 font-semibold">
                {tx.progress_percent.toFixed(0)}%
              </span>
            </div>

            <Progress value={tx.progress_percent} className="h-2" />

            <div className="grid grid-cols-3 gap-2 text-[10px] text-secondary">
              <div>
                <span className="text-secondary/60">Size:</span> {(tx.size_bytes / 1024).toFixed(1)} KB
              </div>
              <div>
                <span className="text-secondary/60">Rate:</span> {tx.data_rate_kbps.toFixed(1)} kbps
              </div>
              <div>
                <span className="text-secondary/60">ETA:</span> {tx.time_remaining_sec.toFixed(0)}s
              </div>
            </div>

            <div className="text-[9px] text-secondary/80">
              Transmitted: {(tx.bytes_transmitted / 1024).toFixed(1)} KB / {(tx.size_bytes / 1024).toFixed(1)} KB
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

export default TransmissionMonitor;