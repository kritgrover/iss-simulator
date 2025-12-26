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
  const [priority, setPriority] = useState<"EXPEDITED" | "NORMAL" | "BULK">("NORMAL");
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
    const success = await sendReply(destinationStation, message, priority);
    setSending(false);

    if (success) {
      toast({
        title: "Message Sent",
        description: `Reply sent to ${DEFAULT_STATIONS.find(s => s.id === destinationStation)?.name || destinationStation}`,
      });
      setMessage("");
      setDestinationStation("");
      setPriority("NORMAL");
    } else {
      toast({
        title: "Error",
        description: "Failed to send reply. Please try again.",
        variant: "destructive",
      });
    }
  };

  const getPriorityColor = (p: string) => {
    switch (p) {
      case "EXPEDITED":
        return "text-red-400";
      case "NORMAL":
        return "text-cyan-400";
      case "BULK":
        return "text-gray-400";
      default:
        return "text-gray-400";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Radio className="w-4 h-4" />
          Send Reply
        </CardTitle>
        <CardDescription>
          Compose and send a message to a ground station
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Destination Station Selector */}
        <div className="space-y-2">
          <Label htmlFor="destination">Destination Station</Label>
          <Select value={destinationStation} onValueChange={setDestinationStation}>
            <SelectTrigger id="destination">
              <SelectValue placeholder="Select a station" />
            </SelectTrigger>
            <SelectContent>
              {DEFAULT_STATIONS.map((station) => (
                <SelectItem key={station.id} value={station.id}>
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

        {/* Priority Selector */}
        <div className="space-y-2">
          <Label htmlFor="priority">Priority</Label>
          <Select value={priority} onValueChange={(v) => setPriority(v as typeof priority)}>
            <SelectTrigger id="priority">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="EXPEDITED">
                <span className={getPriorityColor("EXPEDITED")}>EXPEDITED</span>
              </SelectItem>
              <SelectItem value="NORMAL">
                <span className={getPriorityColor("NORMAL")}>NORMAL</span>
              </SelectItem>
              <SelectItem value="BULK">
                <span className={getPriorityColor("BULK")}>BULK</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Message Composer */}
        <div className="space-y-2">
          <Label htmlFor="message">Message</Label>
          <Textarea
            id="message"
            placeholder="Type your message here..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={6}
            className="font-mono text-sm"
          />
          <div className="text-xs text-secondary">
            {message.length} characters
          </div>
        </div>

        {/* Send Button */}
        <Button
          onClick={handleSend}
          disabled={sending || !destinationStation || !message.trim()}
          className="w-full"
        >
          {sending ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Sending...
            </>
          ) : (
            <>
              <Send className="w-4 h-4 mr-2" />
              Send Reply
            </>
          )}
        </Button>

        {/* Route Preview */}
        {destinationStation && (
          <div className="text-xs text-secondary p-2 bg-background/50 rounded border border-border">
            <div className="font-semibold mb-1">Route Preview:</div>
            <div className="font-mono">
              ISS → {DEFAULT_STATIONS.find(s => s.id === destinationStation)?.name || destinationStation}
            </div>
            <div className="text-xs text-secondary mt-1">
              Routing will be calculated automatically based on visible stations
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MessageReply;

