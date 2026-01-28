"""
Bundle Security Protocol (BSP) Implementation
Provides data integrity, authentication, and confidentiality for DTN bundles.
"""
import hashlib
import hmac
import json
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import os
import base64

class SecurityBlockType(str, Enum):
    """Types of security blocks in BSP"""
    BAB = "BAB"  # Bundle Authentication Block
    PIB = "PIB"  # Payload Integrity Block
    PCB = "PCB"  # Payload Confidentiality Block
    ESB = "ESB"  # Extension Security Block

@dataclass
class SecurityBlock:
    """Base class for BSP security blocks"""
    block_type: SecurityBlockType
    security_target: str  # Bundle ID or fragment ID
    security_source: str  # Station ID that created this block
    security_result: Optional[str] = None  # Result of security operation
    
    def to_dict(self) -> Dict:
        return {
            "block_type": self.block_type.value,
            "security_target": self.security_target,
            "security_source": self.security_source,
            "security_result": self.security_result
        }

class BundleAuthenticationBlock(SecurityBlock):
    """BAB: Ensures bundle authenticity and integrity between SA nodes"""
    
    def __init__(self, security_target: str, security_source: str, mac: str, key_id: str):
        super().__init__(SecurityBlockType.BAB, security_target, security_source)
        self.mac = mac
        self.key_id = key_id
    
    def to_dict(self) -> Dict:
        result = super().to_dict()
        result.update({
            "mac": self.mac,
            "key_id": self.key_id
        })
        return result

class PayloadIntegrityBlock(SecurityBlock):
    """PIB: Ensures integrity of payload by verifying the signer"""
    
    def __init__(self, security_target: str, security_source: str, signature: str, signer: str):
        super().__init__(SecurityBlockType.PIB, security_target, security_source)
        self.signature = signature
        self.signer = signer
    
    def to_dict(self) -> Dict:
        result = super().to_dict()
        result.update({
            "signature": self.signature,
            "signer": self.signer
        })
        return result

class PayloadConfidentialityBlock(SecurityBlock):
    """PCB: Encrypts bundle payload"""
    
    def __init__(self, security_target: str, security_source: str, 
                 encryption_method: str, key_id: str, iv: str):
        super().__init__(SecurityBlockType.PCB, security_target, security_source)
        self.encryption_method = encryption_method
        self.key_id = key_id
        self.iv = iv
    
    def to_dict(self) -> Dict:
        result = super().to_dict()
        result.update({
            "encryption_method": self.encryption_method,
            "key_id": self.key_id,
            "iv": self.iv
        })
        return result

class BSPSecurityManager:
    """
    Manages Bundle Security Protocol operations.
    Provides encryption, authentication, and integrity checking.
    """
    
    # Shared secret key for demonstration
    DEFAULT_KEY = b"iss-simulator-bsp-key-2025-secure"
    
    def __init__(self):
        self.backend = default_backend()
        self.station_keys: Dict[str, bytes] = {}
    
    def _derive_key(self, station_id: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key for a station"""
        if station_id in self.station_keys:
            return self.station_keys[station_id]
        
        if salt is None:
            salt = station_id.encode('utf-8')
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        key = kdf.derive(self.DEFAULT_KEY)
        self.station_keys[station_id] = key
        return key
    
    def _generate_iv(self) -> bytes:
        """Generate a random initialization vector"""
        return os.urandom(16)  # 16 bytes for AES
    
    def encrypt_payload(self, payload: str, source_station: str) -> Tuple[str, PayloadConfidentialityBlock]:
        """
        Encrypt bundle payload using AES-256-CBC
        Returns: (encrypted_payload_base64, PCB)
        """
        try:
            # Convert payload to bytes
            plaintext = payload.encode('utf-8')
            
            # Derive key for source station
            key = self._derive_key(source_station)
            
            # Generate IV
            iv = self._generate_iv()
            
            # Pad plaintext
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(plaintext)
            padded_data += padder.finalize()
            
            # Encrypt
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            # Encode to base64
            encrypted_payload = base64.b64encode(ciphertext).decode('utf-8')
            iv_base64 = base64.b64encode(iv).decode('utf-8')
            
            # Create PCB
            pcb = PayloadConfidentialityBlock(
                security_target="payload",
                security_source=source_station,
                encryption_method="AES-256-CBC",
                key_id=f"{source_station}-key",
                iv=iv_base64
            )
            
            return encrypted_payload, pcb
            
        except Exception as e:
            raise Exception(f"Encryption failed: {str(e)}")
    
    def decrypt_payload(self, encrypted_payload: str, pcb: PayloadConfidentialityBlock, 
                       source_station: str) -> str:
        """
        Decrypt bundle payload
        Returns: decrypted plaintext
        """
        try:
            # Decode from base64
            ciphertext = base64.b64decode(encrypted_payload)
            iv = base64.b64decode(pcb.iv)
            
            # Derive key
            key = self._derive_key(source_station)
            
            # Decrypt
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext)
            plaintext += unpadder.finalize()
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Decryption failed: {str(e)}")
    
    def create_bab(self, bundle_data: Dict, from_station: str, to_station: str) -> BundleAuthenticationBlock:
        """
        Create Bundle Authentication Block (BAB)
        Ensures authenticity and integrity between forwarding SA node and receiving SA node
        """
        try:
            # Create message to authenticate (bundle metadata + encrypted payload hash)
            message = json.dumps({
                "bundle_id": bundle_data.get("bundle_id"),
                "source": bundle_data.get("source_station"),
                "destination": bundle_data.get("destination_station"),
                "from_station": from_station,
                "to_station": to_station,
                "payload_hash": bundle_data.get("payload_hash", "")
            }, sort_keys=True).encode('utf-8')
            
            # Generate MAC using HMAC-SHA256
            key = self._derive_key(from_station)
            mac_bytes = hmac.new(key, message, hashlib.sha256).digest()
            mac = base64.b64encode(mac_bytes).decode('utf-8')
            
            bab = BundleAuthenticationBlock(
                security_target=bundle_data.get("bundle_id", ""),
                security_source=from_station,
                mac=mac,
                key_id=f"{from_station}-key"
            )
            
            return bab
            
        except Exception as e:
            raise Exception(f"BAB creation failed: {str(e)}")
    
    def verify_bab(self, bundle_data: Dict, bab: BundleAuthenticationBlock, 
                   from_station: str, to_station: str) -> bool:
        """
        Verify Bundle Authentication Block
        Returns True if authentication is valid, False otherwise
        """
        try:
            # Recreate message with the same parameters used when creating the BAB
            payload_hash = bundle_data.get("payload_hash", "")
            if not payload_hash:
                print(f"⚠️  BAB verification: payload_hash is missing from bundle_data")
                print(f"   Available keys: {list(bundle_data.keys())}")
            
            message_dict = {
                "bundle_id": bundle_data.get("bundle_id"),
                "source": bundle_data.get("source_station"),
                "destination": bundle_data.get("destination_station"),
                "from_station": from_station,
                "to_station": to_station,
                "payload_hash": payload_hash
            }
            message = json.dumps(message_dict, sort_keys=True).encode('utf-8')
            
            # Recompute MAC
            key = self._derive_key(bab.security_source)
            expected_mac_bytes = hmac.new(key, message, hashlib.sha256).digest()
            expected_mac = base64.b64encode(expected_mac_bytes).decode('utf-8')
            
            # Debug: Print comparison details
            if bab.mac != expected_mac:
                print(f"⚠️  BAB MAC mismatch:")
                print(f"   Bundle ID: {bundle_data.get('bundle_id', 'unknown')[:8]}")
                print(f"   From: {from_station}, To: {to_station}")
                print(f"   BAB security_source: {bab.security_source}")
                print(f"   Expected MAC: {expected_mac[:16]}...")
                print(f"   Received MAC: {bab.mac[:16]}...")
                print(f"   Message used: {message.decode('utf-8')[:200]}...")
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(bab.mac, expected_mac)
            
        except Exception as e:
            print(f"⚠️  BAB verification error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_pib(self, payload_hash: str, source_station: str) -> PayloadIntegrityBlock:
        """
        Create Payload Integrity Block (PIB)
        Ensures integrity of payload by verifying the signer
        """
        try:
            # Sign the payload hash
            key = self._derive_key(source_station)
            signature_bytes = hmac.new(key, payload_hash.encode('utf-8'), hashlib.sha256).digest()
            signature = base64.b64encode(signature_bytes).decode('utf-8')
            
            pib = PayloadIntegrityBlock(
                security_target="payload",
                security_source=source_station,
                signature=signature,
                signer=source_station
            )
            
            return pib
            
        except Exception as e:
            raise Exception(f"PIB creation failed: {str(e)}")
    
    def verify_pib(self, payload_hash: str, pib: PayloadIntegrityBlock) -> bool:
        """
        Verify Payload Integrity Block
        Returns True if integrity is valid, False otherwise
        """
        try:
            # Recompute signature
            key = self._derive_key(pib.signer)
            expected_signature_bytes = hmac.new(key, payload_hash.encode('utf-8'), hashlib.sha256).digest()
            expected_signature = base64.b64encode(expected_signature_bytes).decode('utf-8')
            
            # Constant-time comparison
            return hmac.compare_digest(pib.signature, expected_signature)
            
        except Exception as e:
            print(f"⚠️  PIB verification error: {e}")
            return False
    
    def get_payload_hash(self, encrypted_payload: str) -> str:
        """Get hash of encrypted payload for display purposes"""
        payload_bytes = encrypted_payload.encode('utf-8')
        hash_obj = hashlib.sha256(payload_bytes)
        return hash_obj.hexdigest()
    
    def get_payload_hash_short(self, encrypted_payload: str, length: int = 16) -> str:
        """Get short hash of encrypted payload for UI display"""
        full_hash = self.get_payload_hash(encrypted_payload)
        return full_hash[:length]

