import uuid
import zlib
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from database import DatabaseManager
from bsp_security import BSPSecurityManager, BundleAuthenticationBlock, PayloadConfidentialityBlock, PayloadIntegrityBlock
from bundle_fragmentation import BundleFragmentationManager, BundleFragment

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
    encrypted_payload: str  # Encrypted payload (base64)
    payload_hash: str  # Hash of encrypted payload for display
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
    # Security blocks
    pcb: Optional[PayloadConfidentialityBlock] = None  # Payload Confidentiality Block
    pib: Optional[PayloadIntegrityBlock] = None  # Payload Integrity Block
    bab: Optional[BundleAuthenticationBlock] = None  # Bundle Authentication Block (last applied)
    # Fragmentation
    is_fragmented: bool = False
    fragment_count: int = 1
    fragment_number: int = 0  # 0 if not fragmented, fragment index if fragmented
    
    def __post_init__(self):
        if self.size_bytes == 0:
            # Calculate size based on encrypted payload + headers + security blocks
            payload_size = len(self.encrypted_payload.encode('utf-8'))
            header_overhead = 200  # DTN header overhead
            security_overhead = 300  # Security blocks overhead (BAB, PCB, PIB)
            self.size_bytes = payload_size + header_overhead + security_overhead
        
        # Calculate checksum if not already set (on encrypted payload)
        if self.checksum == 0:
            self.checksum = self.calculate_checksum()
    
    def calculate_checksum(self) -> int:
        """Calculate CRC32 checksum of encrypted bundle payload"""
        data = self.encrypted_payload.encode('utf-8')
        return zlib.crc32(data) & 0xffffffff  # Ensure non-negative 32-bit
    
    def verify_checksum(self, received_checksum: int) -> bool:
        """Verify if received checksum matches calculated checksum"""
        return self.checksum == received_checksum
    
    def is_expired(self) -> bool:
        """Check if bundle has exceeded TTL"""
        age = datetime.now(timezone.utc) - self.created_at
        return age > timedelta(hours=self.ttl_hours)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API/DB - does NOT include decrypted payload"""
        return {
            "bundle_id": self.bundle_id,
            "bundle_id_short": self.bundle_id[:8],
            "source_station": self.source_station,
            "destination_station": self.destination_station,
            "payload": self.payload_hash[:16] + "...",  # Show only hash prefix for security
            "payload_hash": self.payload_hash,
            "payload_hash_short": self.payload_hash[:16],
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
            "checksum": self.checksum,
            "is_fragmented": self.is_fragmented,
            "fragment_count": self.fragment_count,
            "fragment_number": self.fragment_number,
            "pcb": self.pcb.to_dict() if self.pcb else None,
            "pib": self.pib.to_dict() if self.pib else None,
            "bab": self.bab.to_dict() if self.bab else None
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
        self.iss_queue: List[str] = []  # Special queue for bundles from ISS
        self.pending_acks: List[Dict] = []
        self.active_transmissions: Dict[str, BundleTransmission] = {}
        self.pending_acknowledgments: Dict[str, PendingAcknowledgment] = {}  # Bundles waiting for ACK/NAK
        self.delivered_bundles: List[str] = []
        self.failed_bundles: List[str] = []  # Track failed bundles (max retries exceeded, aborted, etc.)
        self.bundle_retry_counts: Dict[str, int] = {}  # Track retry counts for bundles
        self.bundle_failure_reasons: Dict[str, str] = {}  # Track why bundles failed
        self.mesh_connections = mesh_connections or []  # List of (station1, station2) tuples
        self.db_manager = DatabaseManager()
        
        # Broadcast tracking: bundle_id -> set of station_ids that have received it
        self.broadcast_received: Dict[str, set] = {}
        # Broadcast deliveries for display: track each station's receipt of broadcasts
        self.broadcast_deliveries: List[Dict] = []
        # Decrypted messages per station: station_id -> list of decrypted messages
        self.station_decrypted_messages: Dict[str, List[Dict]] = {sid: [] for sid in self.stations.keys()}
        
        # BSP Security and Fragmentation
        self.bsp_security = BSPSecurityManager()
        self.fragmentation_manager = BundleFragmentationManager()
        
        print(f"📦 DTN Bundle Manager initialized with {len(self.stations)} stations")
        print(f"   ACK timeout: {self.ACK_TIMEOUT_SECONDS}s, Max retries: {self.MAX_RETRIES}")
        print(f"   🔐 BSP Security enabled (BAB, PCB, PIB)")
        print(f"   📦 Bundle fragmentation enabled")
        
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
                
                # Handle encrypted payload (new format) or plaintext (legacy)
                encrypted_payload = bundle_data.get('encrypted_payload')
                payload_hash = bundle_data.get('payload_hash')
                
                if not encrypted_payload:
                    # Legacy bundle - payload is plaintext, need to encrypt it
                    # This shouldn't happen in normal operation, but handle gracefully
                    plaintext = bundle_data.get('payload', '')
                    if plaintext and not plaintext.startswith('encrypted:'):
                        # Encrypt legacy payload
                        try:
                            encrypted_payload, pcb = self.bsp_security.encrypt_payload(
                                plaintext, bundle_data['source_station']
                            )
                            payload_hash = self.bsp_security.get_payload_hash(encrypted_payload)
                            print(f"⚠️  Legacy bundle {bundle_data['bundle_id'][:8]} - encrypted on load")
                        except Exception as e:
                            print(f"❌ Error encrypting legacy bundle: {e}")
                            continue
                    else:
                        # Already encrypted or empty
                        encrypted_payload = plaintext
                        if not payload_hash:
                            payload_hash = self.bsp_security.get_payload_hash(encrypted_payload) if encrypted_payload else ""
                
                # Reconstruct security blocks
                pcb = None
                pib = None
                bab = None
                
                if bundle_data.get('pcb'):
                    pcb_data = bundle_data['pcb'] if isinstance(bundle_data['pcb'], dict) else json.loads(bundle_data['pcb'])
                    pcb = PayloadConfidentialityBlock(
                        security_target=pcb_data.get('security_target', 'payload'),
                        security_source=pcb_data.get('security_source', ''),
                        encryption_method=pcb_data.get('encryption_method', 'AES-256-CBC'),
                        key_id=pcb_data.get('key_id', ''),
                        iv=pcb_data.get('iv', '')
                    )
                
                if bundle_data.get('pib'):
                    pib_data = bundle_data['pib'] if isinstance(bundle_data['pib'], dict) else json.loads(bundle_data['pib'])
                    pib = PayloadIntegrityBlock(
                        security_target=pib_data.get('security_target', 'payload'),
                        security_source=pib_data.get('security_source', ''),
                        signature=pib_data.get('signature', ''),
                        signer=pib_data.get('signer', '')
                    )
                
                if bundle_data.get('bab'):
                    bab_data = bundle_data['bab'] if isinstance(bundle_data['bab'], dict) else json.loads(bundle_data['bab'])
                    bab = BundleAuthenticationBlock(
                        security_target=bab_data.get('security_target', ''),
                        security_source=bab_data.get('security_source', ''),
                        mac=bab_data.get('mac', ''),
                        key_id=bab_data.get('key_id', '')
                    )
                
                bundle = DTNBundle(
                    bundle_id=bundle_data['bundle_id'],
                    source_station=bundle_data['source_station'],
                    destination_station=bundle_data['destination_station'],
                    encrypted_payload=encrypted_payload,
                    payload_hash=payload_hash or self.bsp_security.get_payload_hash(encrypted_payload) if encrypted_payload else "",
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
                    checksum=bundle_data.get('checksum', 0),
                    pcb=pcb,
                    pib=pib,
                    bab=bab,
                    is_fragmented=bundle_data.get('is_fragmented', False),
                    fragment_count=bundle_data.get('fragment_count', 1),
                    fragment_number=bundle_data.get('fragment_number', 0)
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
                    if custodian and custodian.upper() == "ISS":
                        # Add to ISS queue
                        if bundle.bundle_id not in self.iss_queue:
                            self.iss_queue.append(bundle.bundle_id)
                    elif custodian and custodian in self.station_queues:
                        self.station_queues[custodian].append(bundle.bundle_id)
                
                loaded_count += 1
            except Exception as e:
                print(f"❌ Error loading bundle {bundle_data.get('bundle_id')}: {e}")
        
        # Sort queues
        for station_id in self.station_queues:
            self._sort_station_queue(station_id)
        
        # Sort ISS queue
        self._sort_iss_queue()
            
        if loaded_count > 0:
            print(f"📦 Restored {loaded_count} bundles from persistent storage")

    def find_route(self, from_station: str, to_station: str, 
                   stations_data: List[Dict], visited: Optional[List[str]] = None) -> Optional[List[str]]:
        """
        Find a route from source to destination using mesh connections and next pass times.
        Uses BFS with preference for stations with sooner next passes.
        Supports ISS as source (reverse routing).
        
        Args:
            from_station: Source station ID (can be "ISS")
            to_station: Destination station ID (can be "ISS" for final destination)
            stations_data: List of station data dicts with next_pass_minutes
            visited: Already visited stations (for loop prevention)
            
        Returns:
            List of station IDs from source to destination station (or station that can reach ISS).
            Route does NOT include "ISS" when destination is ISS - ISS forwarding is handled separately.
            Route DOES include "ISS" when source is ISS (reverse routing).
        """
        if visited is None:
            visited = []
        
        # Handle ISS as source (reverse routing)
        if from_station.upper() == "ISS":
            station_lookup = {s["id"]: s for s in stations_data}
            
            # Find currently visible station from ISS
            currently_visible = [
                sid for sid in self.stations.keys() 
                if sid not in visited and
                station_lookup.get(sid, {}).get("is_visible", False)
            ]
            
            if currently_visible:
                # If destination is visible, route: ISS → destination
                if to_station in currently_visible:
                    return ["ISS", to_station]
                
                # Prefer station with highest elevation
                currently_visible.sort(
                    key=lambda sid: station_lookup.get(sid, {}).get("look_angles", {}).get("elevation", -999),
                    reverse=True
                )
                first_hop = currently_visible[0]
            else:
                # Find station with soonest pass
                upcoming_pass_stations = [
                    sid for sid in self.stations.keys() 
                    if sid not in visited and
                    station_lookup.get(sid, {}).get("next_pass_minutes", 999999) > 0
                ]
                if not upcoming_pass_stations:
                    return None  # No station can see ISS
                upcoming_pass_stations.sort(key=lambda sid: station_lookup.get(sid, {}).get("next_pass_minutes", 999999))
                first_hop = upcoming_pass_stations[0]
            
            # If destination is first hop, done
            if first_hop == to_station:
                return ["ISS", to_station]
            
            # Find route from first hop to destination (recursive, but avoid ISS in visited)
            route_from_first = self.find_route(first_hop, to_station, stations_data, visited=["ISS"])
            if route_from_first:
                return ["ISS"] + route_from_first
            else:
                # Direct route if no mesh route found
                return ["ISS", first_hop, to_station] if first_hop != to_station else ["ISS", to_station]
        
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
                if (sid != from_station or from_station == sid) and # Allow current station
                (sid not in visited or sid == from_station) and
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
                    if (sid != from_station or from_station == sid) and # Allow current station
                    (sid not in visited or sid == from_station) and
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
        """
        Create a new DTN bundle with encryption and optional fragmentation
        Payload is encrypted and stored securely
        """
        bundle_id = str(uuid.uuid4())
        
        priority_enum = BundlePriority.NORMAL
        if priority.upper() == "EXPEDITED":
            priority_enum = BundlePriority.EXPEDITED
        elif priority.upper() == "BULK":
            priority_enum = BundlePriority.BULK
        
        try:
            # Step 1: Encrypt payload
            encrypted_payload, pcb = self.bsp_security.encrypt_payload(payload, source_station)
            payload_hash = self.bsp_security.get_payload_hash(encrypted_payload)
            payload_hash_short = self.bsp_security.get_payload_hash_short(encrypted_payload, 16)
            
            # Step 2: Create Payload Integrity Block (PIB)
            pib = self.bsp_security.create_pib(payload_hash, source_station)
            
            # Step 3: Check if fragmentation is needed
            payload_size = len(encrypted_payload.encode('utf-8'))
            is_fragmented = self.fragmentation_manager.should_fragment(payload_size)
            fragment_count = 1
            
            if is_fragmented:
                # Fragment the encrypted payload
                fragments = self.fragmentation_manager.fragment_bundle(
                    bundle_id, encrypted_payload, source_station
                )
                fragment_count = len(fragments)
                print(f"   📦 Bundle fragmented into {fragment_count} fragments")
                print(f"   Original size: {payload_size} bytes, Fragment size limit: {self.fragmentation_manager.MAX_FRAGMENT_SIZE} bytes")
                
                # Create a bundle for each fragment
                fragment_bundles = []
                for i, fragment in enumerate(fragments):
                    # Create bundle for this fragment
                    fragment_bundle = DTNBundle(
                        bundle_id=fragment.fragment_id,
                        source_station=source_station,
                        destination_station=destination,
                        encrypted_payload=fragment.payload,  # Only this fragment's payload
                        payload_hash=payload_hash,  # Same hash for all fragments (original payload)
                        priority=priority_enum,
                        created_at=datetime.now(timezone.utc),
                        ttl_hours=ttl_hours,
                        current_custodian=source_station,
                        hops=[source_station],
                        pcb=pcb,
                        pib=pib,
                        is_fragmented=True,
                        fragment_count=fragment_count,
                        fragment_number=fragment.fragment_number
                    )
                    
                    # Store fragment bundle
                    self.bundles[fragment.fragment_id] = fragment_bundle
                    
                    if source_station.upper() == "ISS":
                        self.iss_queue.append(fragment.fragment_id)
                    else:
                        self.station_queues[source_station].append(fragment.fragment_id)
                        
                    fragment_bundles.append(fragment_bundle)
                    
                    # Save to DB
                    fragment_dict = fragment_bundle.to_dict()
                    fragment_dict["encrypted_payload"] = fragment.payload
                    self.db_manager.save_bundle(fragment_dict)
                
                # Return the first fragment bundle (for API compatibility)
                bundle = fragment_bundles[0]
                print(f"   Created {fragment_count} fragment bundles (IDs: {', '.join([f[:8] for f in [fb.bundle_id for fb in fragment_bundles]])})")
            else:
                # Step 4: Create bundle (non-fragmented)
                bundle = DTNBundle(
                    bundle_id=bundle_id,
                    source_station=source_station,
                    destination_station=destination,
                    encrypted_payload=encrypted_payload,
                    payload_hash=payload_hash,
                    priority=priority_enum,
                    created_at=datetime.now(timezone.utc),
                    ttl_hours=ttl_hours,
                    current_custodian=source_station,
                    hops=[source_station],
                    pcb=pcb,
                    pib=pib,
                    is_fragmented=False,
                    fragment_count=1,
                    fragment_number=0
                )
                
                self.bundles[bundle_id] = bundle
                if source_station.upper() == "ISS":
                    self.iss_queue.append(bundle_id)
                else:
                    self.station_queues[source_station].append(bundle_id)
            
            if source_station.upper() == "ISS":
                self._sort_iss_queue()
            else:
                self._sort_station_queue(source_station)
            
            # Save to DB (encrypted payload stored) - only for non-fragmented bundles
            # Fragmented bundles are already saved above
            if not is_fragmented:
                bundle_dict = bundle.to_dict()
                bundle_dict["encrypted_payload"] = encrypted_payload  # Store encrypted in DB
                self.db_manager.save_bundle(bundle_dict)
            
            # Log bundle creation with security info
            if is_fragmented:
                print(f"📦 Created fragmented bundle {bundle_id[:8]} at {source_station}")
                print(f"   Payload hash: {payload_hash_short}... (encrypted)")
                print(f"   Total fragments: {fragment_count}, Fragment size: ~{bundle.size_bytes} bytes each")
                print(f"   Priority: {priority_enum.value}")
                print(f"   🔐 Security: PCB={pcb.encryption_method}, PIB=HMAC-SHA256")
            else:
                print(f"📦 Created bundle {bundle_id[:8]} at {source_station}")
                print(f"   Payload hash: {payload_hash_short}... (encrypted)")
                print(f"   Size: {bundle.size_bytes} bytes, Priority: {priority_enum.value}")
                print(f"   🔐 Security: PCB={pcb.encryption_method}, PIB=HMAC-SHA256")
                print(f"   Checksum: 0x{bundle.checksum:08x} (CRC32)")
            
            return bundle
            
        except Exception as e:
            print(f"❌ Error creating bundle: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
        Creates BAB for authentication between SA nodes
        Returns transmission object if started, None if can't start
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # For broadcast bundles, use composite key (bundle_id:to_station) to allow multiple simultaneous transmissions
        # For regular bundles, use bundle_id only
        is_broadcast = bundle.destination_station.upper() == "BROADCAST"
        transmission_key = f"{bundle_id}:{to_station}" if is_broadcast else bundle_id
        
        # Check if already transmitting this bundle to this destination
        if transmission_key in self.active_transmissions:
            return self.active_transmissions[transmission_key]
        
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
        
        # Create Bundle Authentication Block (BAB) for this hop
        # BAB must be the last header applied to a bundle
        if not bundle.bab or bundle.bab.security_source != from_station:
            bundle_dict = bundle.to_dict()
            bundle_dict["payload_hash"] = bundle.payload_hash
            bundle.bab = self.bsp_security.create_bab(bundle_dict, from_station, to_station)
            print(f"   🔐 BAB created for {from_station} → {to_station}")
        
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
        self.active_transmissions[transmission_key] = transmission
        
        # Update DB
        bundle_dict = bundle.to_dict()
        bundle_dict["encrypted_payload"] = bundle.encrypted_payload  # Store encrypted
        self.db_manager.save_bundle(bundle_dict)
        
        # Clear retry count tracking (it's now in the transmission)
        if bundle_id in self.bundle_retry_counts:
            del self.bundle_retry_counts[bundle_id]
        
        retry_msg = f" (retry {retransmission_count + 1})" if retransmission_count > 0 else ""
        print(f"📡 Started transmitting bundle {bundle_id[:8]}{retry_msg}")
        print(f"   Route: {from_station} → {to_station}")
        print(f"   Payload hash: {bundle.payload_hash[:16]}... (encrypted)")
        print(f"   Size: {bundle.size_bytes} bytes ({bundle.size_bytes/1024:.2f} KB)")
        print(f"   Data Rate: {data_rate_bps/1000:.1f} kbps")
        print(f"   Estimated Duration: {transmission_time_sec:.1f}s")
        print(f"   Checksum: 0x{bundle.checksum:08x} (CRC32)")
        
        return transmission
    
    def update_transmissions(self, delta_time_sec: float, 
                           station_contact_states: Dict[str, bool]) -> List[Tuple[str, float]]:
        """
        Update all active transmissions
        station_contact_states: dict of {station_id: is_visible}
        Returns list of tuples: (bundle_id, data_rate_bps) for completed transmissions
        """
        completed = []
        
        for transmission_key, transmission in list(self.active_transmissions.items()):
            # Extract bundle_id from key (handles both bundle_id and bundle_id:to_station formats)
            bundle_id = transmission_key.split(':')[0]
            
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
                
                del self.active_transmissions[transmission_key]
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
                
                del self.active_transmissions[transmission_key]
        
        return completed
    
    def complete_transmission(self, bundle_id: str, data_rate_bps: float) -> Optional[Dict]:
        """
        Complete a bundle transmission - receiver verifies security blocks and checksum
        Returns ACK or NAK message to send back to sender
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # Get transmission info from active transmission record (most reliable)
        # This tells us who sent it and where it's going
        # Check both bundle_id and composite keys (for broadcast)
        transmission = None
        for key in [bundle_id, f"{bundle_id}:{bundle.destination_station}"]:
            if key in self.active_transmissions:
                transmission = self.active_transmissions[key]
                break
        
        if transmission:
            from_station = transmission.from_station  # Actual sender
            to_station = transmission.to_station  # Actual receiver
            bundle.forwarded_to = to_station
        else:
            # Fallback to bundle state (shouldn't happen normally)
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

                print(f"⚠️  Cannot complete transmission for {bundle_id[:8]} - no active transmission and no destination set")
                return None
        
        # Security verification at intermediate node (SA node)
        print(f"🔍 Bundle {bundle_id[:8]} received at {to_station} - verifying security...")
        
        # Step 1: Verify Bundle Authentication Block (BAB) - required at all SA nodes
        security_valid = True
        security_failure_reason = None
        
        if bundle.bab:
            # Pass the correct to_station (receiver) for BAB verification
            # The BAB was created with from_station -> to_station, so we need to verify with the same parameters
            # Create bundle dict without BAB for verification (BAB shouldn't be in the message used for verification)
            bundle_dict_for_verification = bundle.to_dict()
            bundle_dict_for_verification["payload_hash"] = bundle.payload_hash  # Ensure payload_hash is included
            bab_valid = self.bsp_security.verify_bab(
                bundle_dict_for_verification, bundle.bab, from_station, to_station
            )
            if not bab_valid:
                security_valid = False
                security_failure_reason = "BAB verification failed"
                print(f"   ❌ BAB verification FAILED - bundle may be tampered!")
            else:
                print(f"   ✅ BAB verified - authenticity confirmed")
        else:
            # BAB is required by default security policy
            security_valid = False
            security_failure_reason = "Missing BAB (required by security policy)"
            print(f"   ❌ Missing BAB - security policy violation!")
        
        # Step 2: Verify Payload Integrity Block (PIB)
        if security_valid and bundle.pib:
            pib_valid = self.bsp_security.verify_pib(bundle.payload_hash, bundle.pib)
            if not pib_valid:
                security_valid = False
                security_failure_reason = "PIB verification failed"
                print(f"   ❌ PIB verification FAILED - payload integrity compromised!")
            else:
                print(f"   ✅ PIB verified - payload integrity confirmed")
        
        # Step 3: Verify checksum
        received_checksum = bundle.calculate_checksum()
        expected_checksum = bundle.checksum
        checksum_valid = (received_checksum == expected_checksum)
        
        print(f"   Checksum: Expected=0x{expected_checksum:08x}, Received=0x{received_checksum:08x}")
        
        # All verifications must pass
        if security_valid and checksum_valid:
            # Note: New BAB for next hop will be created in start_transmission() when forwarding begins
            # We don't know the next hop destination here, so we can't create it yet
            
            # Check if this is the final destination (ISS or the target ground station)
            is_final_destination = (
                to_station.upper() == "ISS" or 
                to_station.upper() == bundle.destination_station.upper()
            )
            
            print(f"✅ Bundle {bundle_id[:8]} received at {to_station}, all security checks passed - sending ACK")
            
            ack = {
                "type": "ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "ack_type": "delivered" if is_final_destination else "custody_accepted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checksum": bundle.checksum
            }
            
            # Queue ACK to be sent back to sender
            self.queue_ack(ack)
            
            return ack
        else:
            # Security or checksum failure - send NAK
            failure_reason = security_failure_reason or "checksum_mismatch"
            print(f"❌ Bundle {bundle_id[:8]} received at {to_station}, verification FAILED!")
            print(f"   Reason: {failure_reason}")
            print(f"   Sending NAK to {from_station} - requesting retransmission")
            
            nak = {
                "type": "nak",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": failure_reason,
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
        # For broadcasts, the key is composite
        composite_key = f"{bundle_id}:{from_station}"
        if composite_key in self.pending_acknowledgments:
            del self.pending_acknowledgments[composite_key]
        elif bundle_id in self.pending_acknowledgments:
            del self.pending_acknowledgments[bundle_id]
        
        # Process based on destination
        if ack_data.get("ack_type") == "delivered":
            # Delivered to final destination (ISS or target ground station)
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
            
            # Remove from sender's queue (handle ISS queue)
            if to_station.upper() == "ISS":
                if bundle_id in self.iss_queue:
                    self.iss_queue.remove(bundle_id)
            elif bundle_id in self.station_queues.get(to_station, []):
                self.station_queues[to_station].remove(bundle_id)
            
            self.delivered_bundles.append(bundle_id)
            if len(self.delivered_bundles) > 10:
                self.delivered_bundles.pop(0)
            
            # Auto-decrypt if delivered to a ground station (from ISS)
            if from_station.upper() != "ISS" and bundle.source_station.upper() == "ISS":
                # For non-fragmented bundles, decrypt immediately
                # For fragmented bundles, check if all fragments are delivered
                should_decrypt = False
                if not bundle.is_fragmented:
                    should_decrypt = True
                else:
                    fragment_status = self.get_fragment_status_for_station(bundle_id, from_station)
                    if fragment_status and fragment_status["is_complete"]:
                        should_decrypt = True
                
                if should_decrypt:
                    decrypted = self.decrypt_bundle_for_station(bundle_id, from_station)
                    if decrypted:
                        # Add to station's decrypted messages (avoid duplicates)
                        if from_station not in self.station_decrypted_messages:
                            self.station_decrypted_messages[from_station] = []
                        # Check if already decrypted
                        if not any(m["bundle_id"] == bundle_id for m in self.station_decrypted_messages[from_station]):
                            self.station_decrypted_messages[from_station].append(decrypted)
                            # Keep only last 20 messages per station
                            if len(self.station_decrypted_messages[from_station]) > 20:
                                self.station_decrypted_messages[from_station].pop(0)
                            print(f"🔓 Bundle {bundle_id[:8]} decrypted for {from_station.upper()}")
            
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
            
            # Handle broadcast bundles - mark as received AND record for display
            if bundle.destination_station.upper() == "BROADCAST":
                self.mark_broadcast_received(bundle_id, from_station)  # Receiver
                self.mark_broadcast_received(bundle_id, to_station)    # Sender
                # Record delivery for this station's interface display
                self.broadcast_deliveries.append({
                    "bundle_id": bundle_id,
                    "bundle_id_short": bundle_id[:8],
                    "station_id": from_station,
                    "delivered_at": datetime.now(timezone.utc).isoformat(),
                    "payload_hash": bundle.payload_hash,
                    "source": bundle.source_station,
                    "priority": bundle.priority.value
                })
                # Keep only last 50 broadcast deliveries
                if len(self.broadcast_deliveries) > 50:
                    self.broadcast_deliveries.pop(0)
            
            # Update DB
            self.db_manager.update_bundle_status(
                bundle_id=bundle_id,
                status=BundleStatus.QUEUED.value,
                current_custodian=from_station,
                forwarded_to=None
            )
            self.db_manager.update_bundle_hops(bundle_id, bundle.hops)
            
            # Handle ISS queue (if bundle was from ISS)
            if to_station.upper() == "ISS":
                if bundle_id in self.iss_queue:
                    self.iss_queue.remove(bundle_id)
            
            # Move from sender's queue to receiver's queue (if not ISS)
            if to_station.upper() != "ISS":
                if bundle_id in self.station_queues.get(to_station, []):
                    self.station_queues[to_station].remove(bundle_id)
            
            # For broadcast bundles, only add to queue if there are unreceived neighbors
            if bundle.destination_station.upper() == "BROADCAST":
                unreceived_neighbors = self.get_broadcast_unreceived_neighbors(bundle_id, from_station)
                if unreceived_neighbors and from_station.upper() != "ISS" and from_station in self.station_queues:
                    self.station_queues[from_station].append(bundle_id)
                    self._sort_station_queue(from_station)
                    print(f"📡 Bundle {bundle_id[:8]} ACK received - BROADCAST received at {from_station.upper()}, will flood to {len(unreceived_neighbors)} neighbor(s)")
                else:
                    # No unreceived neighbors - this station is the end of the line for this broadcast
                    print(f"📡 Bundle {bundle_id[:8]} ACK received - BROADCAST received at {from_station.upper()} (no more neighbors to flood)")
            elif from_station.upper() != "ISS" and from_station in self.station_queues:
                self.station_queues[from_station].append(bundle_id)
                # Sort the destination queue after adding bundle
                self._sort_station_queue(from_station)
            
            if bundle.destination_station.upper() != "BROADCAST":
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
        
        # For broadcasts, the key is composite
        composite_key = f"{bundle_id}:{from_station}"
        pending_ack_key = composite_key if composite_key in self.pending_acknowledgments else bundle_id
        
        if pending_ack_key not in self.pending_acknowledgments:
            # This can happen when NAK arrives but retry was already handled via direct failure path
            print(f"⚠️  NAK for {bundle_id[:8]} but no pending acknowledgment found - retry already handled")
            return False
        
        pending_ack = self.pending_acknowledgments[pending_ack_key]
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
            del self.pending_acknowledgments[pending_ack_key]
            
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
            del self.pending_acknowledgments[pending_ack_key]
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
        
        for pending_key, pending_ack in list(self.pending_acknowledgments.items()):
            # For broadcasts, key is composite "bundle_id:to_station", extract actual bundle_id
            actual_bundle_id = pending_key.split(':')[0] if ':' in pending_key else pending_key
            
            if pending_ack.is_timed_out():
                print(f"⏰ Bundle {actual_bundle_id[:8]} ACK timeout (>{pending_ack.timeout_seconds}s)")
                
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
                        print(f"🔄 Retransmitting bundle {actual_bundle_id[:8]} to {pending_ack.to_station} (attempt {retry_count})")
                        del self.pending_acknowledgments[pending_key]
                        
                        # Reset bundle status and prepare for retransmission
                        if actual_bundle_id in self.bundles:
                            bundle = self.bundles[actual_bundle_id]
                            bundle.status = BundleStatus.QUEUED
                            bundle.forwarded_to = None
                            
                            # Update DB
                            self.db_manager.update_bundle_status(
                                bundle_id=actual_bundle_id,
                                status=BundleStatus.QUEUED.value,
                                forwarded_to=None
                            )
                            
                            # Store retry count for when transmission starts
                            self.bundle_retry_counts[actual_bundle_id] = retry_count
                        
                        retransmitted.append((actual_bundle_id, retry_count, pending_ack.data_rate_bps))
                    else:
                        # Contact lost, keep waiting (don't count as retry yet)
                        print(f"   Contact lost, will retry when contact restored")
                        pending_ack.retransmission_count -= 1  # Don't count this as a retry
                        pending_ack.transmitted_at = now  # Reset timeout
                else:
                    # Max retries exceeded
                    print(f"❌ Bundle {actual_bundle_id[:8]} FAILED - max retries exceeded (ACK timeout)")
                    print(f"   Total retry attempts: {pending_ack.retransmission_count}")
                    del self.pending_acknowledgments[pending_key]
                    if actual_bundle_id in self.bundles:
                        bundle = self.bundles[actual_bundle_id]
                        bundle.status = BundleStatus.EXPIRED
                        self._mark_bundle_failed(actual_bundle_id, "ack_timeout_max_retries")
                        # Remove from queue
                        if actual_bundle_id in self.station_queues.get(pending_ack.from_station, []):
                            self.station_queues[pending_ack.from_station].remove(actual_bundle_id)
        
        return retransmitted
    
    def get_delivered_bundles(self) -> List[Dict]:
        """Get recently delivered bundles for history"""
        bundles = []
        for bundle_id in reversed(self.delivered_bundles):  # Most recent first
            if bundle_id in self.bundles:
                bundles.append(self.bundles[bundle_id].to_dict())
        return bundles
    
    def get_broadcast_deliveries(self) -> List[Dict]:
        """Get broadcast deliveries for all stations (most recent first)"""
        return list(reversed(self.broadcast_deliveries))
    
    def get_station_decrypted_messages(self, station_id: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Get decrypted messages for station(s). If station_id provided, returns only that station's messages."""
        if station_id:
            return {station_id: self.station_decrypted_messages.get(station_id, [])}
        return self.station_decrypted_messages.copy()
    
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
    
    def cleanup_expired(self):
        """Remove expired bundles from all queues"""
        for bundle_id, bundle in list(self.bundles.items()):
            # Skip bundles that are already delivered or expired
            if bundle.is_expired() and bundle.status not in [BundleStatus.DELIVERED, BundleStatus.EXPIRED]:
                bundle.status = BundleStatus.EXPIRED
                
                # Update DB
                self.db_manager.update_bundle_status(bundle_id=bundle_id, status=BundleStatus.EXPIRED.value)
                
                # Remove from station queues
                for queue in self.station_queues.values():
                    if bundle_id in queue:
                        queue.remove(bundle_id)
                
                # Remove from ISS queue too
                if bundle_id in self.iss_queue:
                    self.iss_queue.remove(bundle_id)
                
                # Mark as failed if not already tracked
                if bundle_id not in self.failed_bundles:
                    self._mark_bundle_failed(bundle_id, "ttl_exceeded")
                print(f"❌ Bundle {bundle_id[:8]} FAILED - expired (TTL exceeded)")
    
    def get_iss_delivered_bundles(self) -> List[Dict]:
        """Get all bundles delivered to ISS with fragment status"""
        iss_bundles = []
        
        # Get all delivered bundles
        for bundle_id in self.delivered_bundles:
            if bundle_id in self.bundles:
                bundle = self.bundles[bundle_id]
                # Only include bundles delivered to ISS
                if bundle.destination_station.upper() == "ISS" and bundle.status == BundleStatus.DELIVERED:
                    bundle_dict = bundle.to_dict()
                    
                    # Check if this is a fragment
                    if bundle.is_fragmented:
                        # Get parent bundle ID (first part of fragment_id before "-frag-")
                        parent_id = bundle_id.split("-frag-")[0] if "-frag-" in bundle_id else bundle_id
                        
                        # Count fragments for this parent
                        fragment_count = 0
                        fragments_received = 0
                        for bid, b in self.bundles.items():
                            if b.destination_station.upper() == "ISS" and b.status == BundleStatus.DELIVERED:
                                if b.is_fragmented:
                                    frag_parent = bid.split("-frag-")[0] if "-frag-" in bid else bid
                                    if frag_parent == parent_id:
                                        fragment_count = max(fragment_count, b.fragment_count)
                                        fragments_received += 1
                        
                        bundle_dict["parent_bundle_id"] = parent_id
                        bundle_dict["fragments_received"] = fragments_received
                        bundle_dict["fragments_total"] = fragment_count
                        bundle_dict["is_complete"] = fragments_received == fragment_count
                    else:
                        bundle_dict["parent_bundle_id"] = bundle_id
                        bundle_dict["fragments_received"] = 1
                        bundle_dict["fragments_total"] = 1
                        bundle_dict["is_complete"] = True
                    
                    iss_bundles.append(bundle_dict)
        
        # Sort by delivered_at (most recent first)
        iss_bundles.sort(key=lambda b: b.get("delivered_at", ""), reverse=True)
        return iss_bundles
    
    def get_fragment_status(self, bundle_id: str) -> Optional[Dict]:
        """Get fragment status for a bundle (works with parent_bundle_id for fragmented bundles)"""
        # Check if this is a fragment ID or parent ID
        if "-frag-" in bundle_id:
            parent_id = bundle_id.split("-frag-")[0]
        else:
            parent_id = bundle_id
        
        # Find all fragments for this parent
        fragments = []
        fragment_count = 0
        
        for bid, bundle in self.bundles.items():
            if bundle.destination_station.upper() == "ISS":
                if bundle.is_fragmented:
                    frag_parent = bid.split("-frag-")[0] if "-frag-" in bid else bid
                    if frag_parent == parent_id:
                        fragment_count = max(fragment_count, bundle.fragment_count)
                        fragments.append({
                            "fragment_number": bundle.fragment_number,
                            "fragment_id": bid,
                            "status": "DELIVERED" if bundle.status == BundleStatus.DELIVERED else "PENDING",
                            "delivered_at": bundle.delivered_at.isoformat() if bundle.delivered_at else None
                        })
                elif not bundle.is_fragmented and bid == parent_id:
                    # Non-fragmented bundle
                    fragments.append({
                        "fragment_number": 0,
                        "fragment_id": bid,
                        "status": "DELIVERED" if bundle.status == BundleStatus.DELIVERED else "PENDING",
                        "delivered_at": bundle.delivered_at.isoformat() if bundle.delivered_at else None
                    })
                    fragment_count = 1
        
        if not fragments:
            return None
        
        fragments.sort(key=lambda f: f["fragment_number"])
        is_complete = len([f for f in fragments if f["status"] == "DELIVERED"]) == fragment_count
        
        return {
            "bundle_id": parent_id,
            "fragments": fragments,
            "fragments_received": len([f for f in fragments if f["status"] == "DELIVERED"]),
            "fragments_total": fragment_count,
            "is_complete": is_complete
        }
    
    def reassemble_and_decrypt_bundle(self, bundle_id: str) -> Optional[Dict]:
        """
        Reassemble fragments and decrypt message for ISS
        Returns dict with decrypted payload or None if incomplete
        """
        # Get parent bundle ID
        if "-frag-" in bundle_id:
            parent_id = bundle_id.split("-frag-")[0]
        else:
            parent_id = bundle_id
        
        # Check fragment status
        fragment_status = self.get_fragment_status(parent_id)
        if not fragment_status or not fragment_status["is_complete"]:
            return None
        
        # Collect all fragment bundles
        fragment_bundles = []
        for bid, bundle in self.bundles.items():
            if bundle.destination_station.upper() == "ISS" and bundle.status == BundleStatus.DELIVERED:
                if bundle.is_fragmented:
                    frag_parent = bid.split("-frag-")[0] if "-frag-" in bid else bid
                    if frag_parent == parent_id:
                        fragment_bundles.append((bundle.fragment_number, bundle))
                elif not bundle.is_fragmented and bid == parent_id:
                    fragment_bundles.append((0, bundle))
        
        if not fragment_bundles:
            return None
        
        # Sort by fragment number
        fragment_bundles.sort(key=lambda x: x[0])
        
        # Reassemble encrypted payload
        encrypted_payload_parts = []
        source_station = None
        pcb = None
        
        for frag_num, bundle in fragment_bundles:
            encrypted_payload_parts.append(bundle.encrypted_payload)
            if source_station is None:
                source_station = bundle.source_station
                pcb = bundle.pcb
        
        reassembled_encrypted = ''.join(encrypted_payload_parts)
        
        # Decrypt
        if not pcb or not source_station:
            return None
        
        try:
            decrypted_payload = self.bsp_security.decrypt_payload(reassembled_encrypted, pcb, source_station)
            
            return {
                "bundle_id": parent_id,
                "decrypted_payload": decrypted_payload,
                "source_station": source_station,
                "reassembled_at": datetime.now(timezone.utc).isoformat(),
                "fragments_count": len(fragment_bundles)
            }
        except Exception as e:
            print(f"❌ Error decrypting bundle {parent_id[:8]}: {e}")
            return None
    
    def decrypt_bundle_for_station(self, bundle_id: str, station_id: str) -> Optional[Dict]:
        """
        Reassemble fragments and decrypt message for a ground station
        Returns dict with decrypted payload or None if incomplete
        """
        # Get parent bundle ID
        if "-frag-" in bundle_id:
            parent_id = bundle_id.split("-frag-")[0]
        else:
            parent_id = bundle_id
        
        # Check if bundle exists and is delivered to this station
        if parent_id not in self.bundles:
            return None
        
        bundle = self.bundles[parent_id]
        if bundle.destination_station.upper() != station_id.upper():
            return None
        
        # Check fragment status for this destination
        fragment_status = self.get_fragment_status_for_station(parent_id, station_id)
        if not fragment_status or not fragment_status["is_complete"]:
            return None
        
        # Collect all fragment bundles
        fragment_bundles = []
        for bid, b in self.bundles.items():
            if b.destination_station.upper() == station_id.upper() and b.status == BundleStatus.DELIVERED:
                if b.is_fragmented:
                    frag_parent = bid.split("-frag-")[0] if "-frag-" in bid else bid
                    if frag_parent == parent_id:
                        fragment_bundles.append((b.fragment_number, b))
                elif not b.is_fragmented and bid == parent_id:
                    fragment_bundles.append((0, b))
        
        if not fragment_bundles:
            return None
        
        # Sort by fragment number
        fragment_bundles.sort(key=lambda x: x[0])
        
        # Reassemble encrypted payload
        encrypted_payload_parts = []
        source_station = None
        pcb = None
        
        for frag_num, b in fragment_bundles:
            encrypted_payload_parts.append(b.encrypted_payload)
            if source_station is None:
                source_station = b.source_station
                pcb = b.pcb
        
        reassembled_encrypted = ''.join(encrypted_payload_parts)
        
        # Decrypt
        if not pcb or not source_station:
            return None
        
        try:
            decrypted_payload = self.bsp_security.decrypt_payload(reassembled_encrypted, pcb, source_station)
            
            return {
                "bundle_id": parent_id,
                "decrypted_payload": decrypted_payload,
                "source_station": source_station,
                "destination_station": station_id,
                "reassembled_at": datetime.now(timezone.utc).isoformat(),
                "fragments_count": len(fragment_bundles)
            }
        except Exception as e:
            print(f"❌ Error decrypting bundle {parent_id[:8]} for {station_id}: {e}")
            return None
    
    def get_fragment_status_for_station(self, bundle_id: str, station_id: str) -> Optional[Dict]:
        """Get fragment status for a bundle delivered to a specific station"""
        # Check if this is a fragment ID or parent ID
        if "-frag-" in bundle_id:
            parent_id = bundle_id.split("-frag-")[0]
        else:
            parent_id = bundle_id
        
        # Find all fragments for this parent delivered to this station
        fragments = []
        fragment_count = 0
        
        for bid, bundle in self.bundles.items():
            if bundle.destination_station.upper() == station_id.upper():
                if bundle.is_fragmented:
                    frag_parent = bid.split("-frag-")[0] if "-frag-" in bid else bid
                    if frag_parent == parent_id:
                        fragment_count = max(fragment_count, bundle.fragment_count)
                        fragments.append({
                            "fragment_number": bundle.fragment_number,
                            "fragment_id": bid,
                            "status": "DELIVERED" if bundle.status == BundleStatus.DELIVERED else "PENDING",
                            "delivered_at": bundle.delivered_at.isoformat() if bundle.delivered_at else None
                        })
                elif not bundle.is_fragmented and bid == parent_id:
                    fragments.append({
                        "fragment_number": 0,
                        "fragment_id": bid,
                        "status": "DELIVERED" if bundle.status == BundleStatus.DELIVERED else "PENDING",
                        "delivered_at": bundle.delivered_at.isoformat() if bundle.delivered_at else None
                    })
                    fragment_count = 1
        
        if not fragments:
            return None
        
        fragments.sort(key=lambda f: f["fragment_number"])
        is_complete = len([f for f in fragments if f["status"] == "DELIVERED"]) == fragment_count
        
        return {
            "bundle_id": parent_id,
            "fragments": fragments,
            "fragments_received": len([f for f in fragments if f["status"] == "DELIVERED"]),
            "fragments_total": fragment_count,
            "is_complete": is_complete
        }
    
    def create_iss_reply_bundle(self, destination_station: str, payload: str, 
                               priority: str = "NORMAL", ttl_hours: int = 24) -> DTNBundle:
        """
        Create a bundle from ISS to a ground station
        Uses reverse routing: ISS → visible station → ... → destination
        """
        # Create bundle with source = "ISS"
        bundle = self.create_bundle(
            source_station="ISS",
            destination=destination_station,
            payload=payload,
            priority=priority,
            ttl_hours=ttl_hours
        )
        
        # Save to DB
        bundle_dict = bundle.to_dict()
        bundle_dict["encrypted_payload"] = bundle.encrypted_payload
        self.db_manager.save_bundle(bundle_dict)
        
        print(f"📤 ISS created reply bundle {bundle.bundle_id[:8]} to {destination_station}")
        
        return bundle
    
    def _sort_iss_queue(self):
        """Sort ISS queue by priority"""
        if not self.iss_queue:
            return
        
        bundles_with_ids = [
            (bundle_id, self.bundles.get(bundle_id))
            for bundle_id in self.iss_queue
            if bundle_id in self.bundles
        ]
        
        priority_order = {"EXPEDITED": 0, "NORMAL": 1, "BULK": 2}
        bundles_with_ids.sort(
            key=lambda x: priority_order.get(x[1].priority.value, 99) if x[1] else 99
        )
        
        self.iss_queue = [bundle_id for bundle_id, _ in bundles_with_ids]
    
    def get_iss_queue(self) -> List[Dict]:
        """Get all bundles in ISS queue"""
        bundles = []
        for bid in self.iss_queue:
            if bid in self.bundles:
                bundle = self.bundles[bid]
                if not bundle.is_expired():
                    bundles.append(bundle.to_dict())
                else:
                    bundle.status = BundleStatus.EXPIRED
        
        priority_order = {"EXPEDITED": 0, "NORMAL": 1, "BULK": 2}
        bundles.sort(key=lambda b: priority_order.get(b["priority"], 99))
        
        return bundles
    
    def get_neighbors(self, station_id: str) -> List[str]:
        """Get all neighbor stations for a given station based on mesh connections"""
        neighbors = []
        for conn in self.mesh_connections:
            station1, station2 = conn
            if station1 == station_id:
                neighbors.append(station2)
            elif station2 == station_id:
                neighbors.append(station1)
        return neighbors
    
    def get_broadcast_unreceived_neighbors(self, bundle_id: str, station_id: str) -> List[str]:
        """Get neighbors of a station that haven't received a broadcast bundle yet"""
        if bundle_id not in self.broadcast_received:
            self.broadcast_received[bundle_id] = set()
        
        neighbors = self.get_neighbors(station_id)
        received = self.broadcast_received[bundle_id]
        
        # Return neighbors that haven't received the broadcast
        return [n for n in neighbors if n not in received]
    
    def mark_broadcast_received(self, bundle_id: str, station_id: str):
        """Mark that a station has received a broadcast bundle"""
        if bundle_id not in self.broadcast_received:
            self.broadcast_received[bundle_id] = set()
        self.broadcast_received[bundle_id].add(station_id)
    
    def has_received_broadcast(self, bundle_id: str, station_id: str) -> bool:
        """Check if a station has already received a broadcast bundle"""
        return bundle_id in self.broadcast_received and station_id in self.broadcast_received[bundle_id]