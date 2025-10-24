import { useState, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { DTNBundle } from '@/types/dtnBundle';

interface ISSPosition {
  latitude: number;
  longitude: number;
  altitude_km: number;
  velocity_kmps: number;
}

interface OrbitalPathPoint {
  lat: number;
  lon: number;
  alt: number;
}

interface LookAngles {
  azimuth: number;
  elevation: number;
  range_km: number;
  is_visible: boolean;
}

interface PassWindow {
  aos_time: string | null;
  los_time: string | null;
  duration_minutes: number;
  is_in_pass: boolean;
}

interface StationData {
  id: string;
  name: string;
  lat: number;
  lon: number;
  look_angles: LookAngles;
  is_visible: boolean;
  next_pass_minutes: number;
  next_pass_time: string | null;
  pass_window: PassWindow | null;
}

interface OrbitalParameters {
  active_station: string;
  latitude: number;
  longitude: number;
  altitude_km: number;
  velocity_kmps: number;
  azimuth: number;
  elevation: number;
  range_km: number;
  next_pass_time: string | null;
  next_pass_minutes: number;
  aos_time: string | null;
  los_time: string | null;
  pass_duration_minutes: number;
  is_in_pass: boolean;
}

interface LinkStatus {
  signal_strength_dbm: number;
  connection_state: "ACQUIRED" | "DEGRADED" | "IDLE";
  latency_ms: number;
  doppler_shift_khz: number;
  snr_db: number;
  range_km: number;
}

interface LinkBudgetHistoryPoint {
  timestamp: string;
  snr_db: number;
  signal_strength_dbm: number;
}

interface CustodyAck {
  type: "custody_ack";
  bundle_id: string;
  bundle_id_short: string;
  from_station: string;
  to_station: string;
  ack_type: "custody_accepted" | "delivered";
  timestamp: string;
}

interface ActiveTransmission {
  bundle_id: string;
  bundle_id_short: string;
  from_station: string;
  to_station: string;
  progress_percent: number;
  bytes_transmitted: number;
  size_bytes: number;
  data_rate_kbps: number;
  time_remaining_sec: number;
}

export interface OrbitalData {
  timestamp: string;
  iss_position: ISSPosition;
  orbital_path: OrbitalPathPoint[];
  stations: StationData[];
  active_station_id: string | null;
  visible_stations_count: number;
  min_elevation: number;
  orbital_parameters: OrbitalParameters | null;
  link_status: LinkStatus | null;
  link_budget_history: LinkBudgetHistoryPoint[];
  dtn_queues: Record<string, DTNBundle[]>;
  custody_acks: CustodyAck[];
  active_transmissions: ActiveTransmission[];
}

export const useOrbitalTracking = () => {
  const WS_URL = 'ws://localhost:8000/ws/orbital_tracking';
  const { isConnected, lastMessage } = useWebSocket(WS_URL);
  
  const [orbitalData, setOrbitalData] = useState<OrbitalData | null>(null);

  useEffect(() => {
    if (lastMessage) {
      if (lastMessage.type === 'orbital_update') {
        setOrbitalData(lastMessage);
      } else if (lastMessage.type === 'connection') {
        console.log('✅ Orbital tracking connected');
        console.log('📡 Tracking', lastMessage.stations?.length || 0, 'stations');
      }
    }
  }, [lastMessage]);

  return {
    isConnected,
    orbitalData
  };
};