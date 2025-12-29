import { Card } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";

interface PassPredictionProps {
  handoffCount?: number;
  stationsUsed?: number;
}

const PassPrediction = ({ handoffCount = 0, stationsUsed = 1 }: PassPredictionProps) => {
  const passes = [
    { startTime: "15:42:18", duration: "09:24", elevation: "78.2°", active: true },
    { startTime: "17:18:45", duration: "08:56", elevation: "65.4°", active: false },
    { startTime: "18:54:32", duration: "07:12", elevation: "52.8°", active: false },
    { startTime: "20:31:08", duration: "06:48", elevation: "48.3°", active: false },
  ];

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
          PASS PREDICTION
        </h3>
        <InfoTooltip
          content={
            <div className="space-y-2">
              <div>
                <strong>Pass Prediction</strong>
              </div>
              <div className="text-xs space-y-1.5">
                <p>Shows upcoming ISS passes over the ground station network.</p>
                <p><strong>Pass Calculation:</strong> Based on TLE (Two-Line Element) orbital data and station coordinates.</p>
                <p><strong>Start Time:</strong> AOS (Acquisition of Signal) - when ISS rises above horizon (elevation > 0°)</p>
                <p><strong>Duration:</strong> Time from AOS to LOS (Loss of Signal) - when ISS sets below horizon</p>
                <p><strong>Max Elevation:</strong> Highest point of pass. Higher elevation = shorter distance = better signal quality</p>
                <p><strong>Statistics:</strong></p>
                <ul className="list-disc list-inside space-y-0.5 ml-2">
                  <li>Total Handoffs: Number of station transitions during passes</li>
                  <li>Stations Used: Count of unique stations that had contact</li>
                  <li>Success Rate: Percentage of packets successfully delivered</li>
                </ul>
                <p><strong>Understanding:</strong> Passes typically last 5-10 minutes. Multiple stations provide continuous coverage as ISS orbits.</p>
              </div>
            </div>
          }
        />
      </div>
      
      <div className="space-y-1">
        <div className="grid grid-cols-3 gap-2 pb-2 border-b border-border text-[10px] text-secondary uppercase">
          <span>Start Time</span>
          <span>Duration</span>
          <span className="text-right">Max Elev</span>
        </div>
        
        {passes.map((pass, idx) => (
          <div 
            key={idx} 
            className={`grid grid-cols-3 gap-2 py-1.5 text-xs font-mono ${
              pass.active ? 'bg-primary/10' : ''
            }`}
          >
            <span>{pass.startTime}</span>
            <span>{pass.duration}</span>
            <span className="text-right">{pass.elevation}</span>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t border-border space-y-1">
        <h4 className="text-[10px] font-semibold tracking-wider uppercase text-secondary mb-2">
          STATISTICS
        </h4>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Total Handoffs</span>
          <span className="font-mono text-amber-500">{handoffCount}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Stations Used</span>
          <span className="font-mono">{stationsUsed}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Packets Sent</span>
          <span className="font-mono">2,847</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Packets Received</span>
          <span className="font-mono">2,821</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Success Rate</span>
          <span className="font-mono text-success">99.1%</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Avg Latency</span>
          <span className="font-mono">145.2 ms</span>
        </div>
      </div>
    </Card>
  );
};

export default PassPrediction;
