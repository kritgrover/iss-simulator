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
    
    # Maximum fragment size (including headers)
    MAX_FRAGMENT_SIZE = 4096  # 4KB per fragment (including headers) - adjust for testing
    FRAGMENT_HEADER_SIZE = 256  # Estimated header overhead per fragment
    
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
            fragment_payload = fragment_payload_bytes.decode('utf-8', errors='ignore')
            
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
    
    def add_fragment(self, fragment: BundleFragment) -> bool:
        """
        Add a received fragment to reassembly buffer
        Returns True if all fragments are received and bundle can be reassembled
        """
        parent_id = fragment.parent_bundle_id
        
        if parent_id not in self.reassembly_buffers:
            self.reassembly_buffers[parent_id] = {}
        
        self.reassembly_buffers[parent_id][fragment.fragment_number] = fragment
        
        # Check if all fragments are received
        if parent_id in self.fragments:
            expected_fragments = len(self.fragments[parent_id])
            received_fragments = len(self.reassembly_buffers[parent_id])
            
            return received_fragments == expected_fragments
        
        # If we don't know total fragments, check if we have first and last
        buffer = self.reassembly_buffers[parent_id]
        if fragment.is_first and fragment.is_last:
            # Single fragment bundle
            return True
        
        if fragment.is_first in buffer and fragment.is_last in buffer:
            first_frag = buffer[fragment.is_first]
            last_frag = buffer[fragment.is_last]
            expected_total = last_frag.total_fragments
            return len(buffer) == expected_total
        
        return False
    
    def reassemble_bundle(self, parent_bundle_id: str) -> Optional[str]:
        """
        Reassemble fragments into original encrypted payload
        Returns reassembled encrypted payload string, or None if incomplete
        """
        if parent_bundle_id not in self.reassembly_buffers:
            return None
        
        buffer = self.reassembly_buffers[parent_bundle_id]
        
        # Sort fragments by fragment number
        sorted_fragments = sorted(buffer.values(), key=lambda f: f.fragment_number)
        
        # Check if we have all fragments
        if parent_bundle_id in self.fragments:
            expected_count = len(self.fragments[parent_bundle_id])
            if len(sorted_fragments) != expected_count:
                return None
        else:
            # Check continuity
            for i, frag in enumerate(sorted_fragments):
                if frag.fragment_number != i:
                    return None
        
        # Reassemble payload
        payload_parts = []
        for fragment in sorted_fragments:
            payload_parts.append(fragment.payload)
        
        reassembled = ''.join(payload_parts)
        
        # Clean up
        del self.reassembly_buffers[parent_bundle_id]
        if parent_bundle_id in self.fragments:
            del self.fragments[parent_bundle_id]
        
        return reassembled
    
    def get_fragments(self, bundle_id: str) -> List[BundleFragment]:
        """Get all fragments for a bundle"""
        return self.fragments.get(bundle_id, [])
    
    def cleanup_fragments(self, bundle_id: str):
        """Clean up fragments for a bundle"""
        if bundle_id in self.fragments:
            del self.fragments[bundle_id]
        if bundle_id in self.reassembly_buffers:
            del self.reassembly_buffers[bundle_id]

