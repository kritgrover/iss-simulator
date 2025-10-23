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
            "age_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds()
        }

class DTNBundleManager:
    """Manages DTN bundles across ground station network"""
    
    def __init__(self, stations: List[Dict]):
        self.stations = {s["id"]: s["name"] for s in stations}
        self.bundles: Dict[str, DTNBundle] = {}
        self.station_queues: Dict[str, List[str]] = {sid: [] for sid in self.stations.keys()}
        self.pending_acks: List[Dict] = []  # NEW: Queue of ACKs to send
        
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
        
        print(f"📦 Created bundle {bundle_id[:8]} at {source_station}: {payload[:30]}...")
        return bundle
    
    def transmit_bundle(self, bundle_id: str, from_station: str, to_station: str) -> Optional[Tuple[bool, Optional[Dict]]]:
        """
        Transmit bundle from one station to another (or ISS)
        Returns: (success, ack_message) where ack_message is dict if ACK should be sent
        """
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        # Prevent forwarding loops - don't send to stations we've already visited
        if to_station in bundle.hops:
            print(f"⚠️  Bundle {bundle_id[:8]} loop detected! Not forwarding {from_station} → {to_station}")
            return (False, None)
        
        # Mark as transmitting
        bundle.status = BundleStatus.TRANSMITTING
        
        # Simulate transmission delay
        if to_station == "ISS" or to_station == bundle.destination_station:
            # Delivered!
            bundle.status = BundleStatus.DELIVERED
            bundle.delivered_at = datetime.now(timezone.utc)
            bundle.hops.append(to_station)
            
            # Remove from queue
            if bundle_id in self.station_queues[from_station]:
                self.station_queues[from_station].remove(bundle_id)
            
            print(f"✅ Bundle {bundle_id[:8]} delivered to {to_station}")
            
            # NEW: Generate ACK for delivery
            ack = {
                "type": "custody_ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": from_station,
                "ack_type": "delivered",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return (True, ack)
        else:
            # Forwarded to another station
            bundle.status = BundleStatus.FORWARDED
            previous_custodian = bundle.current_custodian
            bundle.current_custodian = to_station
            bundle.forwarded_to = to_station
            bundle.hops.append(to_station)
            
            # Move from source queue to destination queue
            if bundle_id in self.station_queues[from_station]:
                self.station_queues[from_station].remove(bundle_id)
            self.station_queues[to_station].append(bundle_id)
            
            # Reset status to queued at new station
            bundle.status = BundleStatus.QUEUED
            
            print(f"📨 Bundle {bundle_id[:8]} forwarded {from_station} → {to_station}")
            
            # NEW: Generate ACK for custody transfer
            ack = {
                "type": "custody_ack",
                "bundle_id": bundle_id,
                "bundle_id_short": bundle_id[:8],
                "from_station": to_station,
                "to_station": previous_custodian,
                "ack_type": "custody_accepted",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return (True, ack)
    
    def process_custody_ack(self, ack: Dict) -> None:
        """
        Process a custody acknowledgement
        When a station receives an ACK, it can safely delete its copy of the bundle
        """
        bundle_id = ack["bundle_id"]
        to_station = ack["to_station"]
        
        # The previous custodian no longer needs to keep the bundle
        # (already removed from queue during transmit_bundle)
        print(f"✓ Station {to_station} received ACK for bundle {ack['bundle_id_short']}")
    
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
    
    def process_contact(self, station_id: str, is_visible: bool, next_visible_station: Optional[str] = None):
        """
        Process bundles during contact opportunities
        - If ISS visible: transmit queued bundles
        - If not visible but another station will be: forward bundles
        """
        queue = self.station_queues.get(station_id, [])
        
        if not queue:
            return
        
        if is_visible:
            # ISS is overhead - transmit bundles
            transmitted = []
            for bundle_id in queue[:3]:  # Transmit up to 3 bundles per update
                result = self.transmit_bundle(bundle_id, station_id, "ISS")
                if result:
                    success, ack = result
                    if success:
                        transmitted.append(bundle_id)
                        if ack:
                            self.queue_ack(ack)
            
            if transmitted:
                print(f"📡 {station_id} transmitted {len(transmitted)} bundles to ISS")
        
        elif next_visible_station and len(queue) > 0:
            # Forward bundle to next station that will have contact
            # Forward highest priority bundle
            bundle_id = queue[0]
            result = self.transmit_bundle(bundle_id, station_id, next_visible_station)
            if result:
                success, ack = result
                if success and ack:
                    self.queue_ack(ack)
    
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