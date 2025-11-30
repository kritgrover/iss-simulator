import { Circle } from "lucide-react";
import { useMET } from "@/hooks/useMET";

interface HeaderProps {
  isConnected: boolean;
  connectionError?: string | null;
}

const Header = ({ isConnected, connectionError }: HeaderProps) => {
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