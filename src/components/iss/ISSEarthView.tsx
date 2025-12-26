import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import Globe3D from "@/components/globe/Globe3D";
import { Satellite } from "lucide-react";

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

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Satellite className="w-4 h-4" />
          Earth View from ISS
        </CardTitle>
        <CardDescription>
          Real-time view of Earth from International Space Station
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 min-h-0">
        <div className="h-full w-full rounded-lg overflow-hidden border border-border bg-background">
          {orbitalData?.iss_position ? (
            <Globe3D
              issPosition={orbitalData.iss_position}
              groundStations={groundStations}
              orbitalPath={orbitalData.orbital_path}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-secondary">
              Waiting for orbital data...
            </div>
          )}
        </div>
        {orbitalData?.iss_position && (
          <div className="mt-2 text-xs text-secondary space-y-1">
            <div className="flex justify-between">
              <span>Altitude:</span>
              <span className="font-mono">{orbitalData.iss_position.altitude_km.toFixed(1)} km</span>
            </div>
            <div className="flex justify-between">
              <span>Velocity:</span>
              <span className="font-mono">{orbitalData.iss_position.velocity_kmps.toFixed(3)} km/s</span>
            </div>
            <div className="flex justify-between">
              <span>Position:</span>
              <span className="font-mono">
                {orbitalData.iss_position.latitude.toFixed(2)}°N, {orbitalData.iss_position.longitude.toFixed(2)}°E
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ISSEarthView;

