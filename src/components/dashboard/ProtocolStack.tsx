import { useState, useEffect } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

interface ProtocolStackProps {
  direction: 'uplink' | 'downlink' | null;
  mode?: 'TCP' | 'DTN';
}

const ProtocolStack = ({ direction, mode = 'TCP' }: ProtocolStackProps) => {
  const [activeLayer, setActiveLayer] = useState<number | null>(null);
  const [packetPosition, setPacketPosition] = useState<number>(-1);

  // Define layers based on mode
  const tcpLayers = [
    { name: "APPLICATION", protocol: "HTTP", label: direction === 'uplink' ? 'Encapsulation' : 'Deliver' },
    { name: "TRANSPORT", protocol: "TCP", label: direction === 'uplink' ? 'Add header' : 'Reassemble' },
    { name: "NETWORK", protocol: "IP", label: direction === 'uplink' ? 'Segment' : 'Route' },
    { name: "PHYSICAL", protocol: "RF", label: direction === 'uplink' ? 'Transmit' : 'Receive' },
  ];

  const dtnLayers = [
    { name: "APPLICATION", protocol: "HTTP", label: direction === 'uplink' ? 'Create payload' : 'Extract payload' },
    { name: "BUNDLE", protocol: "DTN", label: direction === 'uplink' ? 'Bundle wrap' : 'Bundle unwrap', isDTN: true },
    { name: "TRANSPORT", protocol: "TCP", label: direction === 'uplink' ? 'Add header' : 'Reassemble' },
    { name: "NETWORK", protocol: "IP", label: direction === 'uplink' ? 'Segment' : 'Route' },
    { name: "PHYSICAL", protocol: "RF", label: direction === 'uplink' ? 'Transmit' : 'Receive' },
  ];

  const layers = mode === 'DTN' ? dtnLayers : tcpLayers;

  useEffect(() => {
    if (direction) {
      const isUplink = direction === 'uplink';
      const startLayer = isUplink ? 0 : layers.length - 1;
      const endLayer = isUplink ? layers.length - 1 : 0;
      const step = isUplink ? 1 : -1;
      
      let currentLayer = startLayer;
      setPacketPosition(currentLayer);
      
      const interval = setInterval(() => {
        setActiveLayer(currentLayer);
        
        if (currentLayer === endLayer) {
          clearInterval(interval);
          setTimeout(() => {
            setActiveLayer(null);
            setPacketPosition(-1);
          }, 300);
        } else {
          currentLayer += step;
          setPacketPosition(currentLayer);
        }
      }, 200);

      return () => clearInterval(interval);
    }
  }, [direction, layers.length]);

  const glowColor = direction === 'uplink' ? '#00d4ff' : '#4ade80';
  const packetColor = direction === 'uplink' ? '#00d4ff' : '#4ade80';

  return (
    <div className="flex flex-col justify-center h-full relative pr-3">
      {/* Direction arrow indicator */}
      <div className="absolute -left-3 top-1/2 -translate-y-1/2">
        {direction === 'uplink' && (
          <ArrowDown className="w-4 h-4 text-[#00d4ff] animate-pulse" />
        )}
        {direction === 'downlink' && (
          <ArrowUp className="w-4 h-4 text-[#4ade80] animate-pulse" />
        )}
      </div>

      <div className="space-y-1">
        {layers.map((layer, index) => {
          const isActive = activeLayer === index;
          const isDTNLayer = 'isDTN' in layer && layer.isDTN;
          const borderColor = isDTNLayer ? '#ef4444' : (isActive ? glowColor : undefined);
          const bgColor = isDTNLayer ? '#ef444418' : (isActive ? `${glowColor}18` : undefined);
          
          return (
            <div key={index} className="relative">
              <div
                className={`relative border rounded px-2 py-1.5 transition-all duration-200 ${
                  isActive
                    ? ''
                    : isDTNLayer
                    ? 'border-red-500 bg-red-500/10'
                    : 'border-border bg-panel'
                }`}
                style={
                  isActive
                    ? {
                        borderColor: borderColor,
                        backgroundColor: bgColor,
                        boxShadow: `0 0 10px ${glowColor}50`,
                      }
                    : isDTNLayer
                    ? {
                        borderColor: '#ef4444',
                        backgroundColor: '#ef444418',
                      }
                    : {}
                }
              >
                <div className="flex justify-between items-center">
                  <div className={`text-[9px] font-semibold tracking-wider uppercase ${
                    isDTNLayer ? 'text-red-500' : 'text-secondary'
                  }`}>
                    {layer.name}
                  </div>
                  <div className={`text-[8px] font-mono ${
                    isDTNLayer ? 'text-red-500/60' : 'text-secondary/60'
                  }`}>
                    {layer.protocol}
                  </div>
                </div>
                
                {/* Show label during animation */}
                {isActive && (
                  <div className="absolute -right-16 top-1/2 -translate-y-1/2 text-[8px] font-mono whitespace-nowrap opacity-75"
                       style={{ color: glowColor }}>
                    {layer.label}
                  </div>
                )}
              </div>

              {/* Packet icon */}
              {packetPosition === index && (
                <div
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-2 rounded-sm animate-pulse z-10"
                  style={{
                    backgroundColor: packetColor,
                    boxShadow: `0 0 8px ${packetColor}`,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProtocolStack;