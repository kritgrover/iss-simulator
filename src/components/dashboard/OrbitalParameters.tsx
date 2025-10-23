import { Card } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { Satellite } from "lucide-react";

interface OrbitalParametersProps {
  orbitalData?: {
    orbital_parameters: {
      active_station: string;
      latitude: number;
      longitude: number;
      altitude_km: number;
      velocity_kmps: number;
      azimuth: number;
      elevation: number;
      range_km: number;
      next_pass_time: string | null;
      next_pass_minutes: number;
      aos_time: string | null;
      los_time: string | null;
      pass_duration_minutes: number;
      is_in_pass: boolean;
    } | null;
    timestamp: string;
  } | null;
}

const OrbitalParameters = ({ orbitalData }: OrbitalParametersProps) => {
  const [currentPassTime, setCurrentPassTime] = useState("--:--:--");
  const [nextPassTime, setNextPassTime] = useState("--:--:--");

  const params = orbitalData?.orbital_parameters;

  // Update countdown timers
  useEffect(() => {
    const interval = setInterval(() => {
      if (params?.los_time && params.is_in_pass) {
        const now = new Date();
        const los = new Date(params.los_time);
        const diff = los.getTime() - now.getTime();
        
        if (diff > 0) {
          const minutes = Math.floor(diff / 60000);
          const seconds = Math.floor((diff % 60000) / 1000);
          setCurrentPassTime(`${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);
        } else {
          setCurrentPassTime("00:00");
        }
      } else {
        setCurrentPassTime("--:--:--");
      }

      if (params?.next_pass_time && params.next_pass_minutes > 0) {
        const hours = Math.floor(params.next_pass_minutes / 60);
        const minutes = params.next_pass_minutes % 60;
        setNextPassTime(`${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:00`);
      } else {
        setNextPassTime("--:--:--");
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [params]);

  // Determine elevation color
  const getElevationColor = (elevation: number) => {
    if (elevation > 10) return "text-success";
    if (elevation > 0) return "text-amber-500";
    return "text-secondary";
  };

  // Check if ISS is overhead
  const isOverhead = params ? params.elevation > 45 : false;

  const parameters = [
    { 
      label: "Latitude", 
      value: params ? `${params.latitude.toFixed(4)}°${params.latitude >= 0 ? 'N' : 'S'}` : "--°",
      color: "text-foreground"
    },
    { 
      label: "Longitude", 
      value: params ? `${Math.abs(params.longitude).toFixed(4)}°${params.longitude >= 0 ? 'E' : 'W'}` : "--°",
      color: "text-foreground"
    },
    { 
      label: "Altitude", 
      value: params ? `${params.altitude_km.toFixed(1)} km` : "-- km",
      color: "text-primary"
    },
    { 
      label: "Velocity", 
      value: params ? `${params.velocity_kmps.toFixed(2)} km/s` : "-- km/s",
      color: "text-primary"
    },
    { 
      label: "Azimuth", 
      value: params ? `${params.azimuth.toFixed(1)}°` : "--°",
      color: "text-foreground"
    },
    { 
      label: "Elevation", 
      value: params ? `${params.elevation.toFixed(1)}°` : "--°",
      color: params ? getElevationColor(params.elevation) : "text-secondary"
    },
  ];

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">
          ORBITAL PARAMETERS
        </h3>
        {orbitalData && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-mono text-success">LIVE</span>
          </div>
        )}
      </div>
      
      <div className="mb-3 pb-2 border-b border-border">
        <div className="flex justify-between items-center">
          <span className="text-xs text-secondary">Active Station</span>
          <span className="text-xs font-mono text-primary">
            {params?.active_station || "No Station"}
          </span>
        </div>
      </div>

      {/* Overhead indicator */}
      {isOverhead && params?.is_in_pass && (
        <div className="mb-3 p-2 bg-success/20 border border-success/50 rounded flex items-center gap-2">
          <Satellite className="w-4 h-4 text-success animate-pulse" />
          <span className="text-xs font-mono font-semibold text-success">
            ISS OVERHEAD
          </span>
        </div>
      )}
      
      <div className="space-y-2">
        {parameters.map((param) => (
          <div key={param.label} className="flex justify-between items-center py-1">
            <span className="text-xs text-secondary">{param.label}</span>
            <span className={`text-xs font-mono text-right ${param.color}`}>
              {param.value}
            </span>
          </div>
        ))}
      </div>

      <div className="pt-3 mt-3 border-t border-border space-y-1">
        {params?.is_in_pass ? (
          <>
            <div className="flex justify-between text-xs">
              <span className="text-secondary">Current Pass</span>
              <span className="font-mono text-success">{currentPassTime}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-secondary">Duration</span>
              <span className="font-mono">{params.pass_duration_minutes} min</span>
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between text-xs">
              <span className="text-secondary">Next Pass</span>
              <span className="font-mono text-amber-500">{nextPassTime}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-secondary">Status</span>
              <span className="font-mono text-secondary">WAITING</span>
            </div>
          </>
        )}
      </div>

      {/* Range indicator */}
      {params && params.is_in_pass && (
        <div className="pt-2 mt-2 border-t border-border">
          <div className="flex justify-between text-xs">
            <span className="text-secondary">Range</span>
            <span className="font-mono text-primary">{params.range_km.toFixed(1)} km</span>
          </div>
        </div>
      )}
    </Card>
  );
};

export default OrbitalParameters;