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
    // Always reset state when message changes
    setReassembledPayload(null);
    setFragmentStatus(null);
    
    if (selectedMessage) {
      loadFragmentStatus();
      // Check if message already has decrypted payload
      if (selectedMessage.decrypted_payload) {
        setReassembledPayload(selectedMessage.decrypted_payload);
      }
    }
  }, [selectedMessage?.bundle_id]); // Use bundle_id to detect actual message changes

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
      <Card className="p-4">
        <div className="mb-3">
          <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
            <Package className="w-3 h-3" />
            MESSAGE REASSEMBLY
          </h3>
        </div>
        <div className="text-[11px] text-secondary text-center py-8">
          Select a message to view fragment status
        </div>
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
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary flex items-center gap-2">
          <Package className="w-3 h-3" />
          MESSAGE REASSEMBLY
        </h3>
        <div className="text-[11px] font-mono text-secondary mt-1">
          Bundle: {selectedMessage.bundle_id_short} from {selectedMessage.source_station.toUpperCase()}
        </div>
      </div>
      <div className="space-y-4">
        {/* Message Info */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge className={`${getPriorityColor(selectedMessage.priority)} text-[10px] px-1.5 py-0`}>
              {selectedMessage.priority}
            </Badge>
            <span className="text-[11px] font-mono text-secondary">
              Source: {selectedMessage.source_station.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Fragment Progress */}
        {selectedMessage.fragments_total > 1 ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-secondary">Fragment Progress</span>
              <span className="font-mono">
                {selectedMessage.fragments_received} / {selectedMessage.fragments_total}
              </span>
            </div>
            <Progress value={progress} className="h-2" />
            {!selectedMessage.is_complete && (
              <div className="text-[10px] text-amber-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Waiting for remaining fragments...
              </div>
            )}
          </div>
        ) : (
          <div className="text-[11px] text-secondary">
            Single bundle (no fragmentation)
          </div>
        )}

        {/* Fragment List */}
        {fragmentStatus && fragmentStatus.fragments && (
          <div className="space-y-1">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-secondary mb-2">Fragments</div>
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {fragmentStatus.fragments.map((frag: any) => (
                <div
                  key={frag.fragment_number}
                  className={`flex items-center justify-between p-2 rounded border text-[11px] ${
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
                  <span className="text-[10px] text-secondary">
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
            className="w-full h-8 text-[11px] font-mono"
            variant="outline"
          >
            {reassembling ? (
              <>
                <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                Reassembling...
              </>
            ) : (
              <>
                <Package className="w-3 h-3 mr-2" />
                Reassemble & Decrypt
              </>
            )}
          </Button>
        )}

        {/* Decrypted Message */}
        {reassembledPayload && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-semibold tracking-wider uppercase text-secondary">
              <Lock className="w-3 h-3 text-success" />
              Decrypted Message
            </div>
            <div className="p-3 bg-background/50 rounded border border-border font-mono text-[11px] text-terminal-text whitespace-pre-wrap">
              {reassembledPayload}
            </div>
            {selectedMessage.reassembled_at && (
              <div className="text-[10px] text-secondary font-mono">
                Reassembled at: {new Date(selectedMessage.reassembled_at).toLocaleString()}
              </div>
            )}
          </div>
        )}

        {/* Auto-reassemble indicator */}
        {selectedMessage.is_complete && reassembledPayload && (
          <div className="text-[10px] text-success flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            Message fully reassembled and decrypted
          </div>
        )}
      </div>
    </Card>
  );
};

export default MessageReassembly;

