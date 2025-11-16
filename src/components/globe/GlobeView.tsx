import { Play, Pause, Clock, Satellite } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  
  const issLat = orbitalData?.iss_position?.latitude ?? 0;
  const issLon = orbitalData?.iss_position?.longitude ?? 0;
  const issAlt = orbitalData?.iss_position?.altitude_km ?? 0;
  const issVelocity = orbitalData?.iss_position?.velocity_kmps ?? 0;

  const formatTime = (isoString?: string) => {
    if (!isoString) return "--:--:--";
    const date = new Date(isoString);
    return date.toISOString().substr(11, 8);
  };

  // Count how many stations are currently tracking
  const trackingStationsCount = orbitalData?.stations?.filter(s => s.is_visible).length ?? 0;

  return (
    <div className="h-full flex flex-col bg-[#0a0e1a]">
      <div className="px-4 py-3 border-b border-border bg-[#0f1729]">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold tracking-wider uppercase text-secondary">
            ORBITAL TRACKING
          </h2>
          <div className="flex items-center gap-3">
            {trackingStationsCount > 0 && (
              <div className="flex items-center gap-2 bg-success/20 rounded px-2 py-1">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-xs font-mono text-success">
                  {trackingStationsCount} STATION{trackingStationsCount > 1 ? 'S' : ''} TRACKING
                </span>
              </div>
            )}
            {orbitalData && (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-xs font-mono text-success">LIVE</span>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex-1 flex items-center justify-center relative">
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

        {/* Data Panels - Glassmorphism */}
        <div className="absolute bottom-4 left-4 right-4 flex gap-4 animate-in slide-in-from-bottom duration-500">
          {/* ISS Data */}
          <div
            className="flex-1 rounded-lg p-3 transition-all duration-300 hover:scale-105"
            style={{
              background: 'rgba(0, 255, 0, 0.05)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(0, 255, 0, 0.2)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(0, 255, 0, 0.1), 0 0 20px rgba(0, 255, 0, 0.1)',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Satellite className="w-4 h-4 text-success animate-pulse" />
              <span className="text-xs font-semibold text-success uppercase tracking-wide">
                ISS Position
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <div className="text-xs font-mono transition-all hover:translate-x-1">
                <span className="text-secondary">LAT:</span>{' '}
                <span className="text-success font-semibold">{issLat.toFixed(4)}°</span>
              </div>
              <div className="text-xs font-mono transition-all hover:translate-x-1">
                <span className="text-secondary">LON:</span>{' '}
                <span className="text-success font-semibold">{issLon.toFixed(4)}°</span>
              </div>
              <div className="text-xs font-mono transition-all hover:translate-x-1">
                <span className="text-secondary">ALT:</span>{' '}
                <span className="text-primary font-semibold">{issAlt.toFixed(1)} km</span>
              </div>
              <div className="text-xs font-mono transition-all hover:translate-x-1">
                <span className="text-secondary">VEL:</span>{' '}
                <span className="text-primary font-semibold">{issVelocity.toFixed(2)} km/s</span>
              </div>
            </div>
          </div>

          {/* Ground Station Status */}
          {activeStation && activeStationData && (
            <div
              className="flex-1 rounded-lg p-3 transition-all duration-300 hover:scale-105"
              style={{
                background: `${activeStation.color}10`,
                backdropFilter: 'blur(16px)',
                border: `1px solid ${activeStation.color}40`,
                boxShadow: `0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 ${activeStation.color}20, 0 0 20px ${activeStation.color}20`,
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div
                  className="w-3 h-3 rounded-full animate-pulse"
                  style={{
                    backgroundColor: activeStation.color,
                    boxShadow: `0 0 10px ${activeStation.color}`
                  }}
                />
                <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: activeStation.color }}>
                  {activeStation.name}
                </span>
              </div>
              <div className="space-y-1">
                <div className="text-xs font-mono transition-all hover:translate-x-1">
                  <span className="text-secondary">STATUS:</span>{' '}
                  <span className={issInCone ? 'text-success font-semibold' : 'text-secondary'}>
                    {issInCone ? '🔗 TRACKING' : '⏳ WAITING'}
                  </span>
                </div>
                {issInCone ? (
                  <div className="text-xs font-mono transition-all hover:translate-x-1">
                    <span className="text-secondary">ELEV:</span>{' '}
                    <span className="text-primary font-semibold">{activeStationData.look_angles.elevation.toFixed(1)}°</span>
                  </div>
                ) : (
                  <div className="text-xs font-mono">
                    <span className="text-secondary">NEXT:</span>{' '}
                    <span className="text-amber-500">
                      {activeStationData.next_pass_minutes > 0 
                        ? `${activeStationData.next_pass_minutes} min`
                        : '--'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
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

      {/* Bottom Controls */}
      <div className="px-4 py-3 border-t border-border bg-[#0f1729] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" className="h-8">
            <Play className="h-3 w-3 mr-1" />
            <span className="text-xs">Play</span>
          </Button>
          <Button variant="outline" size="sm" className="h-8">
            <Pause className="h-3 w-3 mr-1" />
            <span className="text-xs">Pause</span>
          </Button>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono text-secondary">
          <div className="flex items-center gap-2">
            <Clock className="h-3 w-3" />
            <span>UTC {formatTime(orbitalData?.timestamp)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GlobeView;