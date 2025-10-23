import { Play, Pause, Clock, Satellite } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useRef } from "react";
import { GroundStation } from "@/types/groundStation";

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
  const [earthRotation, setEarthRotation] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

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

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let lastTime = Date.now();

    const animate = () => {
      const now = Date.now();
      const deltaTime = (now - lastTime) / 1000;
      lastTime = now;

      // Slowly rotate Earth
      setEarthRotation(prev => (prev + 0.1) % 360);

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const earthRadius = 100;
      const orbitRadius = 180;

      // Draw space background
      ctx.fillStyle = '#0a0e1a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw orbital path
      ctx.strokeStyle = '#00d4ff30';
      ctx.lineWidth = 1;
      ctx.setLineDash([10, 5]);
      ctx.beginPath();
      ctx.arc(centerX, centerY, orbitRadius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw Earth shadow/glow
      const shadowGradient = ctx.createRadialGradient(
        centerX, centerY, earthRadius,
        centerX, centerY, earthRadius + 30
      );
      shadowGradient.addColorStop(0, '#1e3a8a40');
      shadowGradient.addColorStop(1, '#1e3a8a00');
      ctx.fillStyle = shadowGradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, earthRadius + 30, 0, Math.PI * 2);
      ctx.fill();

      // Draw Earth
      const earthGradient = ctx.createRadialGradient(
        centerX - 30, centerY - 30, 20,
        centerX, centerY, earthRadius
      );
      earthGradient.addColorStop(0, '#60a5fa');
      earthGradient.addColorStop(0.4, '#3b82f6');
      earthGradient.addColorStop(0.7, '#2563eb');
      earthGradient.addColorStop(1, '#1e40af');

      ctx.fillStyle = earthGradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, earthRadius, 0, Math.PI * 2);
      ctx.fill();

      // Draw Earth outline
      ctx.strokeStyle = '#1e40af';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw simplified continents (rotating)
      ctx.save();
      ctx.translate(centerX, centerY);
      ctx.rotate((earthRotation * Math.PI) / 180);
      ctx.fillStyle = '#22c55e';
      ctx.globalAlpha = 0.6;

      // North America
      ctx.beginPath();
      ctx.ellipse(-20, -40, 25, 35, 0.3, 0, Math.PI * 2);
      ctx.fill();

      // South America
      ctx.beginPath();
      ctx.ellipse(-15, 20, 15, 30, 0.2, 0, Math.PI * 2);
      ctx.fill();

      // Europe/Africa
      ctx.beginPath();
      ctx.ellipse(25, -10, 20, 40, -0.2, 0, Math.PI * 2);
      ctx.fill();

      // Asia
      ctx.beginPath();
      ctx.ellipse(50, -30, 30, 25, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
      ctx.globalAlpha = 1;

      // Draw all ground stations
      if (orbitalData?.stations) {
        orbitalData.stations.forEach(stationData => {
          const station = stations.find(s => s.id === stationData.id);
          if (!station) return;

          const stationAngle = ((stationData.lon + earthRotation) * Math.PI) / 180;
          const latFactor = Math.cos((stationData.lat * Math.PI) / 180);
          
          const stationX = centerX + Math.sin(stationAngle) * earthRadius * 0.85 * latFactor;
          const stationY = centerY - Math.sin((stationData.lat * Math.PI) / 180) * earthRadius * 0.85;

          // Only draw if on visible hemisphere
          const isOnVisibleSide = Math.cos(stationAngle) > 0;
          
          if (isOnVisibleSide) {
            const isActive = stationData.id === activeStationId;
            const isTracking = stationData.is_visible;
            
            // Draw ground station
            ctx.fillStyle = station.color;
            ctx.shadowColor = station.color;
            ctx.shadowBlur = isActive ? 15 : 8;
            
            // Pulsing animation for active/tracking stations
            const pulse = isTracking ? 3 + Math.sin(Date.now() / 300) * 1.5 : 2;
            
            ctx.beginPath();
            ctx.arc(stationX, stationY, pulse, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.shadowBlur = 0;
            
            // Outer ring
            ctx.strokeStyle = station.color;
            ctx.lineWidth = isActive ? 2 : 1;
            ctx.beginPath();
            ctx.arc(stationX, stationY, isActive ? 10 : 8, 0, Math.PI * 2);
            ctx.stroke();

            // Label for active or tracking stations
            if (isActive || isTracking) {
              ctx.fillStyle = station.color;
              ctx.font = 'bold 9px monospace';
              ctx.fillText(station.name, stationX - 15, stationY - 15);
            }

            // Draw connection line if tracking ISS
            if (isTracking && orbitalData) {
              const issLon = orbitalData.iss_position.longitude;
              const issLat = orbitalData.iss_position.latitude;
              
              const issAngle = ((issLon + earthRotation) * Math.PI) / 180;
              const issLatFactor = Math.cos((issLat * Math.PI) / 180);
              
              const issX = centerX + Math.cos(issAngle) * orbitRadius;
              const issY = centerY + Math.sin(issAngle) * orbitRadius * issLatFactor;

              ctx.strokeStyle = station.color + '60';
              ctx.lineWidth = 2;
              ctx.setLineDash([10, 5]);
              ctx.beginPath();
              ctx.moveTo(stationX, stationY);
              ctx.lineTo(issX, issY);
              ctx.stroke();
              ctx.setLineDash([]);

              // Draw signal pulses along the line
              const pulseProgress = (Date.now() % 2000) / 2000;
              const pulseX = stationX + (issX - stationX) * pulseProgress;
              const pulseY = stationY + (issY - stationY) * pulseProgress;
              
              ctx.fillStyle = station.color;
              ctx.beginPath();
              ctx.arc(pulseX, pulseY, 4, 0, Math.PI * 2);
              ctx.fill();
            }
          }
        });
      }

      // Draw ISS if we have orbital data
      if (orbitalData) {
        const issLon = orbitalData.iss_position.longitude;
        const issLat = orbitalData.iss_position.latitude;
        
        const issAngle = ((issLon + earthRotation) * Math.PI) / 180;
        const latFactor = Math.cos((issLat * Math.PI) / 180);
        
        const issX = centerX + Math.cos(issAngle) * orbitRadius;
        const issY = centerY + Math.sin(issAngle) * orbitRadius * latFactor;

        // Draw ISS trail
        ctx.strokeStyle = '#00ff0040';
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 1; i <= 20; i++) {
          const trailAngle = issAngle - (i * 0.1);
          const trailX = centerX + Math.cos(trailAngle) * orbitRadius;
          const trailY = centerY + Math.sin(trailAngle) * orbitRadius * latFactor;
          
          if (i === 1) {
            ctx.moveTo(trailX, trailY);
          } else {
            ctx.lineTo(trailX, trailY);
          }
        }
        ctx.stroke();

        // Draw ISS glow
        const issGlow = ctx.createRadialGradient(issX, issY, 0, issX, issY, 25);
        issGlow.addColorStop(0, '#00ff0080');
        issGlow.addColorStop(0.5, '#00ff0040');
        issGlow.addColorStop(1, '#00ff0000');
        ctx.fillStyle = issGlow;
        ctx.beginPath();
        ctx.arc(issX, issY, 25, 0, Math.PI * 2);
        ctx.fill();

        // Draw ISS body
        ctx.save();
        ctx.translate(issX, issY);
        ctx.rotate(issAngle + Math.PI / 2);

        // Solar panels (left)
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(-20, -3, 12, 6);
        
        // Main body
        ctx.fillStyle = '#00ff00';
        ctx.fillRect(-4, -5, 8, 10);
        
        // Solar panels (right)
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(8, -3, 12, 6);

        ctx.restore();

        // Draw ISS label
        ctx.fillStyle = '#00ff00';
        ctx.font = 'bold 11px monospace';
        ctx.shadowColor = '#00ff00';
        ctx.shadowBlur = 5;
        ctx.fillText('🛰️ ISS', issX + 15, issY - 15);
        ctx.shadowBlur = 0;
      }

      // Draw coordinate grid
      ctx.strokeStyle = '#ffffff10';
      ctx.lineWidth = 1;
      for (let i = 0; i < 8; i++) {
        const angle = (i * Math.PI * 2) / 8;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(
          centerX + Math.cos(angle) * (orbitRadius + 30),
          centerY + Math.sin(angle) * (orbitRadius + 30)
        );
        ctx.stroke();
      }

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [earthRotation, orbitalData, stations, activeStationId]);

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
      
      <div className="flex-1 flex items-center justify-center p-4 relative">
        {/* Main Canvas */}
        <div className="relative">
          <canvas 
            ref={canvasRef}
            width={600}
            height={600}
            className="max-w-full h-auto"
          />

          {/* Legend */}
          <div className="absolute top-4 left-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-secondary">Earth</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-secondary">ISS</span>
            </div>
            {activeStation && (
              <div className="flex items-center gap-2 text-xs font-mono">
                <div 
                  className="w-3 h-3 rounded-full" 
                  style={{ backgroundColor: activeStation.color }}
                />
                <span className="text-secondary">{activeStation.name}</span>
              </div>
            )}
          </div>
        </div>

        {/* Data Panels */}
        <div className="absolute bottom-4 left-4 right-4 flex gap-4">
          {/* ISS Data */}
          <div className="flex-1 bg-black/80 backdrop-blur-sm border border-border rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Satellite className="w-4 h-4 text-success" />
              <span className="text-xs font-semibold text-secondary uppercase tracking-wide">
                ISS Position
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <div className="text-xs font-mono">
                <span className="text-secondary">LAT:</span>{' '}
                <span className="text-success">{issLat.toFixed(4)}°</span>
              </div>
              <div className="text-xs font-mono">
                <span className="text-secondary">LON:</span>{' '}
                <span className="text-success">{issLon.toFixed(4)}°</span>
              </div>
              <div className="text-xs font-mono">
                <span className="text-secondary">ALT:</span>{' '}
                <span className="text-primary">{issAlt.toFixed(1)} km</span>
              </div>
              <div className="text-xs font-mono">
                <span className="text-secondary">VEL:</span>{' '}
                <span className="text-primary">{issVelocity.toFixed(2)} km/s</span>
              </div>
            </div>
          </div>

          {/* Ground Station Status */}
          {activeStation && activeStationData && (
            <div className="flex-1 bg-black/80 backdrop-blur-sm border border-border rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <div 
                  className="w-3 h-3 rounded-full animate-pulse" 
                  style={{ backgroundColor: activeStation.color }}
                />
                <span className="text-xs font-semibold text-secondary uppercase tracking-wide">
                  {activeStation.name}
                </span>
              </div>
              <div className="space-y-1">
                <div className="text-xs font-mono">
                  <span className="text-secondary">STATUS:</span>{' '}
                  <span className={issInCone ? 'text-success' : 'text-secondary'}>
                    {issInCone ? '🔗 TRACKING' : '⏳ WAITING'}
                  </span>
                </div>
                {issInCone ? (
                  <div className="text-xs font-mono">
                    <span className="text-secondary">ELEV:</span>{' '}
                    <span className="text-primary">{activeStationData.look_angles.elevation.toFixed(1)}°</span>
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