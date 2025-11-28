export interface DTNBundle {
  bundle_id: string;
  bundle_id_short: string;
  source_station: string;
  destination_station: string;
  payload: string;
  priority: "EXPEDITED" | "NORMAL" | "BULK";
  status: "QUEUED" | "TRANSMITTING" | "WAITING_ACK" | "DELIVERED" | "FORWARDED" | "EXPIRED";
  created_at: string;
  ttl_hours: number;
  current_custodian: string;
  forwarded_to: string | null;
  age_seconds: number;
  hops: string[];
  route: string[];
  delivered_at?: string | null;
  size_bytes: number;
  checksum: number;
}