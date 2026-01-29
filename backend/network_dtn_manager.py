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
        self.servers = {} 
        self.server_threads = {} 
        self.running = False
        self.message_handlers = {} 
        self.connections = {}
        self._node_locks = {}  # Per-node locks for thread-safe cmd() calls
        
        print("🌐 NetworkDTNManager initialized")
    
    def _get_node_lock(self, node_id: str) -> threading.Lock:
        """Get or create a lock for a specific node to serialize cmd() calls.
        
        Mininet's node.cmd() is NOT thread-safe - calling it from multiple threads
        simultaneously causes AssertionError. This lock ensures only one thread
        can execute cmd() on a given node at a time.
        """
        if node_id not in self._node_locks:
            self._node_locks[node_id] = threading.Lock()
        return self._node_locks[node_id]
    
    def start_servers(self):
        """Start TCP servers for all nodes within their Mininet namespaces"""
        if self.running:
            return
        
        if not self.topology:
            print("⚠️  No topology available, cannot start servers in node namespaces")
            return
        
        self.running = True
        
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
            import os
            cmd = 'python3 {} {}'.format(server_script, node_id)
            proc = node.popen(cmd, shell=True)
            
            self.servers[node_id] = proc
            print("📡 Server started for {} in node namespace (PID: {})".format(
                node_id, proc.pid if hasattr(proc, 'pid') else 'unknown'
            ))
        except Exception as e:
            print("❌ Failed to start server for {}: {}".format(node_id, e))
    
    def _handle_ack_received(self, node_id: str, message: Dict):
        """Handle received ACK"""
        bundle_id = message.get('bundle_id')
        if bundle_id not in self.bundles:
            print("⚠️  ACK received for unknown bundle {}".format(bundle_id[:8]))
            return
        
        bundle = self.bundles[bundle_id]
        # Capture sender before process_ack updates it
        sender_station = bundle.current_custodian
        
        # Check if this is the final destination
        is_final_destination = (
            node_id.lower() == 'iss' or 
            node_id.lower() == bundle.destination_station.lower()
        )
        
        ack_data = {
            'type': 'ack',
            'bundle_id': bundle_id,
            'from_station': node_id,  # Receiver
            'to_station': sender_station,  # Sender
            'ack_type': 'delivered' if is_final_destination else 'custody_accepted',
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
        
        node_id_for_lookup = to_node.lower() if to_node.lower() == 'iss' else to_node
        
        dest_ip = self.topology.get_node_ip(node_id_for_lookup)
        if not dest_ip:
            print("❌ Cannot find IP for node {} (looked up as: {})".format(to_node, node_id_for_lookup))
            node = self.topology.get_node(node_id_for_lookup)
            if node:
                print("   Node exists but IP() returned None - network may not be fully started")
            else:
                print("   Node does not exist in topology")
            return False
        
        dest_ip = dest_ip.split('/')[0]
        
        source_node = self.topology.get_node(from_node)
        if not source_node:
            print("❌ Source node {} not found in topology".format(from_node))
            return False
        
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_script = os.path.join(script_dir, 'mininet_nodes', 'dtn_client.py')
        
        import shlex
        # Use encrypted_payload (bundles are now always encrypted)
        payload_escaped = shlex.quote(bundle.encrypted_payload)
        
        # Prepare security blocks as JSON strings
        pcb_json = "null"
        pib_json = "null"
        bab_json = "null"
        payload_hash = bundle.payload_hash if hasattr(bundle, 'payload_hash') else "null"
        
        if bundle.pcb:
            pcb_json = shlex.quote(json.dumps(bundle.pcb.to_dict()))
        if bundle.pib:
            pib_json = shlex.quote(json.dumps(bundle.pib.to_dict()))
        if bundle.bab:
            bab_json = shlex.quote(json.dumps(bundle.bab.to_dict()))
        
        # Build command to run client script within source node's namespace
        # Args: dest_ip bundle_id source_station destination_station payload priority pcb pib bab payload_hash
        cmd = 'python3 {} {} {} {} {} {} {} {} {} {} {}'.format(
            client_script,
            dest_ip,
            bundle_id,
            bundle.source_station,
            bundle.destination_station,
            payload_escaped,
            bundle.priority.value,
            pcb_json,
            pib_json,
            bab_json,
            shlex.quote(payload_hash) if payload_hash != "null" else "null"
        )
        
        try:
            # Get lock for this source node to prevent concurrent cmd() calls
            # Mininet's cmd() is NOT thread-safe
            node_lock = self._get_node_lock(from_node)
            
            with node_lock:
                # Run client script within source node's namespace
                # This ensures the socket connection uses the node's network namespace
                # cmd() runs synchronously and captures stdout/stderr
                result = source_node.cmd(cmd)
            
            # Check result output for success/failure indicators
            result_lower = result.lower()
            
            # Check for success indicators
            if '✅ ack received' in result_lower or 'ack received' in result_lower:
                # Bundle was successfully sent and ACK received
                # Check if this is the final destination (ISS or the target ground station)
                is_final_destination = (
                    to_node.lower() == 'iss' or 
                    to_node.lower() == bundle.destination_station.lower()
                )
                ack_data = {
                    'type': 'ack',
                    'bundle_id': bundle_id,
                    'from_station': to_node,
                    'to_station': from_node,
                    'ack_type': 'delivered' if is_final_destination else 'custody_accepted',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'checksum': bundle.checksum
                }
                self._handle_ack_received(to_node, ack_data)
                return True
            
            # Check for failure indicators
            elif '❌' in result or 'nak received' in result_lower or 'error' in result_lower:
                failure_category = None
                error_reason = 'unknown'
                error_details = []
                
                # Check for checksum failure
                if 'checksum' in result_lower and 'mismatch' in result_lower:
                    failure_category = 'checksum_fail'
                    error_reason = 'checksum_mismatch'
                    error_details.append("Checksum verification failed at receiver")
                elif 'nak received' in result_lower:
                    failure_category = 'checksum_fail'  
                    error_reason = 'nak_received'
                    error_details.append("NAK received from receiver (likely checksum mismatch)")
                
                # Check for link down
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
                
                # Check for bundle lost
                elif not result or len(result.strip()) == 0:
                    failure_category = 'bundle_lost'
                    error_reason = 'no_response'
                    error_details.append("Bundle lost - no response from receiver (possible packet loss)")
                else:
                    # Generic error
                    failure_category = 'bundle_lost'
                    error_reason = 'transmission_error'
                    error_details.append("Bundle lost or transmission error occurred")
                
                # Log detailed failure information
                print("❌ Transmission FAILED for bundle {}: {}".format(bundle_id[:8], failure_category.upper().replace('_', ' ')))
                print("   Reason: {}".format(error_reason))
                if error_details:
                    for detail in error_details:
                        print("   → {}".format(detail))
                if result.strip():
                    print("   Raw output: {}".format(result.strip()[:200]))
                
                # Store failure reason
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
            
            print("⚠️  Could not parse client output for bundle {}, assuming success".format(bundle_id[:8]))
            print("   Output: {}".format(result.strip()[:200]))
            return True
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            failure_category = 'bundle_lost'  
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
        transmission = super().start_transmission(
            bundle_id, from_station, to_station, data_rate_bps, retransmission_count
        )
        
        if transmission:
            bundle = self.bundles.get(bundle_id)
            if bundle:
                # Use composite key for broadcasts to allow multiple simultaneous transmissions
                is_broadcast = bundle.destination_station.upper() == "BROADCAST"
                status_key = "{}:{}".format(bundle_id, to_station) if is_broadcast else bundle_id
                
                from dtn_bundle_manager import PendingAcknowledgment
                now = datetime.now(timezone.utc)
                pending_ack = PendingAcknowledgment(
                    bundle_id=bundle_id,
                    from_station=from_station,  
                    to_station=to_station,  
                    transmitted_at=now,
                    timeout_seconds=self.ACK_TIMEOUT_SECONDS,
                    retransmission_count=retransmission_count or 0,
                    max_retries=self.MAX_RETRIES,
                    data_rate_bps=data_rate_bps
                )
                # Use composite key for pending acknowledgments for broadcasts
                self.pending_acknowledgments[status_key] = pending_ack
                bundle.status = BundleStatus.WAITING_ACK
            else:
                # Fallback if bundle not found
                bundle = self.bundles.get(bundle_id)
                is_broadcast = bundle and bundle.destination_station.upper() == "BROADCAST"
                status_key = "{}:{}".format(bundle_id, to_station) if is_broadcast else bundle_id
            
            # Track network send status
            if not hasattr(self, '_network_send_status'):
                self._network_send_status = {}  
            
            # Initialize status as pending - use composite key for broadcasts
            self._network_send_status[status_key] = {'success': False, 'completed': False, 'failure_reason': None}
            
            # Capture status_key for closure
            thread_status_key = status_key
            
            # Send bundle over network in background thread
            def send_thread():
                transmission_time = transmission.size_bytes / (data_rate_bps / 8)
                time.sleep(transmission_time)
                
                # Send bundle over network
                success = self.send_bundle_over_network(bundle_id, from_station, to_station)
                
                # Update status using captured status_key
                failure_reason = self._network_send_status.get(thread_status_key, {}).get('failure_reason')
                self._network_send_status[thread_status_key] = {
                    'success': success, 
                    'completed': True,
                    'failure_reason': failure_reason
                }
                
                if success:
                    transmission.bytes_transmitted = transmission.size_bytes
            
            thread = threading.Thread(target=send_thread)
            thread.daemon = True
            thread.start()
        
        return transmission
    
    def update_transmissions(self, delta_time_sec, station_contact_states):
        """
        Update all active transmissions - override to wait for network sends and prevent false "complete" messages
        """
        completed = []
        
        for transmission_key, transmission in list(self.active_transmissions.items()):
            # Extract actual bundle_id from transmission object (transmission_key may be composite for broadcasts)
            bundle_id = transmission.bundle_id
            from_station = transmission.from_station
            is_contact_maintained = station_contact_states.get(from_station, False)
            
            if not is_contact_maintained and transmission.to_station == "ISS":
                # Contact lost! Abort transmission to ISS
                elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                print(f"⚠️  Transmission of {bundle_id[:8]} ABORTED after {elapsed:.1f}s (contact lost)")
                print(f"   Progress: {transmission.progress_percent():.1f}% ({transmission.bytes_transmitted:.0f}/{transmission.size_bytes} bytes)")
                
                bundle = self.bundles.get(bundle_id)
                if bundle:
                    bundle.status = BundleStatus.QUEUED  # Back to queue
                
                # Update DB
                self.db_manager.update_bundle_status(bundle_id=bundle_id, status=BundleStatus.QUEUED.value)
                
                del self.active_transmissions[transmission_key]
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
                    status = self._network_send_status.get(transmission_key, {'completed': False, 'success': False, 'failure_reason': None})
                    
                    if status['completed'] and status['success']:
                        elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                        print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                        print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                        print(f"   Size: {transmission.size_bytes} bytes")
                        print(f"   Actual Duration: {elapsed:.2f}s")
                        print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                        
                        completed.append((bundle_id, transmission.data_rate_bps))
                        del self.active_transmissions[transmission_key]
                    elif status['completed'] and not status['success']:
                        failure_reason = status.get('failure_reason', 'unknown')
                        bundle = self.bundles.get(bundle_id)
                        
                        if bundle and transmission:
                            transmission.retransmission_count += 1
                            retry_count = transmission.retransmission_count
                            
                            # Check if we can retry
                            if transmission.can_retry():
                                # Store retry count for retransmission
                                self.bundle_retry_counts[bundle_id] = retry_count
                                
                                # Reset bundle status and prepare for retransmission
                                bundle.status = BundleStatus.QUEUED
                                bundle.forwarded_to = None
                                
                                # Update DB
                                self.db_manager.update_bundle_status(
                                    bundle_id=bundle_id,
                                    status=BundleStatus.QUEUED.value,
                                    forwarded_to=None
                                )
                                
                                # Remove from active transmissions so it can be picked up again
                                del self.active_transmissions[transmission_key]
                                
                                # Remove from pending acknowledgments if present (use transmission_key for broadcasts)
                                if transmission_key in self.pending_acknowledgments:
                                    del self.pending_acknowledgments[transmission_key]
                                
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
                                del self.active_transmissions[transmission_key]
                                
                                # Remove from pending acknowledgments if present
                                if transmission_key in self.pending_acknowledgments:
                                    del self.pending_acknowledgments[transmission_key]
                                
                                # Mark as failed
                                self._mark_bundle_failed(bundle_id, f"{failure_reason}_max_retries")
                                
                                # Remove from queue
                                if bundle_id in self.station_queues.get(transmission.from_station, []):
                                    self.station_queues[transmission.from_station].remove(bundle_id)
                else:
                    elapsed = (datetime.now(timezone.utc) - transmission.started_at).total_seconds()
                    print(f"✅ Transmission COMPLETE: {bundle_id[:8]}")
                    print(f"   Route: {transmission.from_station} → {transmission.to_station}")
                    print(f"   Size: {transmission.size_bytes} bytes")
                    print(f"   Actual Duration: {elapsed:.2f}s")
                    print(f"   Average Rate: {(transmission.size_bytes * 8 / elapsed / 1000):.1f} kbps")
                    
                    completed.append((bundle_id, transmission.data_rate_bps))
                    del self.active_transmissions[transmission_key]
        
        return completed
    
    def complete_transmission(self, bundle_id: str, data_rate_bps: float) -> Optional[Dict]:
        """
        Complete a bundle transmission
        
        Override for NetworkDTNManager:        
        We return None here to prevent main.py from simulating an ACK 
        and causing double-processing.
        """
        return None

