import Globe3D from "@/components/globe/Globe3D";

interface ISSEarthViewProps {
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
      is_visible: boolean;
      look_angles?: {
        elevation: number;
      };
    }>;
  } | null;
  stations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    isActive: boolean;
  }>;
}

const ISSEarthView = ({ orbitalData, stations }: ISSEarthViewProps) => {
  // Convert stations to format expected by Globe3D
  const groundStations = stations.map(station => {
    const orbitalStation = orbitalData?.stations?.find(s => s.id === station.id);
    return {
      id: station.id,
      name: station.name,
      lat: station.lat,
      lon: station.lon,
      color: station.color,
      is_visible: orbitalStation?.is_visible || false,
    };
  });

  const issPosition = orbitalData?.iss_position || {
    latitude: 0,
    longitude: 0,
    altitude_km: 408,
    velocity_kmps: 7.66,
  };

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
            groundStations={groundStations}
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
            {groundStations.filter(s => s.is_visible).map(station => (
              <div key={station.id} className="flex items-center gap-2 text-xs font-mono transition-transform hover:translate-x-1">
                <div
                  className="w-3 h-3 rounded-full animate-pulse"
                  style={{
                    backgroundColor: station.color,
                    boxShadow: `0 0 10px ${station.color}80`
                  }}
                />
                <span className="text-secondary">{station.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ISSEarthView;

