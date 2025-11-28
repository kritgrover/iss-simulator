import { useOrbitalTracking } from '@/hooks/useOrbitalTracking';
import Header from "@/components/Header";
import GlobeView from "@/components/globe/GlobeView";
import SkyView from "@/components/globe/SkyView";
import LinkStatus from "@/components/dashboard/LinkStatus";
import OrbitalParameters from "@/components/dashboard/OrbitalParameters";
import MessageExchange from "@/components/dashboard/MessageExchange";
import StationNetwork from "@/components/dashboard/StationNetwork";
import LinkBudgetChart from "@/components/analytics/LinkBudgetChart";
import TrafficFlowMonitor from "@/components/analytics/TrafficFlowMonitor";
import TransmissionMonitor from "@/components/dashboard/TransmissionMonitor";
import NetworkTopology from "@/components/dashboard/NetworkTopology";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { useState, useEffect } from "react";
import { DEFAULT_STATIONS, GroundStation } from "@/types/groundStation";
import { DTNBundle } from '@/types/dtnBundle';

const Index = () => {
  const { isConnected: orbitalConnected, orbitalData } = useOrbitalTracking();

  const [stations, setStations] = useState<GroundStation[]>(DEFAULT_STATIONS);
  const [activeStationId, setActiveStationId] = useState('toronto');
  const [selectedStationId, setSelectedStationId] = useState('toronto');
  const [handoffCount, setHandoffCount] = useState(0);
  const [handoffInProgress, setHandoffInProgress] = useState(false);

  // Update stations
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

      // Update active station and detect handoff
      if (orbitalData.active_station_id && orbitalData.active_station_id !== activeStationId) {
        const oldStation = activeStationId;
        setActiveStationId(orbitalData.active_station_id);
        setHandoffCount(prev => prev + 1);
        setHandoffInProgress(true);
        console.log(`🔄 Handoff: ${oldStation} → ${orbitalData.active_station_id}`);
        
        // Clear handoff indicator
        setTimeout(() => {
          setHandoffInProgress(false);
        }, 2000);
      }
    }
  }, [orbitalData, activeStationId]);

  const handleStationSelect = (stationId: string) => {
    setSelectedStationId(stationId);
  };

  const activeStation = stations.find(s => s.id === activeStationId);
  const selectedStation = stations.find(s => s.id === selectedStationId);
  
  // Get data for both active and selected stations
  const activeStationData = orbitalData?.stations?.find(s => s.id === activeStationId);
  const selectedStationData = orbitalData?.stations?.find(s => s.id === selectedStationId);
  
  return (
    <div className="min-h-screen flex flex-col">
      <Header isConnected={orbitalConnected} connectionError={orbitalConnected ? null : "Connecting..."} />
      
      <main className="flex-1">
        <ResizablePanelGroup direction="horizontal" className="h-full">
          {/* Left Panel - Globe View & Sky View */}
          <ResizablePanel defaultSize={28} minSize={20} className="bg-panel">
            <div className="h-full border-r border-border flex flex-col">
              <div className="flex-1 min-h-0">
                <GlobeView 
                  stations={stations}
                  activeStationId={activeStationId} // Show which station has ISS
                  orbitalData={orbitalData}
                />
              </div>
              <div className="h-[420px]">
                <SkyView 
                  azimuth={activeStationData?.look_angles?.azimuth ?? 0} 
                  elevation={activeStationData?.look_angles?.elevation ?? 0} 
                  isVisible={activeStationData?.is_visible ?? false} 
                />
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle className="w-1 bg-muted hover:bg-primary/30 transition-colors" />

          {/* Center Panel - Communication Dashboard */}
          <ResizablePanel defaultSize={42} minSize={30}>
            <div className="h-full border-r border-border p-4 space-y-4 overflow-y-auto">
              <LinkStatus linkStatus={orbitalData?.link_status ?? null} />

              <MessageExchange 
                activeStationId={selectedStationId}
                stationColor={selectedStation?.color || '#4ade80'}
                handoffCount={handoffCount}
                linkStatus={selectedStationData?.is_visible ? orbitalData?.link_status : null}
                dtnQueues={orbitalData?.dtn_queues as Record<string, DTNBundle[]> ?? {}}
                custodyAcks={orbitalData?.custody_acks ?? []}
              />
              {orbitalData?.active_transmissions && orbitalData.active_transmissions.length > 0 && (
                <TransmissionMonitor 
                  activeTransmissions={orbitalData.active_transmissions}
                />
              )}
              <StationNetwork 
                stations={stations}
                onStationSelect={handleStationSelect}
                dtnQueues={orbitalData?.dtn_queues as Record<string, DTNBundle[]> ?? {}}
                visibleStationsCount={orbitalData?.visible_stations_count ?? 0}
                handoffInProgress={handoffInProgress}
                activeStationId={activeStationId}
                selectedStationId={selectedStationId}
                meshConnections={orbitalData?.mesh_connections ?? []}
              />
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle className="w-1 bg-muted hover:bg-primary/30 transition-colors" />

          {/* Right Panel - Analytics & Orbital Parameters */}
          <ResizablePanel defaultSize={30} minSize={20}>
            <div className="h-full p-4 space-y-4 overflow-y-auto">
              <NetworkTopology
                stations={stations}
                meshConnections={orbitalData?.mesh_connections ?? []}
                activeTransmissions={orbitalData?.active_transmissions ?? []}
                dtnQueues={orbitalData?.dtn_queues as Record<string, DTNBundle[]> ?? {}}
                activeStationId={orbitalData?.active_station_id}
              />
              <OrbitalParameters orbitalData={orbitalData} />
              <LinkBudgetChart 
                linkBudgetHistory={orbitalData?.link_budget_history ?? []}
                currentSNR={orbitalData?.link_status?.snr_db}
              />
              <TrafficFlowMonitor 
                linkStatus={orbitalData?.link_status ?? null}
                visibleLinks={orbitalData?.visible_links ?? []}
                allQueues={orbitalData?.dtn_queues as Record<string, DTNBundle[]> ?? {}}
                stations={orbitalData?.stations ?? []}
                deliveredBundles={orbitalData?.delivered_bundles ?? []}
                isConnected={orbitalData?.link_status?.connection_state === "ACQUIRED" || orbitalData?.link_status?.connection_state === "DEGRADED"}
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>
    </div>
  );
};

export default Index;