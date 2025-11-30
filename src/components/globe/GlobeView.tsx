import { useState, useEffect } from "react";
import { GroundStation } from "@/types/groundStation";
import Globe3D from "./Globe3D";

interface GlobeViewProps {
  stations: GroundStation[];
  activeStationId: string;
  orbitalData?: {
    iss_position: {
      latitude: number;
      longitude: number;
      altitude_km: number;
      velocity_kmps: number;
    };
    orbital_path: Array<{ lat: number; lon: number; alt: number }>;
    stations: Array<{
      id: string;
      name: string;
      lat: number;
      lon: number;
      look_angles: {
        azimuth: number;
        elevation: number;
        range_km: number;
        is_visible: boolean;
      };
      is_visible: boolean;
      next_pass_minutes: number;
      next_pass_time: string | null;
    }>;
    active_station_id: string | null;
    visible_stations_count: number;
    timestamp: string;
  } | null;
}

const GlobeView = ({
  stations,
  activeStationId,
  orbitalData
}: GlobeViewProps) => {
  const [handoffInProgress, setHandoffInProgress] = useState(false);
  const [prevActiveStation, setPrevActiveStation] = useState(activeStationId);

  // Detect handoff
  useEffect(() => {
    if (activeStationId !== prevActiveStation && prevActiveStation) {
      setHandoffInProgress(true);
      console.log(`🔄 Handoff visual: ${prevActiveStation} → ${activeStationId}`);

      setTimeout(() => {
        setHandoffInProgress(false);
        setPrevActiveStation(activeStationId);
      }, 1500);
    } else if (!prevActiveStation) {
      setPrevActiveStation(activeStationId);
    }
  }, [activeStationId, prevActiveStation]);

  // Prepare data for 3D Globe
  const issPosition = orbitalData?.iss_position || {
    latitude: 0,
    longitude: 0,
    altitude_km: 408,
    velocity_kmps: 7.66,
  };

  const groundStationsWithVisibility = orbitalData?.stations
    ? orbitalData.stations.map((stationData) => {
        const station = stations.find((s) => s.id === stationData.id);
        return {
          id: stationData.id,
          name: stationData.name,
          lat: stationData.lat,
          lon: stationData.lon,
          color: station?.color || '#888888',
          is_visible: stationData.is_visible,
        };
      })
    : stations.map((station) => ({
        id: station.id,
        name: station.name,
        lat: station.lat,
        lon: station.lon,
        color: station.color,
        is_visible: false,
      }));

  const activeStation = stations.find(s => s.id === activeStationId);
  const activeStationData = orbitalData?.stations?.find(s => s.id === activeStationId);
  const issInCone = activeStationData?.is_visible ?? false;

  // Count how many stations are currently tracking
  const trackingStationsCount = orbitalData?.stations?.filter(s => s.is_visible).length ?? 0;

  return (
    <div className="h-full w-full flex items-center justify-center relative bg-[#0a0e1a]">
      {/* Tracking Status Overlay */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-3">
        {trackingStationsCount > 0 && (
          <div className="flex items-center gap-2 bg-success/20 rounded px-2 py-1 backdrop-blur-sm border border-success/30">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-mono text-success">
              {trackingStationsCount} STATION{trackingStationsCount > 1 ? 'S' : ''} TRACKING
            </span>
          </div>
        )}
        {orbitalData && (
          <div className="flex items-center gap-2 bg-success/20 rounded px-2 py-1 backdrop-blur-sm border border-success/30">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-mono text-success">LIVE</span>
          </div>
        )}
      </div>
      
      <div className="flex-1 flex items-center justify-center relative w-full h-full">
        {/* 3D Globe */}
        <div className="w-full h-full">
          <Globe3D
            issPosition={issPosition}
            groundStations={groundStationsWithVisibility}
            orbitalPath={orbitalData?.orbital_path}
          />
        </div>

        {/* Legend and Controls Info - Glassmorphism */}
        <div className="absolute top-4 left-4 space-y-2 z-10 animate-in fade-in duration-500">
          <div
            className="px-3 py-2 rounded-lg space-y-2 transition-all duration-300 hover:scale-105"
            style={{
              background: 'rgba(0, 0, 0, 0.3)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
            }}
          >
            <div className="text-[10px] text-secondary/80 mb-2">
              🖱️ Click + Drag to rotate • Scroll to zoom
            </div>
            <div className="flex items-center gap-2 text-xs font-mono transition-transform hover:translate-x-1">
              <div className="w-3 h-3 rounded-full bg-blue-500 shadow-lg shadow-blue-500/50" />
              <span className="text-secondary">Earth</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono transition-transform hover:translate-x-1">
              <div className="w-3 h-3 rounded-full bg-green-500 shadow-lg shadow-green-500/50 animate-pulse" />
              <span className="text-secondary">ISS</span>
            </div>
            {activeStation && (
              <div className="flex items-center gap-2 text-xs font-mono transition-transform hover:translate-x-1">
                <div
                  className="w-3 h-3 rounded-full animate-pulse"
                  style={{
                    backgroundColor: activeStation.color,
                    boxShadow: `0 0 10px ${activeStation.color}80`
                  }}
                />
                <span className="text-secondary">{activeStation.name}</span>
              </div>
            )}
          </div>
        </div>


        {/* Link Acquired Banner */}
        {issInCone && activeStation && !handoffInProgress && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2">
            <div 
              className="flex items-center gap-3 rounded-full px-6 py-2 border-2 shadow-lg"
              style={{
                backgroundColor: `${activeStation.color}20`,
                borderColor: activeStation.color,
                boxShadow: `0 0 20px ${activeStation.color}60`
              }}
            >
              <div 
                className="w-3 h-3 rounded-full animate-pulse"
                style={{ backgroundColor: activeStation.color }}
              />
              <span 
                className="text-sm font-mono font-bold uppercase tracking-wide" 
                style={{ color: activeStation.color }}
              >
                Link Acquired
              </span>
            </div>
          </div>
        )}

        {/* Handoff Banner */}
        {handoffInProgress && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50">
            <div className="bg-amber-500/90 border-4 border-amber-400 rounded-xl px-8 py-4 shadow-2xl animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-6 h-6 bg-white rounded-full animate-ping" />
                <span className="text-2xl font-mono font-bold text-white uppercase tracking-wider">
                  Handoff In Progress
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GlobeView;