import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class BundlePriority(str, Enum):
    EXPEDITED = "EXPEDITED"  # Red - high priority
    NORMAL = "NORMAL"        # Cyan - standard
    BULK = "BULK"            # Gray - low priority

class BundleStatus(str, Enum):
    QUEUED = "QUEUED"
    TRANSMITTING = "TRANSMITTING"
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
    hops: List[str] = field(default_factory=list)
    size_bytes: int = 0  # NEW: Bundle size
    
    def __post_init__(self):
        if self.size_bytes == 0:
            # Calculate size based on payload + headers
            payload_size = len(self.payload.encode('utf-8'))
            header_overhead = 200  # DTN header overhead (100-500 bytes typical)
            self.size_bytes = payload_size + header_overhead
    
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
            "age_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds(),
            "size_bytes": self.size_bytes  # NEW
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

class DTNBundleManager:
    """Manages DTN bundles across ground station network"""
    
    def __init__(self, stations: List[Dict]):
        self.stations = {s["id"]: s["name"] for s in stations}
        self.bundles: Dict[str, DTNBundle] = {}
        self.station_queues: Dict[str, List[str]] = {sid: [] for sid in self.stations.keys()}
        self.pending_acks: List[Dict] = []
        self.active_transmissions: Dict[str, BundleTransmission] = {}
        self.delivered_bundles: List[str] = []
        
        print(f"📦 DTN Bundle Manager initialized with {len(self.stations)} stations")
    
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
        
        print(f"📦 Created bundle {bundle_id[:8]} at {source_station}: {payload[:30]}... (size: {bundle.size_bytes} bytes)")
        return bundle
    
    def start_transmission(self, bundle_id: str, from_station: str, 
                      to_station: str, data_rate_bps: float) -> Optional[BundleTransmission]:
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
        
        # Store where we're forwarding to (temporarily)
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
            bytes_transmitted=0
        )
        
        # Mark bundle as transmitting
        bundle.status = BundleStatus.TRANSMITTING
        self.active_transmissions[bundle_id] = transmission
        
        print(f"📡 Started transmitting bundle {bundle_id[:8]}")
        print(f"   Route: {from_station} → {to_station}")
        print(f"   Size: {bundle.size_bytes} bytes ({bundle.size_bytes/1024:.2f} KB)")
        print(f"   Data Rate: {data_rate_bps/1000:.1f} kbps")
        print(f"   Estimated Duration: {transmission_time_sec:.1f}s")
        
        return transmission
    
    def update_transmissions(self, delta_time_sec: float, 
                           station_contact_states: Dict[str, bool]) -> List[str]:
        """
        Update all active transmissions
        station_contact_states: dict of {station_id: is_visible}
        Returns list of completed bundle IDs
        """
        completed = []
        
        for bundle_id, transmission in list(self.active_transmissions.items()):
            # Check if contact is maintained
            from_station = transmission.from_station
            is_contact_maintained = station_contact_states.get(from_station, False)
            
            if not is_contact_maintained and transmission.to_station == "ISS":
                # Contact lost! Abort transmission to ISS
                elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                print(f"⚠️  Transmission of {bundle_id[:8]} ABORTED after {elapsed:.1f}s (contact lost)")
                print(f"   Progress: {transmission.progress_percent():.1f}% ({transmission.bytes_transmitted:.0f}/{transmission.size_bytes} bytes)")
                
                bundle = self.bundles[bundle_id]
                bundle.status = BundleStatus.QUEUED  # Back to queue
                del self.active_transmissions[bundle_id]
                continue
            
            # Update bytes transmitted
            bytes_this_tick = (transmission.data_rate_bps / 8) * delta_time_sec
            transmission.bytes_transmitted = min(
                transmission.size_bytes,
                transmission.bytes_transmitted + bytes_this_tick
            )
            
            # Check if complete
            if transmission.is_complete():
                completed.append(bundle_id)
                elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                print(f"   Size: {transmission.size_bytes} bytes")
                print(f"   Actual Duration: {elapsed:.2f}s")
                print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                
                del self.active_transmissions[bundle_id]
        
        return completed
    
    def complete_transmission(self, bundle_id: str) -> Optional[Dict]:
        """
        Complete a bundle transmission and generate ACK
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # Get transmission destination from bundle.forwarded_to
        to_station = bundle.forwarded_to
        from_station = bundle.current_custodian
        
        if not to_station:
            print(f"⚠️  Cannot complete transmission for {bundle_id[:8]} - no destination set")
            return None
        
        # Move bundle
        if to_station == "ISS":
            # Delivered!
            bundle.status = BundleStatus.DELIVERED
            bundle.delivered_at = datetime.now(timezone.utc)
            bundle.hops.append(to_station)
            bundle.forwarded_to = None
            
            # Calculate total delivery time
            total_time = (bundle.delivered_at - bundle.created_at).total_seconds()
            
            # Remove from queue
            if bundle_id in self.station_queues[from_station]:
                self.station_queues[from_station].remove(bundle_id)
            
            self.delivered_bundles.append(bundle_id)
            if len(self.delivered_bundles) > 10:
                self.delivered_bundles.pop(0)
            
            print(f"🎯 Bundle {bundle_id[:8]} DELIVERED to ISS")
            print(f"   Total delivery time: {total_time:.1f}s ({total_time/60:.1f} min)")
            print(f"   Complete path: {' → '.join(bundle.hops)}")
            
            ack = {
                "type": "custody_ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "ack_type": "delivered",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return ack
        else:
            # Forwarded to another station
            bundle.status = BundleStatus.QUEUED
            previous_custodian = bundle.current_custodian
            bundle.current_custodian = to_station
            bundle.hops.append(to_station)
            bundle.forwarded_to = None  # Clear this
            
            # Move from source queue to destination queue
            if bundle_id in self.station_queues[from_station]:
                self.station_queues[from_station].remove(bundle_id)
            self.station_queues[to_station].append(bundle_id)
            
            print(f"📨 Bundle {bundle_id[:8]} custody transferred to {to_station.upper()}")
            print(f"   Path so far: {' → '.join(bundle.hops)}")
            
            ack = {
                "type": "custody_ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": previous_custodian,
                "ack_type": "custody_accepted",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return ack
    
    def get_delivered_bundles(self) -> List[Dict]:
        """Get recently delivered bundles for history"""
        bundles = []
        for bundle_id in reversed(self.delivered_bundles):  # Most recent first
            if bundle_id in self.bundles:
                bundles.append(self.bundles[bundle_id].to_dict())
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
                # Remove from station queue
                for queue in self.station_queues.values():
                    if bundle_id in queue:
                        queue.remove(bundle_id)
                print(f"⏰ Bundle {bundle_id[:8]} expired (TTL exceeded)")