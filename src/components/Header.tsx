import { Circle, Satellite, Radio } from "lucide-react";
import { useMET } from "@/hooks/useMET";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  isConnected: boolean;
  connectionError?: string | null;
  viewMode?: "ground" | "iss";
  onViewModeChange?: (mode: "ground" | "iss") => void;
}

const Header = ({ isConnected, connectionError, viewMode = "ground", onViewModeChange }: HeaderProps) => {
  const met = useMET();

  return (
    <header className="h-14 border-b border-border bg-panel px-6 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <h1 className="text-sm font-semibold tracking-wider uppercase">
          ISS COMMUNICATION SIMULATOR
        </h1>
        <div className="flex items-center gap-4 text-xs font-mono text-secondary">
          <span>MET: {met}</span>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        {onViewModeChange && (
          <div className="flex items-center gap-2 border-r border-border pr-4">
            <Button
              variant={viewMode === "ground" ? "default" : "ghost"}
              size="sm"
              onClick={() => onViewModeChange("ground")}
              className="h-8"
            >
              <Radio className="w-3 h-3 mr-2" />
              Ground View
            </Button>
            <Button
              variant={viewMode === "iss" ? "default" : "ghost"}
              size="sm"
              onClick={() => onViewModeChange("iss")}
              className="h-8"
            >
              <Satellite className="w-3 h-3 mr-2" />
              ISS View
            </Button>
          </div>
        )}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Circle className="w-2 h-2 fill-success text-success animate-pulse" />
              <span className="text-xs font-mono text-success">CONNECTED TO BACKEND</span>
            </>
          ) : (
            <>
              <Circle className="w-2 h-2 fill-destructive text-destructive" />
              <span className="text-xs font-mono text-destructive">
                {connectionError || "COULDN'T ESTABLISH CONNECTION"}
              </span>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;