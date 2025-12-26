import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useISSMessages, ISSMessage } from "@/hooks/useISSMessages";
import { Package, CheckCircle, Clock, RefreshCw, Lock } from "lucide-react";
import { useState, useEffect } from "react";

interface MessageReassemblyProps {
  selectedMessage: ISSMessage | null;
  onMessageSelected?: (message: ISSMessage) => void;
}

const MessageReassembly = ({ selectedMessage, onMessageSelected }: MessageReassemblyProps) => {
  const { messages, getFragmentStatus, reassembleMessage } = useISSMessages();
  const [fragmentStatus, setFragmentStatus] = useState<any>(null);
  const [reassembling, setReassembling] = useState(false);
  const [reassembledPayload, setReassembledPayload] = useState<string | null>(null);

  useEffect(() => {
    if (selectedMessage) {
      loadFragmentStatus();
      // Check if message already has decrypted payload
      if (selectedMessage.decrypted_payload) {
        setReassembledPayload(selectedMessage.decrypted_payload);
      }
    } else {
      setFragmentStatus(null);
      setReassembledPayload(null);
    }
  }, [selectedMessage]);

  const loadFragmentStatus = async () => {
    if (!selectedMessage) return;
    const bundleId = selectedMessage.parent_bundle_id || selectedMessage.bundle_id;
    const status = await getFragmentStatus(bundleId);
    setFragmentStatus(status);
  };

  const handleReassemble = async () => {
    if (!selectedMessage) return;
    setReassembling(true);
    const bundleId = selectedMessage.parent_bundle_id || selectedMessage.bundle_id;
    const result = await reassembleMessage(bundleId);
    if (result) {
      setReassembledPayload(result.decrypted_payload);
    }
    setReassembling(false);
    loadFragmentStatus();
  };

  if (!selectedMessage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="w-4 h-4" />
            Message Reassembly
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-secondary text-center py-8">
            Select a message to view fragment status
          </div>
        </CardContent>
      </Card>
    );
  }

  const bundleId = selectedMessage.parent_bundle_id || selectedMessage.bundle_id;
  const progress = selectedMessage.fragments_total > 0
    ? (selectedMessage.fragments_received / selectedMessage.fragments_total) * 100
    : 100;

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "EXPEDITED":
        return "bg-red-500/20 text-red-400 border-red-500/50";
      case "NORMAL":
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/50";
      case "BULK":
        return "bg-gray-500/20 text-gray-400 border-gray-500/50";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/50";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="w-4 h-4" />
          Message Reassembly
        </CardTitle>
        <CardDescription>
          Bundle: {selectedMessage.bundle_id_short} from {selectedMessage.source_station.toUpperCase()}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Message Info */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge className={getPriorityColor(selectedMessage.priority)}>
              {selectedMessage.priority}
            </Badge>
            <span className="text-xs text-secondary">
              Source: {selectedMessage.source_station.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Fragment Progress */}
        {selectedMessage.fragments_total > 1 ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-secondary">Fragment Progress</span>
              <span className="font-mono">
                {selectedMessage.fragments_received} / {selectedMessage.fragments_total}
              </span>
            </div>
            <Progress value={progress} className="h-2" />
            {!selectedMessage.is_complete && (
              <div className="text-xs text-amber-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Waiting for remaining fragments...
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-secondary">
            Single bundle (no fragmentation)
          </div>
        )}

        {/* Fragment List */}
        {fragmentStatus && fragmentStatus.fragments && (
          <div className="space-y-1">
            <div className="text-sm font-semibold mb-2">Fragments:</div>
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {fragmentStatus.fragments.map((frag: any) => (
                <div
                  key={frag.fragment_number}
                  className={`flex items-center justify-between p-2 rounded border text-xs ${
                    frag.status === "DELIVERED"
                      ? "bg-success/10 border-success/50"
                      : "bg-background/30 border-border"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {frag.status === "DELIVERED" ? (
                      <CheckCircle className="w-3 h-3 text-success" />
                    ) : (
                      <Clock className="w-3 h-3 text-amber-500" />
                    )}
                    <span className="font-mono">Fragment {frag.fragment_number}</span>
                  </div>
                  <span className="text-secondary">
                    {frag.status === "DELIVERED" ? "Received" : "Pending"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reassemble Button */}
        {selectedMessage.is_complete && !reassembledPayload && (
          <Button
            onClick={handleReassemble}
            disabled={reassembling}
            className="w-full"
            variant="outline"
          >
            {reassembling ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Reassembling...
              </>
            ) : (
              <>
                <Package className="w-4 h-4 mr-2" />
                Reassemble & Decrypt
              </>
            )}
          </Button>
        )}

        {/* Decrypted Message */}
        {reassembledPayload && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Lock className="w-4 h-4 text-success" />
              Decrypted Message:
            </div>
            <div className="p-3 bg-background/50 rounded border border-border font-mono text-sm text-terminal-text whitespace-pre-wrap">
              {reassembledPayload}
            </div>
            {selectedMessage.reassembled_at && (
              <div className="text-xs text-secondary">
                Reassembled at: {new Date(selectedMessage.reassembled_at).toLocaleString()}
              </div>
            )}
          </div>
        )}

        {/* Auto-reassemble indicator */}
        {selectedMessage.is_complete && reassembledPayload && (
          <div className="text-xs text-success flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            Message fully reassembled and decrypted
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MessageReassembly;

