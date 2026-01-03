import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useISSMessages } from "@/hooks/useISSMessages";
import { DEFAULT_STATIONS } from "@/types/groundStation";
import { Send, Radio, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "@/hooks/use-toast";

const MessageReply = () => {
  const { sendReply } = useISSMessages();
  const [destinationStation, setDestinationStation] = useState<string>("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!destinationStation) {
      toast({
        title: "Error",
        description: "Please select a destination station",
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
    const success = await sendReply(destinationStation, message, "EXPEDITED");
    setSending(false);

    if (success) {
      toast({
        title: "Message Sent",
        description: `Reply sent to ${DEFAULT_STATIONS.find(s => s.id === destinationStation)?.name || destinationStation}`,
      });
      setMessage("");
      setDestinationStation("");
    } else {
      toast({
        title: "Error",
        description: "Failed to send reply. Please try again.",
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
        {/* Destination Station Selector */}
        <div className="space-y-2">
          <Label htmlFor="destination" className="text-[10px] font-semibold tracking-wider uppercase text-secondary">
            Destination Station
          </Label>
          <Select value={destinationStation} onValueChange={setDestinationStation}>
            <SelectTrigger id="destination" className="h-8 text-[11px] font-mono">
              <SelectValue placeholder="Select a station" />
            </SelectTrigger>
            <SelectContent>
              {DEFAULT_STATIONS.map((station) => (
                <SelectItem key={station.id} value={station.id} className="text-[11px] font-mono">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: station.color }}
                    />
                    {station.name}
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
          disabled={sending || !destinationStation || !message.trim()}
          className="w-full h-8 text-[11px] font-mono"
        >
          {sending ? (
            <>
              <Loader2 className="w-3 h-3 mr-2 animate-spin" />
              Sending...
            </>
          ) : (
            <>
              <Send className="w-3 h-3 mr-2" />
              Send Reply
            </>
          )}
        </Button>

        {/* Route Preview */}
        {destinationStation && (
          <div className="text-[11px] text-secondary p-2 bg-background/50 rounded border border-border">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary mb-1">Route Preview</div>
            <div className="font-mono">
              ISS → {DEFAULT_STATIONS.find(s => s.id === destinationStation)?.name || destinationStation}
            </div>
            <div className="text-[10px] text-secondary mt-1 font-mono">
              Routing will be calculated automatically based on visible stations
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default MessageReply;

