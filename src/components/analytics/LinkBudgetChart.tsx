import { Card } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, ReferenceLine } from "recharts";
import { useEffect, useState } from "react";
import { InfoTooltip } from "@/components/ui/info-tooltip";

interface LinkBudgetChartProps {
  linkBudgetHistory?: Array<{
    timestamp: string;
    snr_db: number;
    signal_strength_dbm: number;
  }>;
  currentSNR?: number;
}

const LinkBudgetChart = ({ linkBudgetHistory, currentSNR }: LinkBudgetChartProps) => {
  const [chartData, setChartData] = useState<Array<{time: string, snr: number}>>([]);

  useEffect(() => {
    if (linkBudgetHistory && linkBudgetHistory.length > 0) {
      // Convert history to chart format (last 60 data points for 1 minute view)
      const data = linkBudgetHistory.slice(-60).map((point, index) => {
        const timestamp = new Date(point.timestamp);
        const seconds = timestamp.getSeconds();
        return {
          time: `${seconds}s`,
          snr: point.snr_db
        };
      });
      setChartData(data);
    } else {
      // Default empty data
      setChartData(Array.from({ length: 60 }, (_, i) => ({
        time: `${i}s`,
        snr: -50
      })));
    }
  }, [linkBudgetHistory]);

  const hasData = linkBudgetHistory && linkBudgetHistory.length > 0;

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
            LINK BUDGET
          </h3>
          <InfoTooltip
            content={
              <div className="space-y-2">
                <div>
                  <strong>Link Budget Analysis</strong>
                </div>
                <div className="text-xs space-y-1.5">
                  <p>This chart shows Signal-to-Noise Ratio (SNR) over time, which is the key metric for link quality.</p>
                  <p><strong>Link Budget Formula:</strong></p>
                  <p className="font-mono text-[10px] bg-muted p-1 rounded">
                    SNR = P_tx + G_tx + G_rx - FSPL - L_atm - L_cable - N_floor
                  </p>
                  <p><strong>Components:</strong></p>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>P_tx: Transmit power (43 dBm for ISS)</li>
                    <li>G_tx, G_rx: Antenna gains (12 dBi ISS, 18 dBi ground)</li>
                    <li>FSPL: Free space path loss (depends on distance & frequency)</li>
                    <li>L_atm: Atmospheric attenuation (depends on elevation angle)</li>
                    <li>N_floor: System noise floor (~-139 dBm)</li>
                  </ul>
                  <p><strong>Reference Lines:</strong> Green (10 dB) = excellent, Yellow (3 dB) = minimum viable</p>
                  <p><strong>Understanding:</strong> Higher SNR means better link quality and higher achievable data rates. SNR varies with distance and elevation during the pass.</p>
                </div>
              </div>
            }
          />
        </div>
        {hasData && currentSNR !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-secondary">Current SNR:</span>
            <span className={`text-xs font-mono font-semibold ${
              currentSNR > 10 ? 'text-success' : 
              currentSNR > 3 ? 'text-amber-500' : 
              'text-destructive'
            }`}>
              {currentSNR.toFixed(1)} dB
            </span>
          </div>
        )}
      </div>
      
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted))" />
          <XAxis 
            dataKey="time" 
            tick={{ fill: 'hsl(var(--secondary))', fontSize: 10 }}
            stroke="hsl(var(--muted))"
            interval={9}
          />
          <YAxis 
            label={{ 
              value: 'SNR (dB)', 
              angle: -90, 
              position: 'insideLeft', 
              style: { fill: 'hsl(var(--secondary))', fontSize: 10 } 
            }}
            tick={{ fill: 'hsl(var(--secondary))', fontSize: 10 }}
            stroke="hsl(var(--muted))"
            domain={[-60, 30]}
          />
          {/* Reference lines for quality thresholds */}
          <ReferenceLine 
            y={10} 
            stroke="#22c55e" 
            strokeDasharray="3 3" 
            label={{ value: 'Good', position: 'right', fontSize: 9, fill: '#22c55e' }}
          />
          <ReferenceLine 
            y={3} 
            stroke="#f59e0b" 
            strokeDasharray="3 3" 
            label={{ value: 'Min', position: 'right', fontSize: 9, fill: '#f59e0b' }}
          />
          <Line 
            type="monotone" 
            dataKey="snr" 
            stroke="hsl(var(--primary))" 
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>

      {!hasData && (
        <div className="text-center py-4">
          <p className="text-xs text-secondary">Waiting for link data...</p>
        </div>
      )}
    </Card>
  );
};

export default LinkBudgetChart;