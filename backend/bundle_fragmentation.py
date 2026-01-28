"""
Bundle Fragmentation Implementation
Handles splitting large bundles into fragments and reassembling them.
"""
import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

class FragmentStatus(str, Enum):
    """Status of a bundle fragment"""
    PENDING = "PENDING"
    TRANSMITTING = "TRANSMITTING"
    RECEIVED = "RECEIVED"
    DELIVERED = "DELIVERED"
    EXPIRED = "EXPIRED"

@dataclass
class BundleFragment:
    """Represents a fragment of a larger bundle"""
    fragment_id: str
    parent_bundle_id: str
    fragment_number: int  # 0-indexed
    total_fragments: int
    payload: str  # Encrypted payload for this fragment
    offset: int  # Byte offset in original payload
    size_bytes: int
    is_first: bool = False
    is_last: bool = False
    status: FragmentStatus = FragmentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "fragment_id": self.fragment_id,
            "parent_bundle_id": self.parent_bundle_id,
            "fragment_number": self.fragment_number,
            "total_fragments": self.total_fragments,
            "offset": self.offset,
            "size_bytes": self.size_bytes,
            "is_first": self.is_first,
            "is_last": self.is_last,
            "status": self.status.value,
            "created_at": self.created_at.isoformat()
        }

class BundleFragmentationManager:
    """
    Manages bundle fragmentation and reassembly.
    Fragments bundles that exceed maximum transmission unit (MTU) size.
    """
    
    # Maximum fragment size
    MAX_FRAGMENT_SIZE = 4096  # 4KB per fragment - adjust for testing
    FRAGMENT_HEADER_SIZE = 4094  # Estimated header overhead per fragment
    
    def __init__(self):
        self.fragments: Dict[str, List[BundleFragment]] = {}  # parent_bundle_id -> fragments
        self.reassembly_buffers: Dict[str, Dict[int, BundleFragment]] = {}  # parent_bundle_id -> {fragment_number: fragment}
    
    def should_fragment(self, payload_size: int) -> bool:
        """Check if bundle should be fragmented"""
        total_size = payload_size + self.FRAGMENT_HEADER_SIZE
        return total_size > self.MAX_FRAGMENT_SIZE
    
    def fragment_bundle(self, bundle_id: str, encrypted_payload: str, 
                       source_station: str) -> List[BundleFragment]:
        """
        Fragment an encrypted payload into multiple fragments
        Returns list of BundleFragment objects
        """
        payload_bytes = encrypted_payload.encode('utf-8')
        payload_size = len(payload_bytes)
        
        # Calculate payload size per fragment (excluding header)
        max_payload_per_fragment = self.MAX_FRAGMENT_SIZE - self.FRAGMENT_HEADER_SIZE
        
        # Calculate number of fragments needed
        total_fragments = (payload_size + max_payload_per_fragment - 1) // max_payload_per_fragment
        
        fragments = []
        
        for i in range(total_fragments):
            offset = i * max_payload_per_fragment
            fragment_payload_bytes = payload_bytes[offset:offset + max_payload_per_fragment]
            # Base64-encoded payloads are ASCII-safe, so decoding should never fail
            fragment_payload = fragment_payload_bytes.decode('ascii')
            
            fragment_id = f"{bundle_id}-frag-{i}"
            
            fragment = BundleFragment(
                fragment_id=fragment_id,
                parent_bundle_id=bundle_id,
                fragment_number=i,
                total_fragments=total_fragments,
                payload=fragment_payload,
                offset=offset,
                size_bytes=len(fragment_payload_bytes) + self.FRAGMENT_HEADER_SIZE,
                is_first=(i == 0),
                is_last=(i == total_fragments - 1),
                status=FragmentStatus.PENDING
            )
            
            fragments.append(fragment)
        
        # Store fragments
        self.fragments[bundle_id] = fragments
        
        return fragments
