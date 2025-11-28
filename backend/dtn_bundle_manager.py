import uuid
import zlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from database import DatabaseManager

class BundlePriority(str, Enum):
    EXPEDITED = "EXPEDITED"  # Red
    NORMAL = "NORMAL"        # Cyan
    BULK = "BULK"            # Gray

class BundleStatus(str, Enum):
    QUEUED = "QUEUED"
    TRANSMITTING = "TRANSMITTING"
    WAITING_ACK = "WAITING_ACK"
    DELIVERED = "DELIVERED"
    FORWARDED = "FORWARDED"
    EXPIRED = "EXPIRED"

@dataclass
class DTNBundle:
    bundle_id: str
    source_station: str
    destination_station: str  # "ISS" or station name
    payload: str
    priority: BundlePriority
    created_at: datetime
    ttl_hours: int = 24
    status: BundleStatus = BundleStatus.QUEUED
    current_custodian: str = ""
    forwarded_to: Optional[str] = None
    delivered_at: Optional[datetime] = None
    hops: List[str] = field(default_factory=list)  # Actual path taken
    route: List[str] = field(default_factory=list)  # Planned route (source -> ... -> destination)
    size_bytes: int = 0
    checksum: int = 0
    
    def __post_init__(self):
        if self.size_bytes == 0:
            # Calculate size based on payload + headers
            payload_size = len(self.payload.encode('utf-8'))
            header_overhead = 200  # DTN header overhead (100-500 bytes typical)
            self.size_bytes = payload_size + header_overhead
        
        # Calculate checksum if not already set
        if self.checksum == 0:
            self.checksum = self.calculate_checksum()
    
    def calculate_checksum(self) -> int:
        """Calculate CRC32 checksum of bundle payload"""
        data = self.payload.encode('utf-8')
        return zlib.crc32(data) & 0xffffffff  # Ensure non-negative 32-bit
    
    def verify_checksum(self, received_checksum: int) -> bool:
        """Verify if received checksum matches calculated checksum"""
        return self.checksum == received_checksum
    
    def is_expired(self) -> bool:
        """Check if bundle has exceeded TTL"""
        age = datetime.now(timezone.utc) - self.created_at
        return age > timedelta(hours=self.ttl_hours)
    
    def to_dict(self) -> Dict:
        return {
            "bundle_id": self.bundle_id,
            "bundle_id_short": self.bundle_id[:8],
            "source_station": self.source_station,
            "destination_station": self.destination_station,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "ttl_hours": self.ttl_hours,
            "current_custodian": self.current_custodian,
            "forwarded_to": self.forwarded_to,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "hops": self.hops,
            "route": self.route,
            "age_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds(),
            "size_bytes": self.size_bytes,
            "checksum": self.checksum
        }

@dataclass
class BundleTransmission:
    """Track ongoing bundle transmission"""
    bundle_id: str
    from_station: str
    to_station: str
    started_at: datetime
    size_bytes: int
    data_rate_bps: float
    expected_completion: datetime
    bytes_transmitted: float = 0
    retransmission_count: int = 0
    max_retries: int = 5
    
    def is_complete(self) -> bool:
        return self.bytes_transmitted >= self.size_bytes
    
    def progress_percent(self) -> float:
        return min(100.0, (self.bytes_transmitted / self.size_bytes) * 100)
    
    def estimated_time_remaining(self) -> float:
        """Return estimated seconds remaining"""
        remaining_bytes = self.size_bytes - self.bytes_transmitted
        if self.data_rate_bps > 0:
            return remaining_bytes / (self.data_rate_bps / 8)
        return 0
    
    def can_retry(self) -> bool:
        """Check if we can retry this transmission"""
        return self.retransmission_count < self.max_retries

@dataclass
class PendingAcknowledgment:
    """Track bundles waiting for ACK/NAK"""
    bundle_id: str
    from_station: str
    to_station: str
    transmitted_at: datetime
    timeout_seconds: float = 30.0
    retransmission_count: int = 0
    max_retries: int = 5
    data_rate_bps: float = 0.0
    
    def is_timed_out(self) -> bool:
        """Check if acknowledgment timeout has expired"""
        elapsed = (datetime.now(timezone.utc) - self.transmitted_at).total_seconds()
        return elapsed >= self.timeout_seconds
    
    def can_retry(self) -> bool:
        """Check if we can retry this transmission"""
        return self.retransmission_count < self.max_retries

class DTNBundleManager:
    """Manages DTN bundles across ground station network"""
    
    # Constants
    ACK_TIMEOUT_SECONDS = 30.0
    MAX_RETRIES = 5
    
    def __init__(self, stations: List[Dict], mesh_connections: Optional[List[Tuple[str, str]]] = None):
        self.stations = {s["id"]: s["name"] for s in stations}
        self.bundles: Dict[str, DTNBundle] = {}
        self.station_queues: Dict[str, List[str]] = {sid: [] for sid in self.stations.keys()}
        self.pending_acks: List[Dict] = []
        self.active_transmissions: Dict[str, BundleTransmission] = {}
        self.pending_acknowledgments: Dict[str, PendingAcknowledgment] = {}  # Bundles waiting for ACK/NAK
        self.delivered_bundles: List[str] = []
        self.failed_bundles: List[str] = []  # Track failed bundles (max retries exceeded, aborted, etc.)
        self.bundle_retry_counts: Dict[str, int] = {}  # Track retry counts for bundles
        self.bundle_failure_reasons: Dict[str, str] = {}  # Track why bundles failed
        self.mesh_connections = mesh_connections or []  # List of (station1, station2) tuples
        self.db_manager = DatabaseManager()
        
        print(f"📦 DTN Bundle Manager initialized with {len(self.stations)} stations")
        print(f"   ACK timeout: {self.ACK_TIMEOUT_SECONDS}s, Max retries: {self.MAX_RETRIES}")
        
        # Load persistent state
        self._load_state()
    
    def _load_state(self):
        """Load bundle state from database"""
        saved_bundles = self.db_manager.get_all_bundles()
        loaded_count = 0
        
        for bundle_data in saved_bundles:
            try:
                # Reconstruct bundle object
                priority_enum = BundlePriority.NORMAL
                if bundle_data['priority'] == "EXPEDITED":
                    priority_enum = BundlePriority.EXPEDITED
                elif bundle_data['priority'] == "BULK":
                    priority_enum = BundlePriority.BULK
                
                # Parse timestamps
                created_at = datetime.fromisoformat(bundle_data['created_at'])
                delivered_at = datetime.fromisoformat(bundle_data['delivered_at']) if bundle_data.get('delivered_at') else None
                
                status_enum = BundleStatus.QUEUED
                try:
                    status_enum = BundleStatus(bundle_data['status'])
                except ValueError:
                    pass
                
                bundle = DTNBundle(
                    bundle_id=bundle_data['bundle_id'],
                    source_station=bundle_data['source_station'],
                    destination_station=bundle_data['destination_station'],
                    payload=bundle_data['payload'],
                    priority=priority_enum,
                    created_at=created_at,
                    ttl_hours=bundle_data['ttl_hours'],
                    status=status_enum,
                    current_custodian=bundle_data['current_custodian'],
                    forwarded_to=bundle_data['forwarded_to'],
                    delivered_at=delivered_at,
                    hops=bundle_data.get('hops', []),
                    route=bundle_data.get('route', []),
                    size_bytes=bundle_data.get('size_bytes', 0),
                    checksum=bundle_data.get('checksum', 0)
                )
                
                self.bundles[bundle.bundle_id] = bundle
                
                # Restore into appropriate queues/lists
                if bundle.status == BundleStatus.DELIVERED:
                    self.delivered_bundles.append(bundle.bundle_id)
                elif bundle.status == BundleStatus.EXPIRED or bundle_data.get('failure_reason'):
                    self.failed_bundles.append(bundle.bundle_id)
                    if bundle_data.get('failure_reason'):
                        self.bundle_failure_reasons[bundle.bundle_id] = bundle_data['failure_reason']
                elif bundle.status in [BundleStatus.QUEUED, BundleStatus.WAITING_ACK]:
                    # Add to custodian's queue
                    custodian = bundle.current_custodian
                    if custodian and custodian in self.station_queues:
                        self.station_queues[custodian].append(bundle.bundle_id)
                
                loaded_count += 1
            except Exception as e:
                print(f"❌ Error loading bundle {bundle_data.get('bundle_id')}: {e}")
        
        # Sort queues
        for station_id in self.station_queues:
            self._sort_station_queue(station_id)
            
        if loaded_count > 0:
            print(f"📦 Restored {loaded_count} bundles from persistent storage")

    def find_route(self, from_station: str, to_station: str, 
                   stations_data: List[Dict], visited: Optional[List[str]] = None) -> Optional[List[str]]:
        """
        Find a route from source to destination using mesh connections and next pass times.
        Uses BFS with preference for stations with sooner next passes.
        
        Args:
            from_station: Source station ID
            to_station: Destination station ID (can be "ISS" for final destination)
            stations_data: List of station data dicts with next_pass_minutes
            visited: Already visited stations (for loop prevention)
            
        Returns:
            List of station IDs from source to destination station (or station that can reach ISS).
            Route does NOT include "ISS" - ISS forwarding is handled separately.
        """
        if visited is None:
            visited = []
        
        # Build adjacency list from mesh connections
        adjacency = {}
        for conn in self.mesh_connections:
            station1, station2 = conn
            if station1 not in adjacency:
                adjacency[station1] = []
            if station2 not in adjacency:
                adjacency[station2] = []
            adjacency[station1].append(station2)
            adjacency[station2].append(station1)
        
        # If no mesh connections, fall back to direct connection or all stations
        if not adjacency:
            for station_id in self.stations.keys():
                adjacency[station_id] = [s for s in self.stations.keys() if s != station_id]
        
        # If destination is ISS, find route to a station that can see ISS
        # Otherwise, route to the specified station
        target_station = to_station
        if to_station == "ISS":
            station_lookup = {s["id"]: s for s in stations_data}
            
            # stations currently tracking ISS (is_visible = True)
            currently_visible = [
                sid for sid in self.stations.keys() 
                if sid != from_station and 
                sid not in visited and
                station_lookup.get(sid, {}).get("is_visible", False)
            ]
            
            if currently_visible:
                # If multiple stations are visible, prefer the one with highest elevation
                currently_visible.sort(
                    key=lambda sid: station_lookup.get(sid, {}).get("look_angles", {}).get("elevation", -999),
                    reverse=True
                )
                target_station = currently_visible[0]
            else:
                # stations with upcoming passes
                upcoming_pass_stations = [
                    sid for sid in self.stations.keys() 
                    if sid != from_station and 
                    sid not in visited and
                    station_lookup.get(sid, {}).get("next_pass_minutes", 999999) > 0
                ]
                if not upcoming_pass_stations:
                    return None  # No station can see ISS
                # Prefer stations with sooner passes
                upcoming_pass_stations.sort(key=lambda sid: station_lookup.get(sid, {}).get("next_pass_minutes", 999999))
                target_station = upcoming_pass_stations[0]  # Route to station with soonest pass
        
        # BFS to find route
        from collections import deque
        queue = deque([(from_station, [from_station])])
        visited_set = set(visited + [from_station])
        
        # Create lookup for station data
        station_lookup = {s["id"]: s for s in stations_data}
        
        while queue:
            current, path = queue.popleft()
            
            # Check if we reached target station
            if current == target_station:
                return path
            
            # Get neighbors
            neighbors = adjacency.get(current, [])
            
            # Sort neighbors by next pass time (sooner passes first)
            def get_next_pass(station_id: str) -> float:
                station = station_lookup.get(station_id, {})
                return station.get("next_pass_minutes", 999999)
            
            neighbors.sort(key=get_next_pass)
            
            for neighbor in neighbors:
                if neighbor not in visited_set:
                    visited_set.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None  # No route found
    
    def create_bundle(self, source_station: str, destination: str, 
                     payload: str, priority: str = "NORMAL", ttl_hours: int = 24) -> DTNBundle:
        """Create a new DTN bundle"""
        bundle_id = str(uuid.uuid4())
        
        priority_enum = BundlePriority.NORMAL
        if priority.upper() == "EXPEDITED":
            priority_enum = BundlePriority.EXPEDITED
        elif priority.upper() == "BULK":
            priority_enum = BundlePriority.BULK
        
        bundle = DTNBundle(
            bundle_id=bundle_id,
            source_station=source_station,
            destination_station=destination,
            payload=payload,
            priority=priority_enum,
            created_at=datetime.now(timezone.utc),
            ttl_hours=ttl_hours,
            current_custodian=source_station,
            hops=[source_station]
        )
        
        self.bundles[bundle_id] = bundle
        self.station_queues[source_station].append(bundle_id)
        
        self._sort_station_queue(source_station)
        
        # Save to DB
        self.db_manager.save_bundle(bundle.to_dict())
        
        # Log checksum calculation
        print(f"📦 Created bundle {bundle_id[:8]} at {source_station}: {payload[:30]}... (size: {bundle.size_bytes} bytes, priority: {priority_enum.value})")
        print(f"   Checksum calculated: 0x{bundle.checksum:08x} (CRC32)")
        return bundle
    
    def _sort_station_queue(self, station_id: str):
        """
        Sort a station's queue by priority
        EXPEDITED (0) > NORMAL (1) > BULK (2)
        """
        queue_ids = self.station_queues.get(station_id, [])
        
        if not queue_ids:
            return
        
        # Get bundle objects
        bundles_with_ids = [
            (bundle_id, self.bundles.get(bundle_id))
            for bundle_id in queue_ids
            if bundle_id in self.bundles
        ]
        
        # Sort by priority
        priority_order = {"EXPEDITED": 0, "NORMAL": 1, "BULK": 2}
        bundles_with_ids.sort(
            key=lambda x: priority_order.get(x[1].priority.value, 99) if x[1] else 99
        )
        
        # Update the queue with sorted IDs
        self.station_queues[station_id] = [bundle_id for bundle_id, _ in bundles_with_ids]
    
    def start_transmission(self, bundle_id: str, from_station: str, 
                      to_station: str, data_rate_bps: float, 
                      retransmission_count: Optional[int] = None) -> Optional[BundleTransmission]:
        """
        Start transmitting a bundle
        Returns transmission object if started, None if can't start
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # Check if already transmitting
        if bundle_id in self.active_transmissions:
            return self.active_transmissions[bundle_id]
        
        # Prevent forwarding loops
        if to_station in bundle.hops:
            print(f"⚠️  Bundle {bundle_id[:8]} loop detected! Not forwarding {from_station} → {to_station}")
            return None
        
        # Get retry count if not provided (check stored retry count)
        if retransmission_count is None:
            retransmission_count = self.bundle_retry_counts.get(bundle_id, 0)
        else:
            self.bundle_retry_counts[bundle_id] = retransmission_count
        
        bundle.forwarded_to = to_station
        
        # Calculate transmission time
        transmission_time_sec = bundle.size_bytes / (data_rate_bps / 8)
        
        now = datetime.now(timezone.utc)
        expected_completion = now + timedelta(seconds=transmission_time_sec)
        
        # Create transmission record
        transmission = BundleTransmission(
            bundle_id=bundle_id,
            from_station=from_station,
            to_station=to_station,
            started_at=now,
            size_bytes=bundle.size_bytes,
            data_rate_bps=data_rate_bps,
            expected_completion=expected_completion,
            bytes_transmitted=0,
            retransmission_count=retransmission_count
        )
        
        # Mark bundle as transmitting
        bundle.status = BundleStatus.TRANSMITTING
        self.active_transmissions[bundle_id] = transmission
        
        # Update DB
        self.db_manager.update_bundle_status(
            bundle_id=bundle_id,
            status=BundleStatus.TRANSMITTING.value,
            forwarded_to=to_station
        )
        
        # Clear retry count tracking (it's now in the transmission)
        if bundle_id in self.bundle_retry_counts:
            del self.bundle_retry_counts[bundle_id]
        
        retry_msg = f" (retry {retransmission_count + 1})" if retransmission_count > 0 else ""
        print(f"📡 Started transmitting bundle {bundle_id[:8]}{retry_msg}")
        print(f"   Route: {from_station} → {to_station}")
        print(f"   Size: {bundle.size_bytes} bytes ({bundle.size_bytes/1024:.2f} KB)")
        print(f"   Data Rate: {data_rate_bps/1000:.1f} kbps")
        print(f"   Estimated Duration: {transmission_time_sec:.1f}s")
        print(f"   Checksum being sent: 0x{bundle.checksum:08x} (CRC32)")
        
        return transmission
    
    def update_transmissions(self, delta_time_sec: float, 
                           station_contact_states: Dict[str, bool]) -> List[Tuple[str, float]]:
        """
        Update all active transmissions
        station_contact_states: dict of {station_id: is_visible}
        Returns list of tuples: (bundle_id, data_rate_bps) for completed transmissions
        """
        completed = []
        
        for bundle_id, transmission in list(self.active_transmissions.items()):
            # Check if contact is maintained
            from_station = transmission.from_station
            is_contact_maintained = station_contact_states.get(from_station, False)
            
            if not is_contact_maintained and transmission.to_station == "ISS":
                # Contact lost! Abort transmission to ISS
                elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                bundle = self.bundles[bundle_id]
                
                transmission.retransmission_count += 1
                
                # Check if we can retry
                if transmission.can_retry():
                    print(f"⚠️  Transmission of {bundle_id[:8]} ABORTED after {elapsed:.1f}s (contact lost)")
                    print(f"   Progress: {transmission.progress_percent():.1f}% ({transmission.bytes_transmitted:.0f}/{transmission.size_bytes} bytes)")
                    print(f"   Will retry when contact restored (attempt {transmission.retransmission_count}/{transmission.max_retries})")
                    bundle.status = BundleStatus.QUEUED 
                    # Update DB
                    self.db_manager.update_bundle_status(bundle_id=bundle_id, status=BundleStatus.QUEUED.value)
                    self.bundle_retry_counts[bundle_id] = transmission.retransmission_count
                else:
                    # Max retries exceeded - mark as failed
                    print(f"❌ Transmission of {bundle_id[:8]} FAILED - max retries exceeded after contact loss")
                    print(f"   Progress: {transmission.progress_percent():.1f}% ({transmission.bytes_transmitted:.0f}/{transmission.size_bytes} bytes)")
                    print(f"   Total retry attempts: {transmission.retransmission_count}")
                    bundle.status = BundleStatus.EXPIRED
                    self._mark_bundle_failed(bundle_id, "contact_lost_max_retries")
                
                del self.active_transmissions[bundle_id]
                continue
            
            # update bytes transmitted
            bytes_this_tick = (transmission.data_rate_bps / 8) * delta_time_sec
            transmission.bytes_transmitted = min(
                transmission.size_bytes,
                transmission.bytes_transmitted + bytes_this_tick
            )
            
            # check if complete
            if transmission.is_complete():
                completed.append((bundle_id, transmission.data_rate_bps))
                elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                print(f"   Size: {transmission.size_bytes} bytes")
                print(f"   Actual Duration: {elapsed:.2f}s")
                print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                
                del self.active_transmissions[bundle_id]
        
        return completed
    
    def complete_transmission(self, bundle_id: str, data_rate_bps: float) -> Optional[Dict]:
        """
        Complete a bundle transmission - receiver verifies checksum and sends ACK/NAK
        Returns ACK or NAK message to send back to sender
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # Get transmission destination from bundle.forwarded_to
        to_station = bundle.forwarded_to
        from_station = bundle.current_custodian
        
        # Check if transmission was already completed
        if not to_station:
            # Check if bundle is already delivered or in a final state
            if bundle.status == BundleStatus.DELIVERED:
                return None

            # Check if bundle is waiting for ACK
            if bundle.status == BundleStatus.WAITING_ACK:
                return None

            # If bundle is in a transmitting state but no forwarded_to, it might be a race condition
            # Try to get destination from active transmission
            if bundle_id in self.active_transmissions:
                to_station = self.active_transmissions[bundle_id].to_station
                if to_station:
                    bundle.forwarded_to = to_station  # Restore it
                else:
                    print(f"⚠️  Cannot complete transmission for {bundle_id[:8]} - no destination set")
                    return None
            else:
                # No active transmission and no forwarded_to - likely already completed
                return None
        
        # Receiver verifies checksum of received bundle
        received_checksum = bundle.calculate_checksum()
        expected_checksum = bundle.checksum
        
        # Log checksum verification
        print(f"🔍 Bundle {bundle_id[:8]} received at {to_station} - verifying checksum...")
        print(f"   Expected checksum (from bundle): 0x{expected_checksum:08x}")
        print(f"   Received checksum (calculated): 0x{received_checksum:08x}")
        
        # Verify checksums match
        checksum_valid = (received_checksum == expected_checksum)
        
        if checksum_valid:
            # send ACK
            print(f"   ✅ Checksums MATCH - bundle integrity verified")
            print(f"✅ Bundle {bundle_id[:8]} received at {to_station}, checksum valid - sending ACK")
            
            ack = {
                "type": "ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "ack_type": "delivered" if to_station == "ISS" else "custody_accepted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checksum": bundle.checksum
            }
            
            # Queue ACK to be sent back to sender
            self.queue_ack(ack)
            
            # Note: Bundle status is not changed here - it remains with sender until ACK is processed            
            return ack
        else:
            # Checksum mismatch - send NAK
            print(f"   ❌ Checksums DO NOT MATCH - bundle may be corrupted!")
            print(f"   Difference: 0x{abs(expected_checksum - received_checksum):08x}")
            print(f"❌ Bundle {bundle_id[:8]} received at {to_station}, checksum INVALID!")
            print(f"   Expected: 0x{expected_checksum:08x}, Received: 0x{received_checksum:08x}")
            print(f"   Sending NAK to {from_station} - requesting retransmission")
            
            nak = {
                "type": "nak",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "checksum_mismatch",
                "expected_checksum": expected_checksum,
                "received_checksum": received_checksum
            }
            
            # Queue NAK to be sent back to sender
            self.queue_ack(nak)
            
            return nak
    
    def process_ack(self, bundle_id: str, ack_data: Dict) -> bool:
        """
        Process an ACK received from receiver
        Returns True if bundle was successfully acknowledged, False otherwise
        """
        if bundle_id not in self.bundles:
            return False
        
        bundle = self.bundles[bundle_id]
        from_station = ack_data.get("from_station")  # Receiver
        to_station = ack_data.get("to_station")  # Sender (us)
        
        # check if we're the sender
        if bundle.current_custodian != to_station:
            print(f"⚠️  ACK for {bundle_id[:8]} received but we're not the sender")
            return False
        
        # Log ACK received with checksum verification
        ack_checksum = ack_data.get("checksum")
        if ack_checksum is not None:
            print(f"📥 ACK received for bundle {bundle_id[:8]} from {from_station}")
            print(f"   Checksum in ACK: 0x{ack_checksum:08x}")
            print(f"   Our bundle checksum: 0x{bundle.checksum:08x}")
            if ack_checksum == bundle.checksum:
                print(f"   ✅ Checksum verified - ACK is valid")
            else:
                print(f"   ⚠️  Checksum mismatch in ACK (shouldn't happen)")
        
        # Remove from pending acknowledgments
        if bundle_id in self.pending_acknowledgments:
            del self.pending_acknowledgments[bundle_id]
        
        # Process based on destination
        if ack_data.get("ack_type") == "delivered":
            # Delivered to ISS!
            bundle.status = BundleStatus.DELIVERED
            bundle.delivered_at = datetime.now(timezone.utc)
            bundle.hops.append(from_station)
            bundle.forwarded_to = None
            
            # Update DB
            self.db_manager.update_bundle_status(
                bundle_id=bundle_id,
                status=BundleStatus.DELIVERED.value,
                delivered_at=bundle.delivered_at.isoformat(),
                forwarded_to=None
            )
            self.db_manager.update_bundle_hops(bundle_id, bundle.hops)
            
            # Calculate total delivery time
            total_time = (bundle.delivered_at - bundle.created_at).total_seconds()
            
            # Remove from sender's queue
            if bundle_id in self.station_queues[to_station]:
                self.station_queues[to_station].remove(bundle_id)
            
            self.delivered_bundles.append(bundle_id)
            if len(self.delivered_bundles) > 10:
                self.delivered_bundles.pop(0)
            
            print(f"🎯 Bundle {bundle_id[:8]} ACK received - DELIVERED to {from_station}")
            print(f"   Total delivery time: {total_time:.1f}s ({total_time/60:.1f} min)")
            print(f"   Complete path: {' → '.join(bundle.hops)}")
            
        else:
            # Custody accepted by another station
            bundle.status = BundleStatus.QUEUED
            previous_custodian = bundle.current_custodian
            bundle.current_custodian = from_station
            bundle.hops.append(from_station)
            bundle.forwarded_to = None
            
            # Update DB
            self.db_manager.update_bundle_status(
                bundle_id=bundle_id,
                status=BundleStatus.QUEUED.value,
                current_custodian=from_station,
                forwarded_to=None
            )
            self.db_manager.update_bundle_hops(bundle_id, bundle.hops)
            
            # Move from sender's queue to receiver's queue
            if bundle_id in self.station_queues[to_station]:
                self.station_queues[to_station].remove(bundle_id)
            self.station_queues[from_station].append(bundle_id)
            
            # Sort the destination queue after adding bundle
            self._sort_station_queue(from_station)
            
            print(f"📨 Bundle {bundle_id[:8]} ACK received - custody transferred to {from_station.upper()}")
            print(f"   Path so far: {' → '.join(bundle.hops)}")
            
            # If route exists and we're not at final destination, prepare for next hop forwarding
            if bundle.route and len(bundle.route) > 0:
                current_index = len(bundle.hops) - 1  
                if current_index < len(bundle.route) - 1:
                    # Not at final destination yet - route will be used for forwarding
                    next_hop = bundle.route[current_index + 1]
                    print(f"   Route: {' → '.join(bundle.route)}")
                    print(f"   Next hop: {next_hop}")
        
        return True
    
    def get_next_hop_from_route(self, bundle_id: str) -> Optional[str]:
        """
        Get the next hop station from the bundle's route.
        Returns None if route is complete or doesn't exist.
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # If no route, return None
        if not bundle.route or len(bundle.route) == 0:
            return None
        
        # Find current position in route
        current_custodian = bundle.current_custodian
        
        # find index of current custodian in route
        try:
            current_index = bundle.route.index(current_custodian)
        except ValueError:
            # Current custodian not in route - might be at start
            if bundle.route[0] == bundle.source_station:
                current_index = 0
            else:
                return None  # Route doesn't match current state
        
        # Check if there's a next hop
        if current_index < len(bundle.route) - 1:
            next_hop = bundle.route[current_index + 1]
            # Don't forward to a station we've already visited
            if next_hop not in bundle.hops:
                return next_hop
        
        return None  # Route complete or no valid next hop
    
    def process_nak(self, bundle_id: str, nak_data: Dict) -> bool:
        """
        Process a NAK received from receiver (checksum mismatch)
        Returns True if retransmission should be attempted, False if max retries exceeded
        """
        if bundle_id not in self.bundles:
            return False
        
        bundle = self.bundles[bundle_id]
        from_station = nak_data.get("from_station")  # Receiver
        to_station = nak_data.get("to_station")  # Sender (us)
        
        # check if we're the sender
        if bundle.current_custodian != to_station:
            print(f"⚠️  NAK for {bundle_id[:8]} received but we're not the sender")
            return False
        
        if bundle_id not in self.pending_acknowledgments:
            # This can happen when NAK arrives but retry was already handled via direct failure path
            print(f"⚠️  NAK for {bundle_id[:8]} but no pending acknowledgment found - retry already handled")
            return False
        
        pending_ack = self.pending_acknowledgments[bundle_id]
        pending_ack.retransmission_count += 1
        
        # Log NAK with checksum details
        expected_checksum = nak_data.get("expected_checksum")
        received_checksum = nak_data.get("received_checksum")
        
        print(f"📥 NAK received for bundle {bundle_id[:8]} from {from_station}")
        print(f"   Reason: {nak_data.get('reason', 'unknown')}")
        if expected_checksum is not None and received_checksum is not None:
            print(f"   Expected checksum: 0x{expected_checksum:08x}")
            print(f"   Received checksum: 0x{received_checksum:08x}")
            print(f"   Our bundle checksum: 0x{bundle.checksum:08x}")
        print(f"❌ Bundle {bundle_id[:8]} NAK received from {from_station} (checksum mismatch)")
        print(f"   Retry attempt: {pending_ack.retransmission_count}/{pending_ack.max_retries}")
        
        if pending_ack.can_retry():
            # Store retry count for when transmission starts
            self.bundle_retry_counts[bundle_id] = pending_ack.retransmission_count
            
            # Remove from pending, will be retransmitted
            del self.pending_acknowledgments[bundle_id]
            
            # Reset bundle status and prepare for retransmission
            bundle.status = BundleStatus.QUEUED
            bundle.forwarded_to = None
            
            # Update DB
            self.db_manager.update_bundle_status(
                bundle_id=bundle_id,
                status=BundleStatus.QUEUED.value,
                forwarded_to=None
            )
            
            print(f"🔄 Scheduling retransmission of {bundle_id[:8]} to {from_station}")
            return True
        else:
            # Max retries exceeded
            print(f"❌ Bundle {bundle_id[:8]} FAILED - max retries exceeded (checksum mismatch)")
            print(f"   Total retry attempts: {pending_ack.retransmission_count}")
            del self.pending_acknowledgments[bundle_id]
            bundle.status = BundleStatus.EXPIRED
            self._mark_bundle_failed(bundle_id, "checksum_mismatch_max_retries")
            # Remove from queue
            if bundle_id in self.station_queues[to_station]:
                self.station_queues[to_station].remove(bundle_id)
            return False
    
    def check_timeouts(self, station_contact_states: Dict[str, bool]) -> List[Tuple[str, int, float]]:
        """
        Check for timed-out pending acknowledgments and retransmit if possible
        Returns list of tuples: (bundle_id, retry_count, data_rate_bps) for retransmitted bundles
        """
        retransmitted = []
        now = datetime.now(timezone.utc)
        
        for bundle_id, pending_ack in list(self.pending_acknowledgments.items()):
            if pending_ack.is_timed_out():
                print(f"⏰ Bundle {bundle_id[:8]} ACK timeout (>{pending_ack.timeout_seconds}s)")
                
                pending_ack.retransmission_count += 1
                print(f"   Retry attempt: {pending_ack.retransmission_count}/{pending_ack.max_retries}")
                
                if pending_ack.can_retry():
                    # Check if contact is still available for retransmission
                    from_station = pending_ack.from_station
                    is_contact_available = True
                    
                    if pending_ack.to_station == "ISS":
                        is_contact_available = station_contact_states.get(from_station, False)
                    
                    if is_contact_available:
                        # Retransmit - preserve retry count
                        retry_count = pending_ack.retransmission_count
                        print(f"🔄 Retransmitting bundle {bundle_id[:8]} to {pending_ack.to_station} (attempt {retry_count})")
                        del self.pending_acknowledgments[bundle_id]
                        
                        # Reset bundle status and prepare for retransmission
                        if bundle_id in self.bundles:
                            bundle = self.bundles[bundle_id]
                            bundle.status = BundleStatus.QUEUED
                            bundle.forwarded_to = None
                            
                            # Update DB
                            self.db_manager.update_bundle_status(
                                bundle_id=bundle_id,
                                status=BundleStatus.QUEUED.value,
                                forwarded_to=None
                            )
                            
                            # Store retry count for when transmission starts
                            self.bundle_retry_counts[bundle_id] = retry_count
                        
                        retransmitted.append((bundle_id, retry_count, pending_ack.data_rate_bps))
                    else:
                        # Contact lost, keep waiting (don't count as retry yet)
                        print(f"   Contact lost, will retry when contact restored")
                        pending_ack.retransmission_count -= 1  # Don't count this as a retry
                        pending_ack.transmitted_at = now  # Reset timeout
                else:
                    # Max retries exceeded
                    print(f"❌ Bundle {bundle_id[:8]} FAILED - max retries exceeded (ACK timeout)")
                    print(f"   Total retry attempts: {pending_ack.retransmission_count}")
                    del self.pending_acknowledgments[bundle_id]
                    if bundle_id in self.bundles:
                        bundle = self.bundles[bundle_id]
                        bundle.status = BundleStatus.EXPIRED
                        self._mark_bundle_failed(bundle_id, "ack_timeout_max_retries")
                        # Remove from queue
                        if bundle_id in self.station_queues[pending_ack.from_station]:
                            self.station_queues[pending_ack.from_station].remove(bundle_id)
        
        return retransmitted
    
    def get_delivered_bundles(self) -> List[Dict]:
        """Get recently delivered bundles for history"""
        bundles = []
        for bundle_id in reversed(self.delivered_bundles):  # Most recent first
            if bundle_id in self.bundles:
                bundles.append(self.bundles[bundle_id].to_dict())
        return bundles
    
    def _mark_bundle_failed(self, bundle_id: str, reason: str) -> None:
        """Mark a bundle as failed and track it"""
        if bundle_id not in self.failed_bundles:
            self.failed_bundles.append(bundle_id)
            # Keep only last 50 failed bundles
            if len(self.failed_bundles) > 50:
                self.failed_bundles.pop(0)
        self.bundle_failure_reasons[bundle_id] = reason
        
        # Update DB
        self.db_manager.update_bundle_status(
            bundle_id=bundle_id,
            status=BundleStatus.EXPIRED.value,
            failure_reason=reason
        )
    
    def get_failed_bundles(self) -> List[Dict]:
        """Get recently failed bundles for frontend"""
        bundles = []
        for bundle_id in reversed(self.failed_bundles):  # Most recent first
            if bundle_id in self.bundles:
                bundle_dict = self.bundles[bundle_id].to_dict()
                # Add failure reason
                bundle_dict["failure_reason"] = self.bundle_failure_reasons.get(bundle_id, "unknown")
                bundles.append(bundle_dict)
        return bundles
    
    def get_pending_acks(self) -> List[Dict]:
        """Get and clear pending ACKs"""
        acks = self.pending_acks.copy()
        self.pending_acks.clear()
        return acks
    
    def queue_ack(self, ack: Dict) -> None:
        """Queue an ACK to be sent"""
        if ack:
            self.pending_acks.append(ack)
    
    def get_station_queue(self, station_id: str) -> List[Dict]:
        """Get all bundles in a station's queue"""
        bundle_ids = self.station_queues.get(station_id, [])
        bundles = []
        
        for bid in bundle_ids:
            if bid in self.bundles:
                bundle = self.bundles[bid]
                if not bundle.is_expired():
                    bundles.append(bundle.to_dict())
                else:
                    # Mark as expired
                    bundle.status = BundleStatus.EXPIRED
        
        # Sort by priority (expedited first)
        priority_order = {"EXPEDITED": 0, "NORMAL": 1, "BULK": 2}
        bundles.sort(key=lambda b: priority_order.get(b["priority"], 99))
        
        return bundles
    
    def get_all_queues(self) -> Dict[str, List[Dict]]:
        """Get queues for all stations"""
        return {
            station_id: self.get_station_queue(station_id)
            for station_id in self.stations.keys()
        }
    
    def get_active_transmissions(self) -> List[Dict]:
        """Get all active transmissions for frontend"""
        return [
            {
                "bundle_id": t.bundle_id,
                "bundle_id_short": t.bundle_id[:8],
                "from_station": t.from_station,
                "to_station": t.to_station,
                "progress_percent": t.progress_percent(),
                "bytes_transmitted": int(t.bytes_transmitted),
                "size_bytes": t.size_bytes,
                "data_rate_kbps": round(t.data_rate_bps / 1000, 1),
                "time_remaining_sec": round(t.estimated_time_remaining(), 1)
            }
            for t in self.active_transmissions.values()
        ]
    
    def process_contact(self, station_id: str, is_visible: bool, 
                       next_visible_station: Optional[str] = None,
                       data_rate_bps: float = 0):
        """
        Process bundles during contact opportunities - DEPRECATED
        This method is kept for compatibility but transmission management
        is now handled in main.py
        """
        pass
    
    def cleanup_expired(self):
        """Remove expired bundles from all queues"""
        for bundle_id, bundle in list(self.bundles.items()):
            if bundle.is_expired() and bundle.status != BundleStatus.DELIVERED:
                bundle.status = BundleStatus.EXPIRED
                
                # Update DB
                self.db_manager.update_bundle_status(bundle_id=bundle_id, status=BundleStatus.EXPIRED.value)
                
                # Remove from station queue
                for queue in self.station_queues.values():
                    if bundle_id in queue:
                        queue.remove(bundle_id)
                # Mark as failed if not already tracked
                if bundle_id not in self.failed_bundles:
                    self._mark_bundle_failed(bundle_id, "ttl_exceeded")
                print(f"❌ Bundle {bundle_id[:8]} FAILED - expired (TTL exceeded)")