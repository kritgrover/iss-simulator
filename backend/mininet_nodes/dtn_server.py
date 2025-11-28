#!/usr/bin/env python3
"""
DTN Server for Mininet Nodes

Runs inside each Mininet node to receive and process DTN bundles.
Handles checksum verification and ACK/NAK generation.
"""

import socket
import json
import struct
import sys
import os
import zlib

# Add parent directory to path to import DTN modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dtn_bundle_manager import DTNBundle

DTN_PORT = 5000


def calculate_checksum(payload: str) -> int:
    """Calculate CRC32 checksum"""
    data = payload.encode('utf-8')
    return zlib.crc32(data) & 0xffffffff


def receive_message(sock: socket.socket) -> dict:
    """Receive a message from socket"""
    try:
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


def handle_bundle(node_id: str, message: dict, client_socket: socket.socket):
    """Handle received bundle"""
    bundle_data = message.get('bundle')
    if not bundle_data:
        return
    
    bundle_id = bundle_data.get('bundle_id', 'unknown')
    payload = bundle_data.get('payload', '')
    expected_checksum = bundle_data.get('checksum', 0)
    destination = bundle_data.get('destination_station', 'iss')
    
    print("📦 Received bundle {} at {}".format(bundle_id[:8], node_id))
    
    # Verify checksum
    calculated_checksum = calculate_checksum(payload)
    
    if calculated_checksum != expected_checksum:
        # Checksum mismatch - send NAK
        print("❌ Checksum mismatch: expected 0x{:08x}, got 0x{:08x}".format(
            expected_checksum, calculated_checksum
        ))
        nak_message = {
            'type': 'nak',
            'bundle_id': bundle_id,
            'reason': 'checksum_mismatch',
            'expected_checksum': expected_checksum,
            'received_checksum': calculated_checksum
        }
        send_message(client_socket, nak_message)
        return
    
    # Checksum valid - send ACK
    print("✅ Bundle {} verified, sending ACK".format(bundle_id[:8]))
    ack_message = {
        'type': 'ack',
        'bundle_id': bundle_id,
        'checksum': calculated_checksum
    }
    send_message(client_socket, ack_message)
    
    # If this is the final destination, bundle is delivered
    if node_id == destination or (node_id == 'iss' and destination == 'iss'):
        print("🎯 Bundle {} delivered to {}".format(bundle_id[:8], node_id))
    else:
        print("📨 Bundle {} received at {} (forwarding needed)".format(
            bundle_id[:8], node_id
        ))


def main():
    """Main server loop"""
    # Get node ID from environment or command line
    node_id = os.environ.get('NODE_ID', sys.argv[1] if len(sys.argv) > 1 else 'unknown')
    
    print("🚀 Starting DTN server for node: {}".format(node_id))
    
    # Create socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', DTN_PORT))
    server_socket.listen(5)
    
    print("📡 DTN server listening on port {}".format(DTN_PORT))
    
    try:
        while True:
            client_socket, addr = server_socket.accept()
            print("🔌 Connection from {}".format(addr))
            
            try:
                # Receive message
                message = receive_message(client_socket)
                if message:
                    msg_type = message.get('type')
                    
                    if msg_type == 'bundle':
                        handle_bundle(node_id, message, client_socket)
                    else:
                        print("⚠️  Unknown message type: {}".format(msg_type))
            except Exception as e:
                print("❌ Error handling connection: {}".format(e))
            finally:
                client_socket.close()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        server_socket.close()


if __name__ == '__main__':
    main()

