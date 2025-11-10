#!/usr/bin/env python3
"""
DTN Client for Mininet Nodes

Client utility to send DTN bundles over the network.
Can be used for testing or manual bundle transmission.
"""

import socket
import json
import struct
import sys
import os
import zlib

# Add parent directory to path to import DTN modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DTN_PORT = 5000


def calculate_checksum(payload: str) -> int:
    """Calculate CRC32 checksum"""
    data = payload.encode('utf-8')
    return zlib.crc32(data) & 0xffffffff


def send_message(sock: socket.socket, message: dict) -> bool:
    """Send a message over socket"""
    try:
        # Serialize message
        message_json = json.dumps(message).encode('utf-8')
        message_length = len(message_json)
        
        # Send length + message
        sock.sendall(struct.pack('>I', message_length))
        sock.sendall(message_json)
        
        return True
    except Exception as e:
        print("❌ Error sending message: {}".format(e))
        return False


def receive_message(sock: socket.socket) -> dict:
    """Receive a message from socket"""
    try:
        # Read message length (4 bytes)
        length_data = sock.recv(4)
        if len(length_data) < 4:
            return None
        
        message_length = struct.unpack('>I', length_data)[0]
        
        # Read message data
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(message_length - len(message_data))
            if not chunk:
                return None
            message_data += chunk
        
        # Parse JSON message
        message = json.loads(message_data.decode('utf-8'))
        return message
    except Exception as e:
        print("❌ Error receiving message: {}".format(e))
        return None


def send_bundle(dest_ip: str, dest_port: int, bundle_id: str, source_station: str,
                destination_station: str, payload: str, priority: str = "NORMAL") -> bool:
    """
    Send a bundle to destination
    
    Args:
        dest_ip: Destination IP address
        dest_port: Destination port
        bundle_id: Bundle ID
        source_station: Source station ID
        destination_station: Destination station ID
        payload: Bundle payload
        priority: Bundle priority
        
    Returns:
        True if ACK received, False if NAK or error
    """
    try:
        # Calculate checksum
        checksum = calculate_checksum(payload)
        
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((dest_ip, dest_port))
        
        # Prepare bundle message
        bundle_message = {
            'type': 'bundle',
            'bundle': {
                'bundle_id': bundle_id,
                'source_station': source_station,
                'destination_station': destination_station,
                'payload': payload,
                'priority': priority,
                'checksum': checksum,
                'size_bytes': len(payload.encode('utf-8')) + 200  # payload + header overhead
            }
        }
        
        # Send bundle
        print("📤 Sending bundle {} to {}:{}".format(bundle_id[:8], dest_ip, dest_port))
        success = send_message(sock, bundle_message)
        
        if not success:
            sock.close()
            return False
        
        # Wait for ACK/NAK
        response = receive_message(sock)
        sock.close()
        
        if response:
            if response.get('type') == 'ack':
                print("✅ ACK received for bundle {}".format(bundle_id[:8]))
                return True
            elif response.get('type') == 'nak':
                print("❌ NAK received for bundle {}: {}".format(
                    bundle_id[:8], response.get('reason', 'unknown')
                ))
                return False
        
        print("⚠️  No response received")
        return False
        
    except socket.timeout:
        print("❌ Error sending bundle: Connection timeout (30s)")
        return False
    except ConnectionRefusedError:
        print("❌ Error sending bundle: Connection refused - server not listening on {}:{}".format(dest_ip, dest_port))
        return False
    except OSError as e:
        if e.errno == 113:  # No route to host
            print("❌ Error sending bundle: No route to host {}:{}".format(dest_ip, dest_port))
        elif e.errno == 111:  # Connection refused
            print("❌ Error sending bundle: Connection refused - server not listening")
        else:
            print("❌ Error sending bundle: Network error (errno {}): {}".format(e.errno, e))
        return False
    except Exception as e:
        error_type = type(e).__name__
        print("❌ Error sending bundle: {} - {}".format(error_type, e))
        return False


def main():
    """CLI interface for sending bundles"""
    if len(sys.argv) < 5:
        print("Usage: {} <dest_ip> <bundle_id> <source_station> <destination_station> <payload> [priority]".format(
            sys.argv[0]
        ))
        print("Example: {} 10.0.0.1 abc123 toronto iss 'Hello from Toronto' NORMAL".format(
            sys.argv[0]
        ))
        sys.exit(1)
    
    dest_ip = sys.argv[1]
    bundle_id = sys.argv[2]
    source_station = sys.argv[3]
    destination_station = sys.argv[4]
    payload = sys.argv[5]
    priority = sys.argv[6] if len(sys.argv) > 6 else "NORMAL"
    
    success = send_bundle(
        dest_ip, DTN_PORT, bundle_id, source_station,
        destination_station, payload, priority
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

