import { useOrbitalTracking } from '@/hooks/useOrbitalTracking';
import ISSEarthView from "@/components/iss/ISSEarthView";
import MessageInbox from "@/components/iss/MessageInbox";
import MessageReassembly from "@/components/iss/MessageReassembly";
import MessageReply from "@/components/iss/MessageReply";
import ISSNetworkQueue from "@/components/iss/ISSNetworkQueue";
import ISSDashboard from "@/components/iss/ISSDashboard";
import OrbitalParameters from "@/components/dashboard/OrbitalParameters";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { useState, useEffect } from "react";
import { DEFAULT_STATIONS, GroundStation } from "@/types/groundStation";
import { useISSMessages, ISSMessage } from "@/hooks/useISSMessages";

const ISSView = () => {
  const { isConnected: orbitalConnected, orbitalData } = useOrbitalTracking();
  const { messages, fetchMessages } = useISSMessages();
  const [selectedMessage, setSelectedMessage] = useState<ISSMessage | null>(null);
  const [stations, setStations] = useState<GroundStation[]>(DEFAULT_STATIONS);

  // Force immediate fetch when ISS view mounts to catch any messages that arrived while on ground view
  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  // Update stations with orbital data
  useEffect(() => {
    if (orbitalData?.stations) {
      setStations(prevStations => 
        prevStations.map(station => {
          const backendStation = orbitalData.stations.find(s => s.id === station.id);
          if (backendStation) {
            return {
              ...station,
              isActive: backendStation.is_visible,
              elevation: backendStation.look_angles?.elevation || 0,
              nextPassTime: backendStation.next_pass_minutes > 0 
                ? `${Math.floor(backendStation.next_pass_minutes / 60)}:${(backendStation.next_pass_minutes % 60).toString().padStart(2, '0')}`
                : '--:--'
            };
          }
          return station;
        })
      );
    }
  }, [orbitalData]);

  // Auto-select first incomplete message if none selected
  useEffect(() => {
    if (!selectedMessage && messages.length > 0) {
      const incompleteMessage = messages.find(m => !m.is_complete);
      if (incompleteMessage) {
        setSelectedMessage(incompleteMessage);
      } else if (messages.length > 0) {
        setSelectedMessage(messages[0]);
      }
    }
  }, [messages, selectedMessage]);

  return (
    <div className="min-h-screen flex flex-col">
      
      {/* Full-screen Earth View Section */}
      <section className="h-screen w-full relative">
        <ISSEarthView 
          stations={stations}
          orbitalData={orbitalData || undefined}
        />
        
        {/* Floating Orbital Parameters and ISS Status */}
        <div className="absolute top-4 right-4 bottom-4 md:bottom-auto z-0 w-full md:w-80 space-y-4 flex flex-col md:block overflow-y-auto">
          <div 
            className="rounded-lg transition-all duration-300 [&>*]:bg-transparent [&>*]:border-0 flex-shrink-0"
            style={{
              background: 'rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
            }}
          >
            <OrbitalParameters orbitalData={orbitalData} />
          </div>
          
          {/* ISS Status */}
          {orbitalData?.iss_position && (
            <div
              className="rounded-lg p-3 transition-all duration-300 flex-shrink-0"
              style={{
                background: 'rgba(0, 255, 0, 0.1)',
                backdropFilter: 'blur(16px)',
                border: '1px solid rgba(0, 255, 0, 0.4)',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(0, 255, 0, 0.2), 0 0 20px rgba(0, 255, 0, 0.2)',
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div
                  className="w-3 h-3 rounded-full animate-pulse"
                  style={{
                    backgroundColor: '#00ff00',
                    boxShadow: '0 0 10px #00ff00'
                  }}
                />
                <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#00ff00' }}>
                  ISS
                </span>
              </div>
              <div className="space-y-1">
                <div className="text-xs font-mono transition-all hover:translate-x-1">
                  <span className="text-secondary">ALT:</span>{' '}
                  <span className="text-primary font-semibold">{orbitalData.iss_position.altitude_km.toFixed(1)} km</span>
                </div>
                <div className="text-xs font-mono transition-all hover:translate-x-1">
                  <span className="text-secondary">VEL:</span>{' '}
                  <span className="text-primary font-semibold">{orbitalData.iss_position.velocity_kmps.toFixed(3)} km/s</span>
                </div>
                <div className="text-xs font-mono">
                  <span className="text-secondary">POS:</span>{' '}
                  <span className="text-primary font-semibold">
                    {orbitalData.iss_position.latitude.toFixed(1)}°N, {orbitalData.iss_position.longitude.toFixed(1)}°E
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
        
      </section>
      
      {/* Panels Section - Below Earth View */}
      <main className="flex-1 w-full">
        <ResizablePanelGroup direction="horizontal" className="h-full min-h-screen">
          {/* Left Panel - Dashboard and Inbox */}
          <ResizablePanel defaultSize={28} minSize={20} className="bg-panel">
            <div className="h-full border-r border-border flex flex-col">
              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
                <ISSDashboard orbitalData={orbitalData || undefined} />
                <MessageInbox 
                  onMessageSelect={setSelectedMessage}
                  selectedMessage={selectedMessage}
                />
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle className="w-1 bg-muted hover:bg-primary/30 transition-colors" />

          {/* Center Panel - Message Reassembly */}
          <ResizablePanel defaultSize={42} minSize={30} className="bg-panel">
            <div className="h-full border-r border-border p-4 space-y-4 overflow-y-auto">
              <MessageReassembly 
                selectedMessage={selectedMessage}
                onMessageSelected={setSelectedMessage}
              />
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle className="w-1 bg-muted hover:bg-primary/30 transition-colors" />

          {/* Right Panel - Reply Interface */}
          <ResizablePanel defaultSize={30} minSize={20} className="bg-panel">
            <div className="h-full p-4 space-y-4 overflow-y-auto">
              <MessageReply stations={stations} />
              <ISSNetworkQueue 
                bundles={orbitalData?.iss_queue || []} 
                stations={stations} 
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>
    </div>
  );
};

export default ISSView;

