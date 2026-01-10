"""
Mininet Topology Manager for ISS Simulator

Creates a network topology with:
- ISS node (central)
- Ground stations in partial mesh (geographic proximity-based)
- Dynamic ISS-ground station links based on visibility
"""

import math
from typing import Dict, List, Optional, Tuple
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, Controller, RemoteController, UserSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance between two points in km"""
    R = 6371.0  # Earth radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


class ISSTopology:
    """Manages Mininet topology for ISS and ground stations"""
    
    # Ground link parameters (terrestrial fiber/backbone)
    GROUND_BANDWIDTH_MBPS = 100  # 100 Mbps
    GROUND_DELAY_MS = 50  # 50ms base delay
    GROUND_LOSS_PERCENT = 20  # 20% packet loss
    
    # Base ISS link parameters (will be updated dynamically)
    ISS_BASE_BANDWIDTH_MBPS = 0.2  # 200 kbps
    ISS_BASE_DELAY_MS = 10  # 10ms base delay
    ISS_BASE_LOSS_PERCENT = 40 # 40% base packet loss
    
    def __init__(self, ground_stations: List[Dict]):
        """
        Initialize topology
        
        Args:
            ground_stations: List of dicts with 'id', 'name', 'lat', 'lon'
        """
        self.ground_stations = ground_stations
        self.net = None
        self.iss_node = None
        self.station_nodes = {}
        self.ground_links = {}  # (station1, station2) -> link
        self.iss_links = {}  # station_id -> link
        self.switch = None
        
        # Calculate ground station mesh connections (partial mesh)
        self.mesh_connections = self._calculate_mesh_topology()
        
        info("🌐 ISSTopology initialized with {} ground stations\n".format(len(ground_stations)))
    
    def _calculate_mesh_topology(self) -> List[Tuple[str, str]]:
        """
        Calculate partial mesh topology - each station connects to 3 nearest neighbors
        Returns list of (station1_id, station2_id) tuples
        """
        connections = []
        station_ids = [s["id"] for s in self.ground_stations]
        
        for i, station1 in enumerate(self.ground_stations):
            # Calculate distances to all other stations
            distances = []
            for j, station2 in enumerate(self.ground_stations):
                if i != j:
                    dist = calculate_distance(
                        station1["lat"], station1["lon"],
                        station2["lat"], station2["lon"]
                    )
                    distances.append((dist, station2["id"]))
            
            # Sort by distance and connect to 3 nearest
            distances.sort(key=lambda x: x[0])
            for dist, station2_id in distances[:3]:
                # Avoid duplicate connections (only add if station1 < station2)
                if station1["id"] < station2_id:
                    connections.append((station1["id"], station2_id))
                elif station2_id < station1["id"]:
                    # Check if reverse connection already exists
                    if (station2_id, station1["id"]) not in connections:
                        connections.append((station1["id"], station2_id))
        
        info("📡 Mesh topology: {} ground station connections\n".format(len(connections)))
        return connections
    
    def build(self):
        """Build the Mininet topology"""
        setLogLevel('info')
        
        info("🔨 Building Mininet topology...\n")
        
        # Create network - use OVSSwitch in standalone mode (no controller needed)
        try:
            self.net = Mininet(controller=None, link=TCLink, switch=OVSSwitch)
            info("📡 Using OVS switch in standalone mode (no controller required)\n")
        except Exception as e1:
            error("❌ Failed to create network with OVS standalone: {}\n".format(e1))
            error("💡 Try installing OpenVSwitch: sudo apt-get install openvswitch-switch\n")
            raise RuntimeError("Could not initialize Mininet network. Error: {}".format(e1))
        
        # Add switch for ground station network
        self.switch = self.net.addSwitch('s1')
        
        # Create ISS node
        self.iss_node = self.net.addHost('iss', ip='10.0.0.100/24')
        info("🛰️  Created ISS node: {}\n".format(self.iss_node.name))
        
        # Create ground station nodes
        for ip_index, station in enumerate(self.ground_stations, start=1):
            station_id = station["id"]
            # Use station ID as hostname, IP based on index
            ip_address = '10.0.0.{}/24'.format(ip_index)
            host = self.net.addHost(
                station_id,
                ip=ip_address
            )
            self.station_nodes[station_id] = host
            info("📡 Created ground station node: {} ({})\n".format(
                station_id, ip_address
            ))
        
        # Connect ground stations to switch
        for station_id, host in self.station_nodes.items():
            link = self.net.addLink(host, self.switch)
            # Set ground link parameters (high bandwidth, low delay)
            link.intf1.config(bw=self.GROUND_BANDWIDTH_MBPS, delay='{}ms'.format(self.GROUND_DELAY_MS), loss=self.GROUND_LOSS_PERCENT)
            link.intf2.config(bw=self.GROUND_BANDWIDTH_MBPS, delay='{}ms'.format(self.GROUND_DELAY_MS), loss=self.GROUND_LOSS_PERCENT)
        
        # Connect ISS to switch (will be used for dynamic links)
        iss_link = self.net.addLink(self.iss_node, self.switch)
        iss_link.intf1.config(bw=self.ISS_BASE_BANDWIDTH_MBPS, delay='{}ms'.format(self.ISS_BASE_DELAY_MS), loss=self.ISS_BASE_LOSS_PERCENT)
        iss_link.intf2.config(bw=self.ISS_BASE_BANDWIDTH_MBPS, delay='{}ms'.format(self.ISS_BASE_DELAY_MS), loss=self.ISS_BASE_LOSS_PERCENT)
        
        info("✅ Topology built successfully\n")
    
    def start(self):
        """Start the network"""
        if self.net is None:
            raise RuntimeError("Topology not built. Call build() first.")
        
        info("🚀 Starting Mininet network...\n")
        self.net.start()
        
        # Configure OVS switch to work in standalone mode (no controller)
        if self.switch and hasattr(self.switch, 'cmd'):
            try:
                self.switch.cmd('ovs-vsctl set-fail-mode', self.switch.name, 'standalone')
                self.switch.cmd('ovs-vsctl del-controller', self.switch.name)
                info("✅ Configured {} to run in standalone mode\n".format(self.switch.name))
            except Exception as e:
                # If ovs-vsctl commands fail, switch might still work
                info("⚠️  Could not configure standalone mode (may still work): {}\n".format(e))
        
        # Give network a moment to fully initialize interfaces
        import time
        time.sleep(0.5)
        
        # Verify all nodes have interfaces
        for station_id, node in self.station_nodes.items():
            try:
                if not node.intfs:
                    error("⚠️  Warning: {} has no interfaces after network start\n".format(station_id))
                else:
                    info("✅ {} has {} interface(s)\n".format(station_id, len(node.intfs)))
            except Exception as e:
                error("⚠️  Error checking interfaces for {}: {}\n".format(station_id, e))
        
        info("✅ Network started\n")
    
    def stop(self):
        """Stop the network"""
        if self.net is None:
            return
        
        info("🛑 Stopping Mininet network...\n")
        self.net.stop()
        info("✅ Network stopped\n")
    
    def create_iss_link(self, station_id: str, bandwidth_mbps: float, 
                        delay_ms: float, loss_percent: float):
        """
        Create or update ISS link to a ground station
        
        Args:
            station_id: Ground station ID
            bandwidth_mbps: Link bandwidth in Mbps
            delay_ms: Link delay in milliseconds
            loss_percent: Packet loss percentage
        """
        if station_id not in self.station_nodes:
            error("❌ Station {} not found\n".format(station_id))
            return
        
        if not self.net or not hasattr(self.net, 'running') or not self.net.running:
            # Network not running yet, just store parameters
            self.iss_links[station_id] = {
                'bandwidth_mbps': bandwidth_mbps,
                'delay_ms': delay_ms,
                'loss_percent': loss_percent,
                'station_node': self.station_nodes[station_id]
            }
            return
        
        if station_id in self.iss_links:
            # Update existing link parameters
            self.update_iss_link(station_id, bandwidth_mbps, delay_ms, loss_percent)
            return
        
        # Store link info
        self.iss_links[station_id] = {
            'bandwidth_mbps': bandwidth_mbps,
            'delay_ms': delay_ms,
            'loss_percent': loss_percent,
            'station_node': self.station_nodes[station_id]
        }
        
        # Apply link parameters using tc commands
        self._apply_link_parameters(station_id, bandwidth_mbps, delay_ms, loss_percent)
        
        info("🔗 Created ISS link to {}: {} Mbps, {} ms delay, {}% loss\n".format(
            station_id, bandwidth_mbps, delay_ms, loss_percent
        ))
    
    def update_iss_link(self, station_id: str, bandwidth_mbps: float,
                       delay_ms: float, loss_percent: float, log_update: bool = True):
        """
        Update ISS link parameters using tc commands
        
        Args:
            station_id: Ground station ID
            bandwidth_mbps: New bandwidth in Mbps
            delay_ms: New delay in milliseconds
            loss_percent: New packet loss percentage
            log_update: Whether to log the update (default: True)
        """
        if not self.net or not hasattr(self.net, 'running') or not self.net.running:
            # Network not running
            return
        
        if station_id not in self.iss_links:
            # Create link if it doesn't exist
            self.create_iss_link(station_id, bandwidth_mbps, delay_ms, loss_percent)
            return
        
        # Update stored parameters
        self.iss_links[station_id].update({
            'bandwidth_mbps': bandwidth_mbps,
            'delay_ms': delay_ms,
            'loss_percent': loss_percent
        })
        
        # Apply link parameters using tc commands
        self._apply_link_parameters(station_id, bandwidth_mbps, delay_ms, loss_percent)
        
        if log_update:
            info("🔄 Updated ISS link to {}: {} Mbps, {} ms delay, {}% loss\n".format(
                station_id, bandwidth_mbps, delay_ms, loss_percent
            ))
    
    def _apply_link_parameters(self, station_id: str, bandwidth_mbps: float,
                              delay_ms: float, loss_percent: float):
        """
        Apply link parameters using tc (traffic control) commands
        """
        if self.net is None or not self.net.running:
            return

        # Get the station node and ISS node
        station_node = self.station_nodes.get(station_id)
        if not station_node:
            error("❌ Station {} not found for link update\n".format(station_id))
            return

        if not self.iss_node:
            error("❌ ISS node not found\n")
            return

        # Find links to the switch
        station_links = self.net.linksBetween(station_node, self.switch)
        iss_links = self.net.linksBetween(self.iss_node, self.switch)
        
        if not station_links or not iss_links:
            return
        
        station_link = station_links[0]
        iss_link = iss_links[0]
        
        # Get the interfaces on the nodes (not the switch side)
        if station_link.intf1.node == station_node:
            station_intf = station_link.intf1
        else:
            station_intf = station_link.intf2
            
        if iss_link.intf1.node == self.iss_node:
            iss_intf = iss_link.intf1
        else:
            iss_intf = iss_link.intf2
            
        # Apply parameters using Mininet's config method (which uses tc under the hood)
        try:
            # Update station interface (uplink/downlink)
            station_intf.config(bw=bandwidth_mbps, delay='{}ms'.format(delay_ms), loss=loss_percent)
            
            # Update ISS interface
            iss_intf.config(bw=bandwidth_mbps, delay='{}ms'.format(delay_ms), loss=loss_percent)
            
        except Exception as e:
            error("❌ Failed to apply link parameters: {}\n".format(e))
    
    def get_node(self, node_id: str) -> Optional[Host]:
        """Get a node by ID (case-insensitive for ISS)"""
        node_id_lower = node_id.lower()
        if node_id_lower == 'iss':
            return self.iss_node
        return self.station_nodes.get(node_id)
    
    def get_node_ip(self, node_id: str) -> Optional[str]:
        """Get IP address of a node (case-insensitive for ISS)"""
        # Handle ISS case-insensitively
        node_id_lower = node_id.lower()
        if node_id_lower == 'iss':
            node = self.iss_node
        else:
            node = self.get_node(node_id)
        
        if node:
            try:
                ip = node.IP()
                if ip:
                    return ip
            except (AttributeError, RuntimeError) as e:
                error("❌ Error getting IP for {}: {}\n".format(node_id, e))
            return None
        return None
    
    def ping_test(self, source: str, target: str) -> bool:
        """Test connectivity between two nodes"""
        source_node = self.get_node(source)
        target_node = self.get_node(target)
        
        if not source_node or not target_node:
            return False
        
        result = source_node.cmd('ping -c 1 {}'.format(target_node.IP()))
        return '1 received' in result
    
    def get_mesh_connections(self) -> List[Tuple[str, str]]:
        """Get list of ground station mesh connections"""
        return self.mesh_connections


def create_topology(ground_stations: List[Dict]) -> ISSTopology:
    """Factory function to create and build topology"""
    topology = ISSTopology(ground_stations)
    topology.build()
    return topology


if __name__ == '__main__':
    # Test topology
    test_stations = [
        {"id": "toronto", "name": "Toronto", "lat": 43.6532, "lon": -79.3832},
        {"id": "london", "name": "London", "lat": 51.5074, "lon": -0.1278},
        {"id": "tokyo", "name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    ]
    
    topo = create_topology(test_stations)
    topo.start()
    
    try:
        # Test ping
        print("Testing connectivity...")
        print("ISS -> Toronto:", topo.ping_test('iss', 'toronto'))
        print("Toronto -> London:", topo.ping_test('toronto', 'london'))
        
        from mininet.cli import CLI
        CLI(topo.net)
    finally:
        topo.stop()

