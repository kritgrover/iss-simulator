"""
Network DTN Manager

Extends DTNBundleManager to use real network sockets instead of simulation.
Handles bundle transmission over TCP sockets with real network delays and noise.
"""

import socket
import json
import struct
import threading
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone
from dtn_bundle_manager import (
    DTNBundleManager, DTNBundle, BundlePriority, BundleStatus,
    BundleTransmission, PendingAcknowledgment
)


class NetworkDTNManager(DTNBundleManager):
    """DTN Manager that uses real network sockets"""
    
    # Network protocol constants
    PROTOCOL_VERSION = 1
    MSG_TYPE_BUNDLE = 1
    MSG_TYPE_ACK = 2
    MSG_TYPE_NAK = 3
    
    # Port for DTN protocol
    DTN_PORT = 5000
    
    def __init__(self, stations: List[Dict], topology=None):
        """
        Initialize Network DTN Manager
        
        Args:
            stations: List of ground station dictionaries
            topology: ISSTopology instance (optional, for IP lookups)
        """
        super().__init__(stations)
        self.topology = topology
        self.servers = {}  # node_id -> server socket
        self.server_threads = {}  # node_id -> thread
        self.running = False
        self.message_handlers = {}  # node_id -> handler function
        
        # Track active connections
        self.connections = {}  # (from_node, to_node) -> socket
        
        print("🌐 NetworkDTNManager initialized")
    
    def start_servers(self):
        """Start TCP servers for all nodes within their Mininet namespaces"""
        if self.running:
            return
        
        if not self.topology:
            print("⚠️  No topology available, cannot start servers in node namespaces")
            return
        
        self.running = True
        
        # Get the path to dtn_server.py
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dtn_server_script = os.path.join(script_dir, 'mininet_nodes', 'dtn_server.py')
        
        # Start server for each ground station within its node namespace
        for station_id in self.stations.keys():
            self._start_server_in_node(station_id, dtn_server_script)
        
        # Start server for ISS within its node namespace
        self._start_server_in_node('iss', dtn_server_script)
        
        print("✅ All DTN servers started in node namespaces")
    
    def stop_servers(self):
        """Stop all TCP servers"""
        self.running = False
        
        # Close all connections
        for conn in self.connections.values():
            try:
                conn.close()
            except:
                pass
        self.connections.clear()
        
        # Stop all server processes
        for node_id, proc in self.servers.items():
            try:
                if hasattr(proc, 'terminate'):
                    proc.terminate()
                elif hasattr(proc, 'kill'):
                    proc.kill()
                elif hasattr(proc, 'close'):
                    proc.close()
            except:
                pass
        
        # Wait for processes to finish
        for node_id, proc in self.servers.items():
            try:
                if hasattr(proc, 'wait'):
                    proc.wait(timeout=1.0)
            except:
                pass
        
        self.servers.clear()
        self.server_threads.clear()
        
        print("🛑 All DTN servers stopped")
    
    def _start_server_in_node(self, node_id: str, server_script: str):
        """Start TCP server within a Mininet node's namespace"""
        if node_id in self.servers:
            return
        
        # Get the Mininet node
        node = self.topology.get_node(node_id)
        if not node:
            print("❌ Node {} not found in topology".format(node_id))
            return
        
        try:
            # Run the server script within the node's namespace
            # Use popen to run it in background
            import os
            cmd = 'python3 {} {}'.format(server_script, node_id)
            proc = node.popen(cmd, shell=True)
            
            self.servers[node_id] = proc
            print("📡 Server started for {} in node namespace (PID: {})".format(
                node_id, proc.pid if hasattr(proc, 'pid') else 'unknown'
            ))
        except Exception as e:
            print("❌ Failed to start server for {}: {}".format(node_id, e))
    
    def _handle_connection(self, node_id: str, client_socket: socket.socket, addr):
        """Handle incoming connection"""
        try:
            while self.running:
                # Receive message
                message = self._receive_message(client_socket)
                if not message:
                    break
                
                # Process message
                self._process_message(node_id, message, client_socket)
        except Exception as e:
            print("❌ Connection error for {}: {}".format(node_id, e))
        finally:
            client_socket.close()
    
    def _receive_message(self, sock: socket.socket) -> Optional[Dict]:
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
    
    def _send_message(self, sock: socket.socket, message: Dict) -> bool:
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
    
    def _process_message(self, node_id: str, message: Dict, client_socket: socket.socket):
        """Process received message"""
        msg_type = message.get('type')
        
        if msg_type == 'bundle':
            # Received a bundle
            self._handle_bundle_received(node_id, message, client_socket)
        elif msg_type == 'ack':
            # Received an ACK
            self._handle_ack_received(node_id, message)
        elif msg_type == 'nak':
            # Received a NAK
            self._handle_nak_received(node_id, message)
    
    def _handle_bundle_received(self, node_id: str, message: Dict, client_socket: socket.socket):
        """Handle received bundle"""
        bundle_data = message.get('bundle')
        if not bundle_data:
            return
        
        # Reconstruct bundle
        bundle_id = bundle_data.get('bundle_id')
        payload = bundle_data.get('payload')
        checksum = bundle_data.get('checksum')
        
        # Verify checksum
        import zlib
        calculated_checksum = zlib.crc32(payload.encode('utf-8')) & 0xffffffff
        
        if calculated_checksum != checksum:
            # Checksum mismatch - send NAK
            print("❌ Checksum mismatch for bundle {} at {}".format(
                bundle_id[:8], node_id
            ))
            nak_message = {
                'type': 'nak',
                'bundle_id': bundle_id,
                'reason': 'checksum_mismatch',
                'expected_checksum': checksum,
                'received_checksum': calculated_checksum
            }
            self._send_message(client_socket, nak_message)
            return
        
        # Checksum valid - send ACK
        print("✅ Bundle {} received and verified at {}".format(
            bundle_id[:8], node_id
        ))
        ack_message = {
            'type': 'ack',
            'bundle_id': bundle_id,
            'checksum': checksum
        }
        self._send_message(client_socket, ack_message)
        
        # Process bundle (add to queue if not final destination)
        if node_id != bundle_data.get('destination_station', 'iss'):
            # Forward to destination or queue
            # This would integrate with the existing DTN logic
            pass
    
    def _handle_ack_received(self, node_id: str, message: Dict):
        """Handle received ACK"""
        bundle_id = message.get('bundle_id')
        ack_data = {
            'type': 'ack',
            'bundle_id': bundle_id,
            'from_station': node_id,
            'to_station': self.bundles.get(bundle_id).current_custodian if bundle_id in self.bundles else None,
            'ack_type': 'delivered' if node_id == 'iss' else 'custody_accepted',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checksum': message.get('checksum')
        }
        
        # Process ACK using parent class method
        if bundle_id in self.bundles:
            self.process_ack(bundle_id, ack_data)
    
    def _handle_nak_received(self, node_id: str, message: Dict):
        """Handle received NAK"""
        bundle_id = message.get('bundle_id')
        nak_data = {
            'type': 'nak',
            'bundle_id': bundle_id,
            'from_station': node_id,
            'to_station': self.bundles.get(bundle_id).current_custodian if bundle_id in self.bundles else None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'reason': message.get('reason', 'unknown'),
            'expected_checksum': message.get('expected_checksum'),
            'received_checksum': message.get('received_checksum')
        }
        
        # Process NAK using parent class method
        if bundle_id in self.bundles:
            self.process_nak(bundle_id, nak_data)
    
    def send_bundle_over_network(self, bundle_id: str, from_node: str, to_node: str) -> bool:
        """
        Send bundle over network using TCP socket
        
        Args:
            bundle_id: Bundle ID to send
            from_node: Source node ID
            to_node: Destination node ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        if bundle_id not in self.bundles:
            return False
        
        bundle = self.bundles[bundle_id]
        
        # Get destination IP
        if not self.topology:
            print("❌ Topology not set, cannot send bundle")
            return False
        
        dest_ip = self.topology.get_node_ip(to_node)
        if not dest_ip:
            print("❌ Cannot find IP for node {}".format(to_node))
            return False
        
        # Extract IP address (remove /24 subnet)
        dest_ip = dest_ip.split('/')[0]
        
        try:
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30.0)  # 30 second timeout
            sock.connect((dest_ip, self.DTN_PORT))
            
            # Prepare bundle message
            bundle_message = {
                'type': 'bundle',
                'bundle': {
                    'bundle_id': bundle.bundle_id,
                    'source_station': bundle.source_station,
                    'destination_station': bundle.destination_station,
                    'payload': bundle.payload,
                    'priority': bundle.priority.value,
                    'checksum': bundle.checksum,
                    'size_bytes': bundle.size_bytes
                }
            }
            
            # Send message
            success = self._send_message(sock, bundle_message)
            
            if success:
                # Wait for ACK/NAK
                response = self._receive_message(sock)
                if response:
                    if response.get('type') == 'ack':
                        self._handle_ack_received(to_node, response)
                    elif response.get('type') == 'nak':
                        self._handle_nak_received(to_node, response)
            
            sock.close()
            return success
            
        except Exception as e:
            print("❌ Error sending bundle {} to {}: {}".format(
                bundle_id[:8], to_node, e
            ))
            return False
    
    def start_transmission(self, bundle_id: str, from_station: str,
                          to_station: str, data_rate_bps: float,
                          retransmission_count: Optional[int] = None) -> Optional[BundleTransmission]:
        """
        Start transmitting a bundle over the network
        
        This extends the parent method to actually send over network
        """
        # Call parent to create transmission record
        transmission = super().start_transmission(
            bundle_id, from_station, to_station, data_rate_bps, retransmission_count
        )
        
        if transmission:
            # Send bundle over network in background thread
            def send_thread():
                # Simulate transmission time based on data rate
                transmission_time = transmission.size_bytes / (data_rate_bps / 8)
                time.sleep(transmission_time)
                
                # Send bundle
                success = self.send_bundle_over_network(bundle_id, from_station, to_station)
                
                if success:
                    # Mark as complete
                    transmission.bytes_transmitted = transmission.size_bytes
                else:
                    # Transmission failed - will be retried
                    print("❌ Transmission failed for bundle {}".format(bundle_id[:8]))
            
            thread = threading.Thread(target=send_thread)
            thread.daemon = True
            thread.start()
        
        return transmission

