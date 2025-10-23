import { Video, Globe, ExternalLink } from "lucide-react";
import { useState } from "react";

interface SkyViewProps {
  azimuth?: number;
  elevation?: number;
  isVisible?: boolean;
}

const SkyView = ({ 
  azimuth = 127.8, 
  elevation = 42.3, 
  isVisible = true 
}: SkyViewProps) => {
  const [viewMode, setViewMode] = useState<'map' | 'stream'>('map');
  const [streamSource, setStreamSource] = useState(0);

  // Multiple stream sources to try
  const streamSources = [
    {
      name: "NASA Live Stream",
      url: "https://www.youtube.com/embed/iYmvCUonukw?autoplay=1&mute=1",
      description: "High definition Earth view from ISS"
    },
    {
      name: "Sen 4K Live",
      url: "https://www.youtube.com/embed/fO9e9jnhYK8?autoplay=1&mute=1",
      description: "24/7 ISS live feed"
    },
    {
      name: "ISS Live Streaming",
      url: "https://www.youtube.com/embed/Ra2CBPw1TOY?autoplay=1&mute=0",
      description: "24/7 ISS live feed"
    },
    {
      name: "LIVE Video from the International Space Station",
      url: "https://www.youtube.com/embed/hl0CtTZzUGg?si=IlY8gRc6VtUhr8Cl",
      description: "24/7 ISS live feed"
    }
  ];

  const currentStream = streamSources[streamSource];

  const handleNextStream = () => {
    setStreamSource((prev) => (prev + 1) % streamSources.length);
  };

  return (
    <div className="h-full flex flex-col border-t border-border bg-[#0a0e1a]">
      <div className="px-4 py-3 border-b border-border bg-[#0f1729]">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold tracking-wider uppercase text-secondary">
            ISS VIEW
          </h2>
          <div className="flex items-center gap-3">
            {/* Toggle buttons */}
            <div className="flex gap-1 bg-background/50 rounded p-1">
              <button
                onClick={() => setViewMode('map')}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  viewMode === 'map' 
                    ? 'bg-primary text-primary-foreground' 
                    : 'text-secondary hover:text-foreground'
                }`}
                title="Map View"
              >
                <Globe className="w-3 h-3" />
              </button>
              <button
                onClick={() => setViewMode('stream')}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  viewMode === 'stream' 
                    ? 'bg-primary text-primary-foreground' 
                    : 'text-secondary hover:text-foreground'
                }`}
                title="Live Stream"
              >
                <Video className="w-3 h-3" />
              </button>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-xs font-mono text-success">LIVE</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 relative bg-black overflow-hidden">
        {viewMode === 'map' ? (
          /* ISS Tracker Map */
          <iframe
            src="https://isstracker.spaceflight.esa.int/"
            width="100%"
            height="100%"
            className="absolute inset-0 border-0 block"
            scrolling="no"
            title="ISS Tracker"
          />
        ) : (
          /* Live Stream with source selector */
          <div className="absolute inset-0">
            <iframe
              key={streamSource} // Force reload when source changes
              width="100%"
              height="100%"
              src={currentStream.url}
              title={currentStream.name}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="absolute inset-0 border-0 block"
              scrolling="no"
            />
            
            {/* Stream source selector overlay */}
            <div className="absolute top-2 left-2 right-2 flex items-center justify-between bg-black/80 backdrop-blur-sm rounded p-2 z-10">
              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold text-foreground truncate">
                  {currentStream.name}
                </div>
                <div className="text-[10px] text-secondary truncate">
                  {currentStream.description}
                </div>
              </div>
              <button
                onClick={handleNextStream}
                className="ml-2 px-2 py-1 bg-primary/20 hover:bg-primary/30 border border-primary/50 rounded text-xs font-mono text-primary transition-colors flex items-center gap-1"
                title="Try another stream"
              >
                <ExternalLink className="w-3 h-3" />
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Status bar at bottom */}
      <div className="px-4 py-3 border-t border-border bg-[#0f1729] space-y-1">
        
        <div className="flex justify-between text-xs">
          <span className="text-secondary"></span>
          <span className={`font-mono ${isVisible ? 'text-success' : 'text-secondary'}`}>
            {isVisible ? '🔗 TRACKING' : '⏳ WAITING'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default SkyView;