import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useISSMessages } from "@/hooks/useISSMessages";
import { DEFAULT_STATIONS, GroundStation } from "@/types/groundStation";
import { Send, Radio, Loader2, Megaphone } from "lucide-react";
import { useState } from "react";
import { toast } from "@/hooks/use-toast";

interface MessageReplyProps {
  stations?: GroundStation[];
}

const MessageReply = ({ stations = DEFAULT_STATIONS }: MessageReplyProps) => {
  const { sendReply } = useISSMessages();
  const [destinationStation, setDestinationStation] = useState<string>("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [isBroadcast, setIsBroadcast] = useState(false);

  const handleSend = async () => {
    if (!isBroadcast && !destinationStation) {
      toast({
        title: "Error",
        description: "Please select a destination station or enable broadcast",
        variant: "destructive",
      });
      return;
    }

    if (!message.trim()) {
      toast({
        title: "Error",
        description: "Please enter a message",
        variant: "destructive",
      });
      return;
    }

    setSending(true);
    // Always use EXPEDITED priority for ISS messages
    const success = await sendReply(
      isBroadcast ? "BROADCAST" : destinationStation, 
      message, 
      "EXPEDITED",
      isBroadcast
    );
    setSending(false);

    if (success) {
      if (isBroadcast) {
        toast({
          title: "Broadcast Queued",
          description: `Broadcast message added to ISS queue. Will flood to all stations at next contact.`,
        });
      } else {
        const stationName = stations.find(s => s.id === destinationStation)?.name || destinationStation;
        toast({
          title: "Message Queued",
          description: `Reply to ${stationName} added to ISS queue. Will transmit at next contact.`,
        });
      }
      setMessage("");
      setDestinationStation("");
      setIsBroadcast(false);
    } else {
      toast({
        title: "Error",
        description: "Failed to queue reply. Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
          <Radio className="w-3 h-3" />
          SEND REPLY
        </h3>
        <div className="text-[11px] font-mono text-secondary mt-1">
          Compose and send a message to a ground station
        </div>
      </div>
      <div className="space-y-4">
        {/* Broadcast Option */}
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="broadcast"
              checked={isBroadcast}
              onCheckedChange={(checked) => {
                setIsBroadcast(checked === true);
                if (checked) {
                  setDestinationStation("");
                }
              }}
            />
            <Label
              htmlFor="broadcast"
              className="text-[10px] font-semibold tracking-wider uppercase text-secondary cursor-pointer flex items-center gap-2"
            >
              <Megaphone className="w-3 h-3" />
              Broadcast to All Stations
            </Label>
          </div>
          {isBroadcast && (
            <div className="text-[10px] text-secondary font-mono pl-6">
              Message will be flooded to all ground stations via mesh network
            </div>
          )}
        </div>

        {/* Destination Station Selector */}
        <div className="space-y-2">
          <Label htmlFor="destination" className="text-[10px] font-semibold tracking-wider uppercase text-secondary">
            Destination Station
          </Label>
          <Select 
            value={destinationStation} 
            onValueChange={setDestinationStation}
            disabled={isBroadcast}
          >
            <SelectTrigger 
              id="destination" 
              className={`h-8 text-[11px] font-mono ${isBroadcast ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <SelectValue placeholder={isBroadcast ? "Broadcast mode (all stations)" : "Select a station"} />
            </SelectTrigger>
            <SelectContent>
              {stations.map((station) => (
                <SelectItem key={station.id} value={station.id} className="text-[11px] font-mono">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: station.color }}
                    />
                    {station.name}
                    {station.isActive && (
                      <span className="ml-2 text-[10px] text-green-500 font-bold">(VISIBLE)</span>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Message Composer */}
        <div className="space-y-2">
          <Label htmlFor="message" className="text-[10px] font-semibold tracking-wider uppercase text-secondary">
            Message
          </Label>
          <Textarea
            id="message"
            placeholder="Type your message here..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={6}
            className="font-mono text-[11px]"
          />
          <div className="text-[10px] text-secondary font-mono">
            {message.length} characters
          </div>
        </div>

        {/* Send Button */}
        <Button
          onClick={handleSend}
          disabled={sending || (!isBroadcast && !destinationStation) || !message.trim()}
          className="w-full h-8 text-[11px] font-mono"
        >
          {sending ? (
            <>
              <Loader2 className="w-3 h-3 mr-2 animate-spin" />
              Queueing...
            </>
          ) : (
            <>
              {isBroadcast ? (
                <>
                  <Megaphone className="w-3 h-3 mr-2" />
                  Queue Broadcast
                </>
              ) : (
                <>
                  <Send className="w-3 h-3 mr-2" />
                  Queue Reply
                </>
              )}
            </>
          )}
        </Button>

        {/* Route Preview */}
        {(destinationStation || isBroadcast) && (
          <div className="text-[11px] text-secondary p-2 bg-background/50 rounded border border-border">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary mb-1">Route Preview</div>
            {isBroadcast ? (
              <>
                <div className="font-mono">
                  ISS → [First Contact] → All Stations (Flooding)
                </div>
                <div className="text-[10px] text-secondary mt-1 font-mono">
                  Message will be sent to first available station, then flooded to all neighbors, then 2-hop neighbors, until all stations receive it.
                </div>
              </>
            ) : (
              <>
                <div className="font-mono">
                  ISS → {stations.find(s => s.id === destinationStation)?.name || destinationStation}
                </div>
                <div className="text-[10px] text-secondary mt-1 font-mono">
                  Message will be queued and sent to the first available ground station, then routed via shortest path.
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};

export default MessageReply;

