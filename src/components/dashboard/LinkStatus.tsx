import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Signal, SignalHigh, SignalLow, SignalZero } from "lucide-react";
import { InfoTooltip } from "@/components/ui/info-tooltip";

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

  // Calculate signal strength percentage
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
  const isApproaching = dopplerShift < 0;
  
  // Doppler shift bar position
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
        <div className="flex items-center gap-2">
          <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary">
            LINK STATUS
          </h3>
          <InfoTooltip
            content={
              <div className="space-y-2">
                <div>
                  <strong>Link Status Overview</strong>
                </div>
                <div className="text-xs space-y-1.5">
                  <p>This panel shows real-time RF communication parameters between the ground station and ISS.</p>
                  <p><strong>Signal Strength:</strong> Received power in dBm. Calculated from transmit power, antenna gains, path loss, and atmospheric attenuation.</p>
                  <p><strong>SNR:</strong> Signal-to-Noise Ratio indicates link quality. Higher values mean better communication reliability.</p>
                  <p><strong>Doppler Shift:</strong> Frequency change due to relative motion. Blue shift (negative) = approaching, Red shift (positive) = receding.</p>
                  <p><strong>Latency:</strong> One-way propagation delay based on distance and speed of light (~3ms per 1000km).</p>
                </div>
              </div>
            }
          />
        </div>
        {linkStatus && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-[13px] font-mono text-success">LIVE</span>
          </div>
        )}
      </div>
      
      {/* Signal Strength with Visual Bars */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <SignalIcon className={`w-4 h-4 ${signalQuality.color}`} />
            <span className="text-[13px] text-secondary">Signal Strength</span>
            <InfoTooltip
              content={
                <div className="space-y-2">
                  <div>
                    <strong>Signal Strength (dBm)</strong>
                  </div>
                  <div className="text-xs space-y-1.5">
                    <p><strong>Calculation:</strong> Received Power = Transmit Power + Antenna Gains - Path Loss - Atmospheric Loss - Cable Loss</p>
                    <p><strong>Path Loss:</strong> FSPL = 20×log₁₀(distance) + 20×log₁₀(frequency) + 32.44</p>
                    <p><strong>Thresholds:</strong></p>
                    <ul className="list-disc list-inside space-y-0.5 ml-2">
                      <li>Excellent: ≥ -60 dBm</li>
                      <li>Good: -75 to -60 dBm</li>
                      <li>Fair: -90 to -75 dBm</li>
                      <li>Weak: -105 to -90 dBm</li>
                      <li>Very Weak: -115 to -105 dBm</li>
                    </ul>
                    <p><strong>Meaning:</strong> Higher (less negative) values indicate stronger received signal. Signal degrades with distance and atmospheric conditions.</p>
                  </div>
                </div>
              }
            />
          </div>
          <div className="text-right">
            <div className={`text-[13px] font-mono font-semibold ${signalQuality.color}`}>
              {signalQuality.level}
            </div>
            <div className="text-[11px] text-secondary">
              {signalStrength.toFixed(1)} dBm
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <Progress value={signalPercent} className="h-2" />
        <div className="flex justify-between text-[11px] text-secondary">
          <span>-120 dBm</span>
          <span>-80 dBm</span>
          <span>-40 dBm</span>
        </div>
      </div>

      {/* Connection State and Latency */}
      <div className="grid grid-cols-2 gap-3 pt-2">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[13px] text-secondary">Connection</span>
            <InfoTooltip
              content={
                <div className="space-y-2">
                  <div>
                    <strong>Connection State</strong>
                  </div>
                  <div className="text-xs space-y-1.5">
                    <p><strong>ACQUIRED:</strong> Strong link established, full communication capability</p>
                    <p><strong>DEGRADED:</strong> Weak link, reduced data rate, higher error probability</p>
                    <p><strong>IDLE:</strong> No active connection, station out of range or below horizon</p>
                    <p><strong>Determined by:</strong> Signal strength threshold (-90 dBm) and SNR (&gt;3 dB minimum)</p>
                  </div>
                </div>
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <div 
              className={`w-2 h-2 rounded-full ${
                connectionState === "ACQUIRED" ? "bg-success animate-pulse" :
                connectionState === "DEGRADED" ? "bg-amber-500 animate-pulse" :
                "bg-secondary"
              }`}
            />
            <span className={`text-[13px] font-mono font-semibold ${getConnectionColor()}`}>
              {connectionState}
            </span>
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[13px] text-secondary">Latency</span>
            <InfoTooltip
              content={
                <div className="space-y-2">
                  <div>
                    <strong>Latency (Propagation Delay)</strong>
                  </div>
                  <div className="text-xs space-y-1.5">
                    <p><strong>Calculation:</strong> Latency = Distance / Speed of Light</p>
                    <p>Speed of Light: 299,792.458 km/s</p>
                    <p><strong>Example:</strong> At 400 km range: ~1.33 ms one-way delay</p>
                    <p><strong>Meaning:</strong> Time for signal to travel from transmitter to receiver. Round-trip latency is double this value. This is the fundamental limit - cannot be reduced.</p>
                    <p><strong>Impact:</strong> Affects real-time communication. For ISS at ~400km altitude, latency is typically 1-3ms, which is negligible for most applications.</p>
                  </div>
                </div>
              }
            />
          </div>
          <div className="text-[13px] font-mono text-right">
            {latency > 0 ? `${latency.toFixed(2)} ms` : '--'}
          </div>
        </div>
      </div>

      {/* Doppler Shift Visualization */}
      <div className="pt-2">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[13px] text-secondary">Doppler Shift</span>
          <InfoTooltip
            content={
              <div className="space-y-2">
                <div>
                  <strong>Doppler Shift</strong>
                </div>
                <div className="text-xs space-y-1.5">
                  <p><strong>Calculation:</strong> Δf = (v_r × f₀) / c</p>
                  <p>Where: v_r = radial velocity, f₀ = carrier frequency, c = speed of light</p>
                  <p><strong>Blue Shift (Negative):</strong> ISS approaching ground station. Frequency increases.</p>
                  <p><strong>Red Shift (Positive):</strong> ISS receding from ground station. Frequency decreases.</p>
                  <p><strong>Maximum:</strong> Occurs at closest approach when radial velocity is highest (~7.66 km/s orbital velocity).</p>
                  <p><strong>Impact:</strong> Requires frequency tracking/compensation in receivers. At 145.8 MHz, max shift is ~±3.8 kHz.</p>
                  <p><strong>Understanding:</strong> The visualization shows the frequency offset. Blue indicates approaching, red indicates receding.</p>
                </div>
              </div>
            }
          />
        </div>
        <div className="text-[13px] font-mono mb-2">
          {dopplerShift > 0 ? '+' : ''}{dopplerShift.toFixed(3)} kHz
        </div>

        {/* Doppler Frequency Spectrum */}
        <div className="relative h-12 bg-background/50 rounded border border-border overflow-hidden">
          <div 
            className="absolute inset-0 opacity-20"
            style={{
              background: 'linear-gradient(90deg, rgba(251,191,36,0.3) 0%, rgba(100,116,139,0.1) 50%, rgba(0,212,255,0.3) 100%)'
            }}
          />

          {/* Scale markings */}
          <div className="absolute inset-0 flex justify-between items-center px-2 text-[10px] text-secondary/60 font-mono">
            <span>-10</span>
            <span>-5</span>
            <span className="text-secondary">0 kHz</span>
            <span>+5</span>
            <span>+10</span>
          </div>

          {/* Center line*/}
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
          <span className={`text-[10px] font-mono ${isApproaching ? 'text-[#00d4ff]' : 'text-[#fbbf24]'}`}>
            {Math.abs(dopplerShift) > 0.01 
              ? (isApproaching ? '← APPROACHING (Blue Shift)' : 'RECEDING → (Red Shift)')
              : 'STATIONARY'}
          </span>
        </div>
      </div>

      {/* SNR Display */}
      <div className="pt-2 border-t border-border">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-1.5">
            <span className="text-[13px] text-secondary">Signal-to-Noise Ratio</span>
            <InfoTooltip
              content={
                <div className="space-y-2">
                  <div>
                    <strong>Signal-to-Noise Ratio (SNR)</strong>
                  </div>
                  <div className="text-xs space-y-1.5">
                    <p><strong>Calculation:</strong> SNR (dB) = Received Power (dBm) - Noise Floor (dBm)</p>
                    <p><strong>Noise Floor:</strong> k×T×B where k=Boltzmann constant, T=system temperature (125K), B=bandwidth (12.5 kHz)</p>
                    <p><strong>Thresholds:</strong></p>
                    <ul className="list-disc list-inside space-y-0.5 ml-2">
                      <li>Excellent: &gt;10 dB (very low error rate)</li>
                      <li>Good: 6-10 dB (low error rate)</li>
                      <li>Marginal: 3-6 dB (moderate errors, may need retransmission)</li>
                      <li>Unusable: &lt;3 dB (high error rate, link unreliable)</li>
                    </ul>
                    <p><strong>Data Rate:</strong> Uses Shannon-Hartley: C = B × log₂(1 + SNR). Higher SNR enables higher data rates.</p>
                    <p><strong>Meaning:</strong> Measures how much stronger the signal is compared to background noise. Critical for determining link quality and achievable data rate.</p>
                  </div>
                </div>
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <div 
              className={`w-2 h-2 rounded-full ${
                snr > 10 ? 'bg-success' : 
                snr > 3 ? 'bg-amber-500' : 
                'bg-destructive'
              }`}
            />
            <span className={`text-[13px] font-mono font-semibold ${
              snr > 10 ? 'text-success' : 
              snr > 3 ? 'text-amber-500' : 
              'text-destructive'
            }`}>
              {snr.toFixed(1)} dB
            </span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-secondary">
          {snr > 10 ? 'Excellent link quality' : 
           snr > 3 ? 'Marginal link quality' : 
           'Link unusable'}
        </div>
      </div>
    </Card>
  );
};

export default LinkStatus;