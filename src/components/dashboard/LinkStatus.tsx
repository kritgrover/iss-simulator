import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Signal, SignalHigh, SignalLow, SignalZero } from "lucide-react";

interface LinkStatusProps {
  linkStatus?: {
    signal_strength_dbm: number;
    connection_state: "ACQUIRED" | "DEGRADED" | "IDLE";
    latency_ms: number;
    doppler_shift_khz: number;
    snr_db: number;
    range_km: number;
  } | null;
}

const LinkStatus = ({ linkStatus }: LinkStatusProps) => {
  // Default values if no data
  const signalStrength = linkStatus?.signal_strength_dbm ?? -120;
  const connectionState = linkStatus?.connection_state ?? "IDLE";
  const latency = linkStatus?.latency_ms ?? 0;
  const dopplerShift = linkStatus?.doppler_shift_khz ?? 0;
  const snr = linkStatus?.snr_db ?? -50;

  // Calculate signal strength percentage (scale: -120 dBm to -40 dBm)
  const signalPercent = Math.max(0, Math.min(100, ((signalStrength + 120) / 80) * 100));

  // Signal quality assessment
  const getSignalQuality = () => {
    if (signalStrength >= -60) return { level: "Excellent", color: "text-success", icon: SignalHigh, bars: 5 };
    if (signalStrength >= -75) return { level: "Good", color: "text-success", icon: SignalHigh, bars: 4 };
    if (signalStrength >= -90) return { level: "Fair", color: "text-amber-500", icon: Signal, bars: 3 };
    if (signalStrength >= -105) return { level: "Weak", color: "text-amber-500", icon: SignalLow, bars: 2 };
    if (signalStrength >= -115) return { level: "Very Weak", color: "text-destructive", icon: SignalZero, bars: 1 };
    return { level: "No Signal", color: "text-secondary", icon: SignalZero, bars: 0 };
  };

  const signalQuality = getSignalQuality();
  const SignalIcon = signalQuality.icon;

  // Determine if approaching or receding
  const isApproaching = dopplerShift < 0;
  
  // Doppler shift bar position (scale: -10 kHz to +10 kHz)
  const dopplerPercent = Math.max(0, Math.min(100, ((dopplerShift + 10) / 20) * 100));

  // Connection state colors
  const getConnectionColor = () => {
    switch (connectionState) {
      case "ACQUIRED": return "text-success";
      case "DEGRADED": return "text-amber-500";
      case "IDLE": return "text-secondary";
      default: return "text-secondary";
    }
  };

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
          LINK STATUS
        </h3>
        {linkStatus && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-mono text-success">LIVE</span>
          </div>
        )}
      </div>
      
      {/* Signal Strength with Visual Bars */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <SignalIcon className={`w-4 h-4 ${signalQuality.color}`} />
            <span className="text-xs text-secondary">Signal Strength</span>
          </div>
          <div className="text-right">
            <div className={`text-xs font-mono font-semibold ${signalQuality.color}`}>
              {signalQuality.level}
            </div>
            <div className="text-[10px] text-secondary">
              {signalStrength.toFixed(1)} dBm
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <Progress value={signalPercent} className="h-2" />
        <div className="flex justify-between text-[10px] text-secondary">
          <span>-120 dBm</span>
          <span>-80 dBm</span>
          <span>-40 dBm</span>
        </div>
      </div>

      {/* Connection State and Latency */}
      <div className="grid grid-cols-2 gap-3 pt-2">
        <div>
          <div className="text-xs text-secondary mb-1">Connection</div>
          <div className="flex items-center gap-2">
            <div 
              className={`w-2 h-2 rounded-full ${
                connectionState === "ACQUIRED" ? "bg-success animate-pulse" :
                connectionState === "DEGRADED" ? "bg-amber-500 animate-pulse" :
                "bg-secondary"
              }`}
            />
            <span className={`text-xs font-mono font-semibold ${getConnectionColor()}`}>
              {connectionState}
            </span>
          </div>
        </div>
        <div>
          <div className="text-xs text-secondary mb-1">Latency</div>
          <div className="text-xs font-mono text-right">
            {latency > 0 ? `${latency.toFixed(2)} ms` : '--'}
          </div>
        </div>
      </div>

      {/* Doppler Shift Visualization */}
      <div className="pt-2">
        <div className="text-xs text-secondary mb-1">Doppler Shift</div>
        <div className="text-xs font-mono mb-2">
          {dopplerShift > 0 ? '+' : ''}{dopplerShift.toFixed(3)} kHz
        </div>

        {/* Doppler Frequency Spectrum */}
        <div className="relative h-12 bg-background/50 rounded border border-border overflow-hidden">
          {/* Background gradient */}
          <div 
            className="absolute inset-0 opacity-20"
            style={{
              background: 'linear-gradient(90deg, rgba(251,191,36,0.3) 0%, rgba(100,116,139,0.1) 50%, rgba(0,212,255,0.3) 100%)'
            }}
          />

          {/* Scale markings */}
          <div className="absolute inset-0 flex justify-between items-center px-2 text-[9px] text-secondary/60 font-mono">
            <span>-10</span>
            <span>-5</span>
            <span className="text-secondary">0 kHz</span>
            <span>+5</span>
            <span>+10</span>
          </div>

          {/* Center line (0 Hz reference) */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-secondary/30" />

          {/* Doppler indicator bar */}
          {Math.abs(dopplerShift) > 0.01 && (
            <div 
              className="absolute top-1/2 -translate-y-1/2 h-8 w-1 rounded-full transition-all duration-300 shadow-lg"
              style={{
                left: `${dopplerPercent}%`,
                backgroundColor: isApproaching ? '#00d4ff' : '#fbbf24',
                boxShadow: `0 0 10px ${isApproaching ? '#00d4ff' : '#fbbf24'}`,
              }}
            >
              {/* Indicator glow */}
              <div 
                className="absolute inset-0 rounded-full blur-sm animate-pulse"
                style={{
                  backgroundColor: isApproaching ? '#00d4ff' : '#fbbf24',
                }}
              />
            </div>
          )}

          {/* Waveform pattern */}
          <svg className="absolute inset-0 w-full h-full opacity-30 pointer-events-none">
            <path
              d={`M 0,24 ${Array.from({ length: 50 }, (_, i) => {
                const x = (i / 49) * 100;
                const freq = 0.2 + Math.abs(50 - x) * 0.02;
                const y = 24 + Math.sin(i * freq) * 8;
                return `L ${x},${y}`;
              }).join(' ')}`}
              fill="none"
              stroke={isApproaching ? '#00d4ff' : '#fbbf24'}
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        </div>

        {/* Direction indicator */}
        <div className="flex justify-center mt-1">
          <span className={`text-[9px] font-mono ${isApproaching ? 'text-[#00d4ff]' : 'text-[#fbbf24]'}`}>
            {Math.abs(dopplerShift) > 0.01 
              ? (isApproaching ? '← APPROACHING (Blue Shift)' : 'RECEDING → (Red Shift)')
              : 'STATIONARY'}
          </span>
        </div>
      </div>

      {/* SNR Display */}
      <div className="pt-2 border-t border-border">
        <div className="flex justify-between items-center">
          <span className="text-xs text-secondary">Signal-to-Noise Ratio</span>
          <div className="flex items-center gap-2">
            <div 
              className={`w-2 h-2 rounded-full ${
                snr > 10 ? 'bg-success' : 
                snr > 3 ? 'bg-amber-500' : 
                'bg-destructive'
              }`}
            />
            <span className={`text-xs font-mono font-semibold ${
              snr > 10 ? 'text-success' : 
              snr > 3 ? 'text-amber-500' : 
              'text-destructive'
            }`}>
              {snr.toFixed(1)} dB
            </span>
          </div>
        </div>
        <div className="mt-1 text-[10px] text-secondary">
          {snr > 10 ? 'Excellent link quality' : 
           snr > 3 ? 'Marginal link quality' : 
           'Link unusable'}
        </div>
      </div>
    </Card>
  );
};

export default LinkStatus;