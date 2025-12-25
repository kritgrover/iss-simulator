export interface SecurityBlock {
  block_type: string;
  security_target: string;
  security_source: string;
  security_result?: string;
}

export interface PayloadConfidentialityBlock extends SecurityBlock {
  encryption_method: string;
  key_id: string;
  iv: string;
}

export interface PayloadIntegrityBlock extends SecurityBlock {
  signature: string;
  signer: string;
}

export interface BundleAuthenticationBlock extends SecurityBlock {
  mac: string;
  key_id: string;
}

export interface DTNBundle {
  bundle_id: string;
  bundle_id_short: string;
  source_station: string;
  destination_station: string;
  payload: string; // Display hash (shortened)
  payload_hash?: string; // Full hash
  payload_hash_short?: string; // Short hash for display
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
  // Security blocks
  pcb?: PayloadConfidentialityBlock;
  pib?: PayloadIntegrityBlock;
  bab?: BundleAuthenticationBlock;
  // Fragmentation
  is_fragmented?: boolean;
  fragment_count?: number;
  fragment_number?: number;
}