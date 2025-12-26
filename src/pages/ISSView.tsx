import { useOrbitalTracking } from '@/hooks/useOrbitalTracking';
import Header from "@/components/Header";
import ISSEarthView from "@/components/iss/ISSEarthView";
import MessageInbox from "@/components/iss/MessageInbox";
import MessageReassembly from "@/components/iss/MessageReassembly";
import MessageReply from "@/components/iss/MessageReply";
import ISSDashboard from "@/components/iss/ISSDashboard";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { useState, useEffect } from "react";
import { DEFAULT_STATIONS, GroundStation } from "@/types/groundStation";
import { useISSMessages, ISSMessage } from "@/hooks/useISSMessages";

const ISSView = () => {
  const { isConnected: orbitalConnected, orbitalData } = useOrbitalTracking();
  const { messages } = useISSMessages();
  const [selectedMessage, setSelectedMessage] = useState<ISSMessage | null>(null);
  const [stations, setStations] = useState<GroundStation[]>(DEFAULT_STATIONS);

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
      </section>
      
      {/* Panels Section - Below Earth View */}
      <main className="flex-1 w-full">
        <ResizablePanelGroup direction="horizontal" className="h-full min-h-screen">
          {/* Left Panel - Dashboard and Inbox */}
          <ResizablePanel defaultSize={30} minSize={20} className="bg-panel">
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
          <ResizablePanel defaultSize={40} minSize={30} className="bg-panel">
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
              <MessageReply />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>
    </div>
  );
};

export default ISSView;

