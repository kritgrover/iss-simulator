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
        # Get mesh connections from topology if available
        mesh_connections = None
        if topology:
            mesh_connections = topology.get_mesh_connections()
        
        super().__init__(stations, mesh_connections=mesh_connections)
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
        source_station = bundle_data.get('source_station')
        destination_station = bundle_data.get('destination_station', 'iss')
        priority = bundle_data.get('priority', 'NORMAL')
        
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
        
        # Checksum valid - create bundle object at receiver if it doesn't exist
        # Bundle will be added to receiver's queue when ACK is processed at sender side
        # Note: In most cases, bundle should already exist (created at sender), but we create it
        # here if it doesn't exist (e.g., if sender's bundle manager was reset)
        if bundle_id not in self.bundles:
            # Create bundle object at receiver
            from dtn_bundle_manager import DTNBundle, BundlePriority
            priority_enum = BundlePriority.NORMAL
            if priority.upper() == "EXPEDITED":
                priority_enum = BundlePriority.EXPEDITED
            elif priority.upper() == "BULK":
                priority_enum = BundlePriority.BULK
            
            bundle = DTNBundle(
                bundle_id=bundle_id,
                source_station=source_station,
                destination_station=destination_station,
                payload=payload,
                priority=priority_enum,
                created_at=datetime.now(timezone.utc),
                ttl_hours=24,  # Default TTL
                current_custodian=node_id,  # Receiver becomes custodian when bundle is received
                hops=[source_station]  # Start with source station, will be updated when ACK processed
            )
            self.bundles[bundle_id] = bundle
            print("📦 Bundle {} created at receiver {} (will be queued when ACK processed)".format(
                bundle_id[:8], node_id
            ))
        
        # Send ACK
        print("✅ Bundle {} received and verified at {}".format(
            bundle_id[:8], node_id
        ))
        ack_message = {
            'type': 'ack',
            'bundle_id': bundle_id,
            'checksum': checksum
        }
        self._send_message(client_socket, ack_message)
    
    def _handle_ack_received(self, node_id: str, message: Dict):
        """Handle received ACK"""
        bundle_id = message.get('bundle_id')
        if bundle_id not in self.bundles:
            print("⚠️  ACK received for unknown bundle {}".format(bundle_id[:8]))
            return
        
        bundle = self.bundles[bundle_id]
        # Capture sender (current custodian) before process_ack updates it
        sender_station = bundle.current_custodian
        
        ack_data = {
            'type': 'ack',
            'bundle_id': bundle_id,
            'from_station': node_id,  # Receiver
            'to_station': sender_station,  # Sender
            'ack_type': 'delivered' if node_id.lower() == 'iss' else 'custody_accepted',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checksum': message.get('checksum')
        }
        
        # Process ACK using parent class method
        # This will move bundle from sender's queue to receiver's queue
        self.process_ack(bundle_id, ack_data)
        
        # Queue ACK for display in message terminal
        # Format ACK for frontend display
        custody_ack = {
            'type': 'custody_ack',
            'bundle_id': bundle_id,
            'bundle_id_short': bundle_id[:8],
            'from_station': node_id,  # Receiver (who accepted custody)
            'to_station': sender_station,  # Sender (who sent the bundle)
            'ack_type': ack_data['ack_type'],
            'timestamp': ack_data['timestamp']
        }
        self.queue_ack(custody_ack)
    
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
        Send bundle over network using TCP socket from within source node's namespace
        
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
        
        # Handle ISS node name (case-insensitive)
        node_id_for_lookup = to_node.lower() if to_node.lower() == 'iss' else to_node
        
        dest_ip = self.topology.get_node_ip(node_id_for_lookup)
        if not dest_ip:
            print("❌ Cannot find IP for node {} (looked up as: {})".format(to_node, node_id_for_lookup))
            # Debug: Check if node exists
            node = self.topology.get_node(node_id_for_lookup)
            if node:
                print("   Node exists but IP() returned None - network may not be fully started")
            else:
                print("   Node does not exist in topology")
            return False
        
        # Extract IP address (remove /24 subnet)
        dest_ip = dest_ip.split('/')[0]
        
        # Get source node to run client from its namespace
        source_node = self.topology.get_node(from_node)
        if not source_node:
            print("❌ Source node {} not found in topology".format(from_node))
            return False
        
        # Get path to client script
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_script = os.path.join(script_dir, 'mininet_nodes', 'dtn_client.py')
        
        # Escape payload for shell (handle quotes and special chars)
        import shlex
        payload_escaped = shlex.quote(bundle.payload)
        
        # Build command to run client script within source node's namespace
        cmd = 'python3 {} {} {} {} {} {} {}'.format(
            client_script,
            dest_ip,
            bundle_id,
            bundle.source_station,
            bundle.destination_station,
            payload_escaped,
            bundle.priority.value
        )
        
        try:
            # Run client script within source node's namespace
            # This ensures the socket connection uses the node's network namespace
            # cmd() runs synchronously and captures stdout/stderr
            result = source_node.cmd(cmd)
            
            # Check result output for success/failure indicators
            result_lower = result.lower()
            
            # Check for success indicators
            if '✅ ack received' in result_lower or 'ack received' in result_lower:
                # Bundle was successfully sent and ACK received
                ack_data = {
                    'type': 'ack',
                    'bundle_id': bundle_id,
                    'from_station': to_node,
                    'to_station': from_node,
                    'ack_type': 'custody_accepted' if to_node.lower() != 'iss' else 'delivered',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'checksum': bundle.checksum
                }
                self._handle_ack_received(to_node, ack_data)
                return True
            
            # Check for failure indicators and extract detailed error information
            elif '❌' in result or 'nak received' in result_lower or 'error' in result_lower:
                # Categorize failure type
                failure_category = None
                error_reason = 'unknown'
                error_details = []
                
                # Check for checksum failure (highest priority - explicit NAK)
                if 'checksum' in result_lower and 'mismatch' in result_lower:
                    failure_category = 'checksum_fail'
                    error_reason = 'checksum_mismatch'
                    error_details.append("Checksum verification failed at receiver")
                elif 'nak received' in result_lower:
                    failure_category = 'checksum_fail'  # NAK usually means checksum failure
                    error_reason = 'nak_received'
                    error_details.append("NAK received from receiver (likely checksum mismatch)")
                
                # Check for link down (connection issues)
                elif 'connection refused' in result_lower or 'connectionrefusederror' in result_lower:
                    failure_category = 'link_down'
                    error_reason = 'connection_refused'
                    error_details.append("Link is down - destination server not listening or not reachable")
                elif 'no route to host' in result_lower or 'network is unreachable' in result_lower:
                    failure_category = 'link_down'
                    error_reason = 'no_route'
                    error_details.append("Link is down - no network route to destination")
                
                # Check for timeout
                elif 'timeout' in result_lower or 'timed out' in result_lower or 'connection timeout' in result_lower:
                    failure_category = 'timeout'
                    error_reason = 'timeout'
                    error_details.append("Timeout - connection or operation timed out (30s)")
                
                # Check for bundle lost (no response, empty output, etc.)
                elif not result or len(result.strip()) == 0:
                    failure_category = 'bundle_lost'
                    error_reason = 'no_response'
                    error_details.append("Bundle lost - no response from receiver (possible packet loss)")
                else:
                    # Generic error - could be bundle lost or other issue
                    failure_category = 'bundle_lost'
                    error_reason = 'transmission_error'
                    error_details.append("Bundle lost or transmission error occurred")
                
                # Log detailed failure information with category
                print("❌ Transmission FAILED for bundle {}: {}".format(bundle_id[:8], failure_category.upper().replace('_', ' ')))
                print("   Reason: {}".format(error_reason))
                if error_details:
                    for detail in error_details:
                        print("   → {}".format(detail))
                # Also print the raw output for debugging (truncated)
                if result.strip():
                    print("   Raw output: {}".format(result.strip()[:200]))
                
                # Store failure reason for later reference
                if hasattr(self, '_network_send_status') and bundle_id in self._network_send_status:
                    self._network_send_status[bundle_id]['failure_reason'] = failure_category
                
                # Transmission failed - create NAK
                nak_data = {
                    'type': 'nak',
                    'bundle_id': bundle_id,
                    'from_station': to_node,
                    'to_station': from_node,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'reason': error_reason
                }
                self._handle_nak_received(to_node, nak_data)
                return False
            
            # If we can't determine from output, check if command completed
            if not result or len(result.strip()) == 0:
                failure_category = 'bundle_lost'
                print("❌ Transmission FAILED for bundle {}: {}".format(bundle_id[:8], failure_category.upper().replace('_', ' ')))
                print("   Reason: No response from client script (possible timeout, crash, or bundle lost)")
                
                # Store failure reason
                if hasattr(self, '_network_send_status') and bundle_id in self._network_send_status:
                    self._network_send_status[bundle_id]['failure_reason'] = failure_category
                
                return False
            
            # If we got here, couldn't parse result but command completed
            # This is suspicious - log warning but assume success for now
            print("⚠️  Could not parse client output for bundle {}, assuming success".format(bundle_id[:8]))
            print("   Output: {}".format(result.strip()[:200]))
            return True
                
        except Exception as e:
            # Capture exception details and categorize failure
            error_type = type(e).__name__
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            # Categorize exception-based failures
            failure_category = 'bundle_lost'  # Default to bundle lost for exceptions
            if 'timeout' in error_msg_lower or 'timed out' in error_msg_lower:
                failure_category = 'timeout'
            elif 'connection' in error_msg_lower or 'refused' in error_msg_lower:
                failure_category = 'link_down'
            elif 'network' in error_msg_lower or 'route' in error_msg_lower or 'unreachable' in error_msg_lower:
                failure_category = 'link_down'
            
            print("❌ Transmission FAILED for bundle {}: {}".format(
                bundle_id[:8], failure_category.upper().replace('_', ' ')
            ))
            print("   Exception: {} - {}".format(error_type, error_msg))
            import traceback
            print("   Traceback: {}".format(traceback.format_exc().split('\n')[-2]))  # Last meaningful line
            
            # Store failure reason
            if hasattr(self, '_network_send_status') and bundle_id in self._network_send_status:
                self._network_send_status[bundle_id]['failure_reason'] = failure_category
            
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
            # Create pending acknowledgment for timeout handling
            # In mininet, ACK comes back through network, but we need pending_ack for timeout tracking
            bundle = self.bundles.get(bundle_id)
            if bundle:
                from dtn_bundle_manager import PendingAcknowledgment
                now = datetime.now(timezone.utc)
                pending_ack = PendingAcknowledgment(
                    bundle_id=bundle_id,
                    from_station=from_station,  # Current custodian (sender)
                    to_station=to_station,  # Destination
                    transmitted_at=now,
                    timeout_seconds=self.ACK_TIMEOUT_SECONDS,
                    retransmission_count=retransmission_count or 0,
                    max_retries=self.MAX_RETRIES,
                    data_rate_bps=data_rate_bps
                )
                self.pending_acknowledgments[bundle_id] = pending_ack
                bundle.status = BundleStatus.WAITING_ACK
            
            # Track network send status
            if not hasattr(self, '_network_send_status'):
                self._network_send_status = {}  # bundle_id -> (success: bool, completed: bool, failure_reason: str)
            
            # Initialize status as pending
            self._network_send_status[bundle_id] = {'success': False, 'completed': False, 'failure_reason': None}
            
            # Send bundle over network in background thread
            def send_thread():
                # Simulate transmission time based on data rate
                transmission_time = transmission.size_bytes / (data_rate_bps / 8)
                time.sleep(transmission_time)
                
                # Send bundle over network
                success = self.send_bundle_over_network(bundle_id, from_station, to_station)
                
                # Update status
                failure_reason = self._network_send_status.get(bundle_id, {}).get('failure_reason')
                self._network_send_status[bundle_id] = {
                    'success': success, 
                    'completed': True,
                    'failure_reason': failure_reason
                }
                
                if success:
                    # Mark as complete
                    transmission.bytes_transmitted = transmission.size_bytes
                else:
                    # Transmission failed - failure reason already logged in send_bundle_over_network
                    # Don't mark bytes as transmitted so it won't be marked as complete
                    pass
            
            thread = threading.Thread(target=send_thread)
            thread.daemon = True
            thread.start()
        
        return transmission
    
    def update_transmissions(self, delta_time_sec, station_contact_states):
        """
        Update all active transmissions - override to wait for network sends and prevent false "complete" messages
        """
        completed = []
        
        for bundle_id, transmission in list(self.active_transmissions.items()):
            # Check if contact is maintained (for ISS transmissions)
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
            
            # Update bytes transmitted (simulated progress)
            bytes_this_tick = (transmission.data_rate_bps / 8) * delta_time_sec
            transmission.bytes_transmitted = min(
                transmission.size_bytes,
                transmission.bytes_transmitted + bytes_this_tick
            )
            
            # Check if simulated transmission is complete
            if transmission.is_complete():
                # Check if network send actually completed successfully
                if hasattr(self, '_network_send_status'):
                    status = self._network_send_status.get(bundle_id, {'completed': False, 'success': False, 'failure_reason': None})
                    
                    if status['completed'] and status['success']:
                        # Network send succeeded - transmission is really complete
                        elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                        print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                        print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                        print(f"   Size: {transmission.size_bytes} bytes")
                        print(f"   Actual Duration: {elapsed:.2f}s")
                        print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                        
                        completed.append((bundle_id, transmission.data_rate_bps))
                        del self.active_transmissions[bundle_id]
                    elif status['completed'] and not status['success']:
                        # Network send failed - prepare for retransmission
                        # Failure reason already logged in send_bundle_over_network
                        failure_reason = status.get('failure_reason', 'unknown')
                        bundle = self.bundles.get(bundle_id)
                        transmission = self.active_transmissions.get(bundle_id)
                        
                        if bundle and transmission:
                            # Increment retry count
                            transmission.retransmission_count += 1
                            retry_count = transmission.retransmission_count
                            
                            # Check if we can retry
                            if transmission.can_retry():
                                # Store retry count for retransmission
                                self.bundle_retry_counts[bundle_id] = retry_count
                                
                                # Reset bundle status and prepare for retransmission
                                bundle.status = BundleStatus.QUEUED
                                bundle.forwarded_to = None
                                
                                # Remove from active transmissions so it can be picked up again
                                del self.active_transmissions[bundle_id]
                                
                                # Remove from pending acknowledgments if present
                                if bundle_id in self.pending_acknowledgments:
                                    del self.pending_acknowledgments[bundle_id]
                                
                                print("⚠️  Bundle {} transmission failed ({}), requeuing for retry (attempt {}/{})".format(
                                    bundle_id[:8], 
                                    failure_reason.replace('_', ' ') if failure_reason else 'unknown',
                                    retry_count + 1,
                                    transmission.max_retries + 1
                                ))
                            else:
                                # Max retries exceeded - mark as failed
                                print("❌ Bundle {} FAILED - max retries exceeded ({}), marking as expired".format(
                                    bundle_id[:8],
                                    failure_reason.replace('_', ' ') if failure_reason else 'unknown'
                                ))
                                bundle.status = BundleStatus.EXPIRED
                                bundle.forwarded_to = None
                                
                                # Remove from active transmissions
                                del self.active_transmissions[bundle_id]
                                
                                # Remove from pending acknowledgments if present
                                if bundle_id in self.pending_acknowledgments:
                                    del self.pending_acknowledgments[bundle_id]
                                
                                # Mark as failed
                                self._mark_bundle_failed(bundle_id, f"{failure_reason}_max_retries")
                                
                                # Remove from queue
                                if bundle_id in self.station_queues.get(transmission.from_station, []):
                                    self.station_queues[transmission.from_station].remove(bundle_id)
                    else:
                        # Network send still in progress - wait for it
                        # Don't mark as complete yet
                        pass
                else:
                    # No network send status tracking - use parent behavior
                    elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                    print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                    print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                    print(f"   Size: {transmission.size_bytes} bytes")
                    print(f"   Actual Duration: {elapsed:.2f}s")
                    print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                    
                    completed.append((bundle_id, transmission.data_rate_bps))
                    del self.active_transmissions[bundle_id]
        
        return completed

