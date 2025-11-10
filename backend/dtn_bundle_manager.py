import uuid
import zlib
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
    hops: List[str] = field(default_factory=list)
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
    
    def __init__(self, stations: List[Dict]):
        self.stations = {s["id"]: s["name"] for s in stations}
        self.bundles: Dict[str, DTNBundle] = {}
        self.station_queues: Dict[str, List[str]] = {sid: [] for sid in self.stations.keys()}
        self.pending_acks: List[Dict] = []
        self.active_transmissions: Dict[str, BundleTransmission] = {}
        self.pending_acknowledgments: Dict[str, PendingAcknowledgment] = {}  # Bundles waiting for ACK/NAK
        self.delivered_bundles: List[str] = []
        self.bundle_retry_counts: Dict[str, int] = {}  # Track retry counts for bundles
        
        print(f"📦 DTN Bundle Manager initialized with {len(self.stations)} stations")
        print(f"   ACK timeout: {self.ACK_TIMEOUT_SECONDS}s, Max retries: {self.MAX_RETRIES}")
    
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
            # Store the provided retry count
            self.bundle_retry_counts[bundle_id] = retransmission_count
        
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
            bytes_transmitted=0,
            retransmission_count=retransmission_count
        )
        
        # Mark bundle as transmitting
        bundle.status = BundleStatus.TRANSMITTING
        self.active_transmissions[bundle_id] = transmission
        
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
        
        # Check if transmission was already completed (ACK already processed)
        # This can happen if complete_transmission is called after process_ack
        if not to_station:
            # Check if bundle is already delivered or in a final state
            if bundle.status == BundleStatus.DELIVERED:
                # Already delivered, nothing to do
                return None
            # Check if bundle is waiting for ACK (transmission completed, waiting for response)
            if bundle.status == BundleStatus.WAITING_ACK:
                # Transmission completed, ACK is being processed, nothing to do here
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
        # Calculate checksum of the received payload
        received_checksum = bundle.calculate_checksum()
        expected_checksum = bundle.checksum
        
        # Log checksum verification
        print(f"🔍 Bundle {bundle_id[:8]} received at {to_station} - verifying checksum...")
        print(f"   Expected checksum (from bundle): 0x{expected_checksum:08x}")
        print(f"   Received checksum (calculated): 0x{received_checksum:08x}")
        
        # Verify checksums match
        checksum_valid = (received_checksum == expected_checksum)
        
        if checksum_valid:
            # Checksum matches - send ACK
            print(f"   ✅ Checksums MATCH - bundle integrity verified")
            print(f"✅ Bundle {bundle_id[:8]} received at {to_station}, checksum valid - sending ACK")
            
            # Create ACK message
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
            # The pending_acknowledgment tracks that sender is waiting for ACK
            
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
        
        # Verify we're the sender
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
            
            # Move from sender's queue to receiver's queue
            if bundle_id in self.station_queues[to_station]:
                self.station_queues[to_station].remove(bundle_id)
            self.station_queues[from_station].append(bundle_id)
            
            # Sort the destination queue after adding bundle
            self._sort_station_queue(from_station)
            
            print(f"📨 Bundle {bundle_id[:8]} ACK received - custody transferred to {from_station.upper()}")
            print(f"   Path so far: {' → '.join(bundle.hops)}")
        
        return True
    
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
        
        # Verify we're the sender
        if bundle.current_custodian != to_station:
            print(f"⚠️  NAK for {bundle_id[:8]} received but we're not the sender")
            return False
        
        # Check if we have pending acknowledgment for this bundle
        if bundle_id not in self.pending_acknowledgments:
            print(f"⚠️  NAK for {bundle_id[:8]} but no pending acknowledgment found")
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
            
            print(f"🔄 Scheduling retransmission of {bundle_id[:8]} to {from_station}")
            return True
        else:
            # Max retries exceeded
            print(f"⚠️  Bundle {bundle_id[:8]} max retries exceeded - giving up")
            del self.pending_acknowledgments[bundle_id]
            bundle.status = BundleStatus.EXPIRED
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
                    print(f"⚠️  Bundle {bundle_id[:8]} max retries exceeded - giving up")
                    del self.pending_acknowledgments[bundle_id]
                    if bundle_id in self.bundles:
                        bundle = self.bundles[bundle_id]
                        bundle.status = BundleStatus.EXPIRED
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