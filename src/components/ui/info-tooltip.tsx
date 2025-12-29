import * as React from "react";
import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface InfoTooltipProps {
  content: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}

export const InfoTooltip = ({ content, side = "top", className = "" }: InfoTooltipProps) => {
  return (
    <TooltipProvider delayDuration={100} skipDelayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={`inline-flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 cursor-help ${className}`}
            aria-label="Show information"
          >
            <HelpCircle className="w-3.5 h-3.5 text-muted-foreground hover:text-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent 
          side={side} 
          className="max-w-sm p-3 text-sm bg-popover border border-border shadow-lg z-[9999]"
          sideOffset={8}
          align="start"
          avoidCollisions={true}
          style={{ 
            backgroundColor: 'hsl(var(--popover))',
            color: 'hsl(var(--popover-foreground))',
            zIndex: 9999
          }}
        >
          <div className="space-y-1.5 text-popover-foreground">
            {content}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

