from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
import json
import os
from datetime import datetime, timezone
from collections import deque
from tle_fetcher import TLEFetcher
from orbital_tracker import OrbitalTracker
from link_budget_calculator import LinkBudgetCalculator
from dtn_bundle_manager import DTNBundleManager, BundlePriority, BundleStatus

# Mininet imports (optional - fallback if not available)
USE_MININET = os.environ.get('USE_MININET', 'false').lower() == 'true'
if USE_MININET:
    try:
        from mininet_topology import ISSTopology, create_topology
        from link_parameter_manager import LinkParameterManager
        from network_dtn_manager import NetworkDTNManager
        MININET_AVAILABLE = True
    except ImportError as e:
        print("⚠️  Mininet not available: {}. Using simulation mode.".format(e))
        MININET_AVAILABLE = False
        USE_MININET = False
else:
    MININET_AVAILABLE = False

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
tle_fetcher = TLEFetcher()
link_budget_calc = LinkBudgetCalculator()

# Ground stations
GROUND_STATIONS = [
    {"id": "toronto", "name": "Toronto", "lat": 43.6532, "lon": -79.3832},
    {"id": "london", "name": "London", "lat": 51.5074, "lon": -0.1278},
    {"id": "tokyo", "name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"id": "sydney", "name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"id": "washington", "name": "Washington DC", "lat": 38.9072, "lon": -77.0369},
    {"id": "singapore", "name": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"id": "bengaluru", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"id": "saopaulo", "name": "São Paulo", "lat": -23.5505, "lon": -46.6333},
    {"id": "moscow", "name": "Moscow", "lat": 55.7558, "lon": 37.6173},
]

MIN_ELEVATION_FOR_VISIBILITY = -5.0

# Initialize Mininet topology and network DTN manager (if enabled)
topology = None
link_param_manager = None
if USE_MININET and MININET_AVAILABLE:
    try:
        print("🌐 Initializing Mininet topology...")
        topology = create_topology(GROUND_STATIONS)
        topology.start()
        link_param_manager = LinkParameterManager()
        dtn_manager = NetworkDTNManager(GROUND_STATIONS, topology)
        dtn_manager.start_servers()
        print("✅ Mininet network simulation enabled")
    except Exception as e:
        print("❌ Failed to initialize Mininet: {}. Falling back to simulation mode.".format(e))
        topology = None
        link_param_manager = None
        dtn_manager = DTNBundleManager(GROUND_STATIONS, mesh_connections=None)
        USE_MININET = False
else:
    # Initialize standard DTN Bundle Manager (simulation mode)
    dtn_manager = DTNBundleManager(GROUND_STATIONS, mesh_connections=None)
    print("📊 Using simulation mode (Mininet disabled)")

# Pydantic models for API
class BundleCreateRequest(BaseModel):
    source_station: str
    destination: str = "ISS"
    payload: str
    priority: str = "NORMAL"
    ttl_hours: int = 24

@app.get("/")
async def root():
    return {
        "message": "ISS Orbital Tracking Backend with DTN",
        "stations": len(GROUND_STATIONS),
        "min_elevation": MIN_ELEVATION_FOR_VISIBILITY
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Basic heartbeat websocket"""
    await websocket.accept()
    print("✅ Client connected to /ws")
    
    try:
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print("❌ Client disconnected from /ws")

@app.websocket("/ws/orbital_tracking")
async def orbital_tracking_websocket(websocket: WebSocket):
    """Real-time ISS tracking with DTN bundle management"""
    await websocket.accept()
    print("✅ Client connected to /ws/orbital_tracking")
    
    try:
        # Fetch TLE data
        tle = tle_fetcher.get_tle()
        if not tle:
            await websocket.send_json({
                "type": "error",
                "message": "Could not fetch TLE data"
            })
            await websocket.close()
            return
        
        # Initialize tracker
        tracker = OrbitalTracker(tle)
        link_budget_history = deque(maxlen=300)
        
        # Send initial connection
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Orbital tracking with realistic DTN transmission initialized",
            "stations": GROUND_STATIONS,
            "min_elevation": MIN_ELEVATION_FOR_VISIBILITY
        })
        
        # Calculate orbital path
        orbital_path = tracker.get_orbital_path(minutes=95, points=150)
        last_path_update = datetime.now(timezone.utc)
        
        print("🚀 Starting orbital tracking with realistic DTN transmission...")
        
        iteration = 0
        current_active_station = None
        last_update_time = datetime.now(timezone.utc)
        last_link_log_time = datetime.now(timezone.utc)  # Track when to log link updates
        
        while True:
            iteration += 1
            now = datetime.now(timezone.utc)
            delta_time = (now - last_update_time).total_seconds()
            last_update_time = now
            
            # Get ISS position
            iss_position = tracker.get_current_position()
            
            # Calculate for all stations
            stations_data = []
            visible_stations = []
            
            for station in GROUND_STATIONS:
                look_angles = tracker.calculate_look_angles(station["lat"], station["lon"])
                is_visible = look_angles["elevation"] > MIN_ELEVATION_FOR_VISIBILITY
                
                next_pass = tracker.predict_next_pass(
                    station["lat"], 
                    station["lon"],
                    min_elevation=MIN_ELEVATION_FOR_VISIBILITY
                )
                
                pass_window = None
                if is_visible:
                    pass_window = tracker.calculate_pass_window(
                        station["lat"],
                        station["lon"],
                        min_elevation=MIN_ELEVATION_FOR_VISIBILITY
                    )
                
                station_data = {
                    "id": station["id"],
                    "name": station["name"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "look_angles": look_angles,
                    "is_visible": is_visible,
                    "next_pass_minutes": next_pass["minutes_until"],
                    "next_pass_time": next_pass["start_time"],
                    "pass_window": pass_window
                }
                
                stations_data.append(station_data)
                
                if is_visible:
                    visible_stations.append(station_data)
            
            # Determine active station (highest elevation among visible)
            if visible_stations:
                visible_stations.sort(key=lambda s: s["look_angles"]["elevation"], reverse=True)
                new_active_station = visible_stations[0]["id"]
                
                if current_active_station and current_active_station != new_active_station:
                    print(f"🔄 HANDOFF: {current_active_station} → {new_active_station}")
                
                current_active_station = new_active_station
            else:
                stations_data.sort(key=lambda s: s["next_pass_minutes"] if s["next_pass_minutes"] > 0 else 999999)
                current_active_station = None
            
            # Build station contact state map
            station_contact_states = {}
            for station_data in stations_data:
                station_contact_states[station_data["id"]] = station_data["is_visible"]
            
            # Update ongoing transmissions (realistic time-based progress)
            completed_bundles = dtn_manager.update_transmissions(
                delta_time,
                station_contact_states
            )
            
            # Complete transmissions - receiver verifies checksum and generates ACK/NAK
            for bundle_info in completed_bundles:
                if isinstance(bundle_info, tuple):
                    bundle_id, data_rate_bps = bundle_info
                else:
                    # Backward compatibility
                    bundle_id = bundle_info
                    data_rate_bps = 100_000_000.0
                
                bundle = dtn_manager.bundles.get(bundle_id)
                if bundle:
                    # Receiver verifies checksum and generates ACK/NAK
                    ack_or_nak = dtn_manager.complete_transmission(bundle_id, data_rate_bps)
                    
                    if ack_or_nak:
                        # Create pending acknowledgment on sender side
                        from_station = bundle.current_custodian
                        to_station = bundle.forwarded_to if bundle.forwarded_to else "unknown"
                        
                        now = datetime.now(timezone.utc)
                        from dtn_bundle_manager import PendingAcknowledgment
                        pending_ack = PendingAcknowledgment(
                            bundle_id=bundle_id,
                            from_station=from_station,
                            to_station=to_station,
                            transmitted_at=now,
                            timeout_seconds=dtn_manager.ACK_TIMEOUT_SECONDS,
                            retransmission_count=0,
                            max_retries=dtn_manager.MAX_RETRIES,
                            data_rate_bps=data_rate_bps
                        )
                        dtn_manager.pending_acknowledgments[bundle_id] = pending_ack
                        bundle.status = BundleStatus.WAITING_ACK
                        
                        if ack_or_nak.get("type") == "ack":
                            # Process ACK at sender - removes bundle from queue and pending_ack
                            dtn_manager.process_ack(bundle_id, ack_or_nak)
                        elif ack_or_nak.get("type") == "nak":
                            # Process NAK at sender - will update retry count and schedule retransmission
                            dtn_manager.process_nak(bundle_id, ack_or_nak)
            
            # Check for timeouts in pending acknowledgments
            retransmitted_bundles_info = dtn_manager.check_timeouts(station_contact_states)
            
            # Store retransmission info for bundles that need to be retransmitted
            retransmission_map = {}  # bundle_id -> (retry_count, data_rate_bps)
            retransmitted_bundle_ids = []
            for retrans_info in retransmitted_bundles_info:
                if isinstance(retrans_info, tuple) and len(retrans_info) == 3:
                    bundle_id, retry_count, data_rate_bps = retrans_info
                    retransmission_map[bundle_id] = (retry_count, data_rate_bps)
                    retransmitted_bundle_ids.append(bundle_id)
                else:
                    # Backward compatibility
                    retransmitted_bundle_ids.append(retrans_info)
            
            # Process ISS bundles first (if any visible station)
            if dtn_manager.iss_queue:
                visible_stations = [s for s in stations_data if s["is_visible"]]
                if visible_stations:
                    # Find station with highest elevation
                    best_station = max(visible_stations, key=lambda s: s["look_angles"]["elevation"])
                    station_id = best_station["id"]
                    
                    # Check if already transmitting
                    is_transmitting = any(
                        t.from_station == "ISS" or t.to_station == station_id
                        for t in dtn_manager.active_transmissions.values()
                    )
                    
                    if not is_transmitting:
                        next_bundle_id = dtn_manager.iss_queue[0]
                        next_bundle = dtn_manager.bundles.get(next_bundle_id)
                        
                        if next_bundle:
                            # Handle broadcast bundles differently
                            if next_bundle.destination_station.upper() == "BROADCAST":
                                # For broadcast, just send to first visible station
                                # Flooding will happen when it's received
                                first_hop = station_id
                                
                                # Calculate data rate
                                radial_velocity_data = tracker.calculate_radial_velocity(
                                    best_station["lat"],
                                    best_station["lon"]
                                )
                                
                                link_budget = link_budget_calc.calculate_link_budget(
                                    best_station["look_angles"]["range_km"],
                                    best_station["look_angles"]["elevation"],
                                    radial_velocity_data["radial_velocity_kmps"]
                                )
                                
                                data_rate_bps = link_budget.get("data_rate_bps", 0)
                                
                                if data_rate_bps > 0:
                                    print(f"📡 ISS transmitting BROADCAST bundle {next_bundle_id[:8]} to {first_hop.upper()} (will flood to all stations)")
                                    dtn_manager.start_transmission(
                                        next_bundle_id,
                                        "ISS",
                                        first_hop,
                                        data_rate_bps,
                                        retransmission_count=0
                                    )
                            else:
                                # Calculate route from ISS to destination
                                route = dtn_manager.find_route(
                                    "ISS",
                                    next_bundle.destination_station,
                                    stations_data,
                                    visited=[]
                                )
                                
                                if route and len(route) > 1:
                                    next_bundle.route = route
                                    dtn_manager.db_manager.update_bundle_route(next_bundle_id, route)
                                    
                                    # First hop is the visible station
                                    first_hop = route[1]  # route[0] is "ISS"
                                    
                                    # Calculate data rate
                                    radial_velocity_data = tracker.calculate_radial_velocity(
                                        best_station["lat"],
                                        best_station["lon"]
                                    )
                                    
                                    link_budget = link_budget_calc.calculate_link_budget(
                                        best_station["look_angles"]["range_km"],
                                        best_station["look_angles"]["elevation"],
                                        radial_velocity_data["radial_velocity_kmps"]
                                    )
                                    
                                    data_rate_bps = link_budget.get("data_rate_bps", 0)
                                    
                                    if data_rate_bps > 0:
                                        print(f"🛰️  ISS transmitting bundle {next_bundle_id[:8]} to {first_hop.upper()} (route: {' → '.join(route)})")
                                        dtn_manager.start_transmission(
                                            next_bundle_id,
                                            "ISS",
                                            first_hop,
                                            data_rate_bps,
                                            retransmission_count=0
                                        )
            
            # Process DTN bundles - start new transmissions or forward
            for station_data in stations_data:
                station_id = station_data["id"]
                is_visible = station_data["is_visible"]  
                
                # Get station's queue
                queue = dtn_manager.station_queues.get(station_id, [])
                
                if not queue:
                    continue  # No bundles to process
                
                # Check if this station is already transmitting or waiting for ACK
                is_transmitting = any(
                    t.from_station == station_id 
                    for t in dtn_manager.active_transmissions.values()
                )
                
                # Also check if station is waiting for ACK on any bundle
                is_waiting_ack = any(
                    pending.from_station == station_id
                    for pending in dtn_manager.pending_acknowledgments.values()
                )
                
                if is_transmitting or is_waiting_ack:
                    continue  # Already transmitting or waiting for ACK, don't start another
                
                # Queue is now pre-sorted by priority in dtn_bundle_manager
                # Skip bundles that are waiting for ACK or already delivered/expired
                next_bundle_id = None
                next_bundle = None
                for bundle_id in queue:
                    bundle = dtn_manager.bundles.get(bundle_id)
                    if bundle and bundle.status not in [BundleStatus.WAITING_ACK, BundleStatus.DELIVERED, BundleStatus.EXPIRED]:
                        next_bundle_id = bundle_id
                        next_bundle = bundle
                        break
                
                if not next_bundle_id or not next_bundle:
                    continue  # No valid bundle to process
                
                # Check bundle destination first
                bundle_destination = next_bundle.destination_station
                
                # Case 1: Bundle destination is ISS and this station can see ISS - transmit directly
                if bundle_destination.upper() == "ISS" and is_visible:
                    # Calculate data rate for this specific station
                    radial_velocity_data = tracker.calculate_radial_velocity(
                        station_data["lat"],
                        station_data["lon"]
                    )
                    
                    link_budget = link_budget_calc.calculate_link_budget(
                        station_data["look_angles"]["range_km"],
                        station_data["look_angles"]["elevation"],
                        radial_velocity_data["radial_velocity_kmps"]
                    )
                    
                    data_rate_bps = link_budget.get("data_rate_bps", 0)
                    connection_state = link_budget.get("connection_state", "IDLE")
                    
                    # Only transmit if link is up and data rate is available
                    if data_rate_bps > 0 and connection_state != "IDLE":
                        # Check if this is a retransmission
                        retry_count = None  
                        if next_bundle_id in retransmission_map:
                            retry_count, stored_data_rate = retransmission_map[next_bundle_id]
                            if stored_data_rate > 0:
                                data_rate_bps = stored_data_rate
                        
                        retry_msg = ""
                        if retry_count is not None and retry_count > 0:
                            retry_msg = f" (retry {retry_count + 1})"
                        elif next_bundle_id in dtn_manager.bundle_retry_counts:
                            retry_count_stored = dtn_manager.bundle_retry_counts[next_bundle_id]
                            if retry_count_stored > 0:
                                retry_msg = f" (retry {retry_count_stored + 1})"
                        
                        print(f"🛰️  {station_id.upper()} has ISS contact - transmitting {next_bundle.priority.value} priority bundle to ISS{retry_msg}")
                        dtn_manager.start_transmission(
                            next_bundle_id,
                            station_id,
                            "ISS",
                            data_rate_bps,
                            retransmission_count=retry_count
                        )
                        continue  # Skip forwarding logic, bundle is being sent to ISS
                
                # Case 2: Handle BROADCAST bundles - flood to all neighbors
                if bundle_destination.upper() == "BROADCAST":
                    # Mark this station as having received the broadcast
                    if not dtn_manager.has_received_broadcast(next_bundle_id, station_id):
                        dtn_manager.mark_broadcast_received(next_bundle_id, station_id)
                        print(f"📡 {station_id.upper()} received BROADCAST bundle {next_bundle_id[:8]}")
                    
                    # Get neighbors that haven't received the broadcast yet
                    unreceived_neighbors = dtn_manager.get_broadcast_unreceived_neighbors(next_bundle_id, station_id)
                    
                    if unreceived_neighbors:
                        # Forward to first unreceived neighbor (we'll process others in next iterations)
                        next_neighbor = unreceived_neighbors[0]
                        print(f"📡 {station_id.upper()} flooding BROADCAST bundle {next_bundle_id[:8]} to {next_neighbor.upper()} ({len(unreceived_neighbors)} neighbors remaining)")
                        
                        ground_link_bps = 100_000_000
                        dtn_manager.start_transmission(
                            next_bundle_id,
                            station_id,
                            next_neighbor,
                            ground_link_bps,
                            retransmission_count=0
                        )
                        continue
                    else:
                        # All neighbors have received it - check if we need to continue flooding
                        # This station has received and forwarded to all neighbors
                        print(f"✅ {station_id.upper()} has forwarded BROADCAST bundle {next_bundle_id[:8]} to all neighbors")
                        # Bundle will remain in queue but won't be forwarded again from here
                        continue
                
                # Case 3: Bundle destination is a ground station OR this station can't see ISS
                if bundle_destination.upper() != "ISS" or not is_visible:
                    # Check if bundle has a route - if so, use it for forwarding
                    next_hop_from_route = dtn_manager.get_next_hop_from_route(next_bundle_id)
                    
                    if next_hop_from_route:
                        retry_count = None
                        if next_bundle_id in retransmission_map:
                            retry_count, stored_data_rate = retransmission_map[next_bundle_id]
                        elif next_bundle_id in dtn_manager.bundle_retry_counts:
                            retry_count = dtn_manager.bundle_retry_counts[next_bundle_id]
                        
                        retry_msg = f" (retry {retry_count + 1})" if retry_count and retry_count > 0 else ""
                        print(f"📨 {station_id.upper()} forwarding {next_bundle.priority.value} priority bundle to {next_hop_from_route.upper()}{retry_msg} (route: {' → '.join(next_bundle.route)})")
                        
                        # Use ground link (fast, 100 Mbps)
                        ground_link_bps = 100_000_000
                        dtn_manager.start_transmission(
                            next_bundle_id,
                            station_id,
                            next_hop_from_route,
                            ground_link_bps,
                            retransmission_count=retry_count
                        )
                        continue  # Don't check for other forwarding options
                    
                    # No route exists - calculate one if we have mesh connections
                    if not next_bundle.route or len(next_bundle.route) == 0:
                        final_destination = bundle_destination if bundle_destination.upper() != "ISS" else "ISS"
                        route = dtn_manager.find_route(
                            station_id,
                            final_destination,
                            stations_data,
                            visited=next_bundle.hops
                        )
                        if route:
                            next_bundle.route = route
                            # Persist the calculated route to prevent recalculation on restart
                            dtn_manager.db_manager.update_bundle_route(next_bundle_id, route)
                            
                            print(f"🗺️  Calculated route for bundle {next_bundle_id[:8]}: {' → '.join(route)}")
                            # Use first hop from route
                            if len(route) > 1:
                                next_hop_from_route = route[1]  # route[0] is current station
                                
                                retry_count = None
                                if next_bundle_id in retransmission_map:
                                    retry_count, stored_data_rate = retransmission_map[next_bundle_id]
                                elif next_bundle_id in dtn_manager.bundle_retry_counts:
                                    retry_count = dtn_manager.bundle_retry_counts[next_bundle_id]
                                
                                retry_msg = f" (retry {retry_count + 1})" if retry_count and retry_count > 0 else ""
                                print(f"📨 {station_id.upper()} forwarding {next_bundle.priority.value} priority bundle to {next_hop_from_route.upper()}{retry_msg} (route: {' → '.join(route)})")
                                
                                ground_link_bps = 100_000_000
                                dtn_manager.start_transmission(
                                    next_bundle_id,
                                    station_id,
                                    next_hop_from_route,
                                    ground_link_bps,
                                    retransmission_count=retry_count
                                )
                                continue
                    
                    # Fallback: Original forwarding logic (if no route found)
                    active_station_has_link = False
                    if current_active_station:
                        active_station_data = next(
                            (s for s in stations_data if s["id"] == current_active_station),
                            None
                        )
                        if active_station_data and active_station_data["is_visible"]:
                            radial_velocity_data = tracker.calculate_radial_velocity(
                                active_station_data["lat"],
                                active_station_data["lon"]
                            )
                            link_budget = link_budget_calc.calculate_link_budget(
                                active_station_data["look_angles"]["range_km"],
                                active_station_data["look_angles"]["elevation"],
                                radial_velocity_data["radial_velocity_kmps"]
                            )
                            active_station_has_link = (
                                link_budget.get("connection_state", "IDLE") != "IDLE" and
                                link_budget.get("data_rate_bps", 0) > 0
                            )
                    
                    if current_active_station and current_active_station != station_id and active_station_has_link:
                        visited_stations = next_bundle.hops
                        
                        if current_active_station not in visited_stations:
                            retry_count = None
                            if next_bundle_id in retransmission_map:
                                retry_count, stored_data_rate = retransmission_map[next_bundle_id]
                            elif next_bundle_id in dtn_manager.bundle_retry_counts:
                                retry_count = dtn_manager.bundle_retry_counts[next_bundle_id]
                            
                            retry_msg = f" (retry {retry_count + 1})" if retry_count and retry_count > 0 else ""
                            print(f"📨 {station_id.upper()} forwarding {next_bundle.priority.value} priority bundle to ACTIVE station {current_active_station.upper()}{retry_msg} for immediate ISS contact")
                            
                            ground_link_bps = 100_000_000
                            dtn_manager.start_transmission(
                                next_bundle_id,
                                station_id,
                                current_active_station,
                                ground_link_bps,
                                retransmission_count=retry_count
                            )
                            continue
                    
                    # Second check: Look for stations with upcoming passes
                    if not is_visible:
                        current_station_next_pass = station_data["next_pass_minutes"]
                        
                        if current_station_next_pass > 0:
                            visited_stations = next_bundle.hops
                            
                            better_stations = [
                                s for s in stations_data 
                                if s["id"] != station_id 
                                and s["id"] not in visited_stations
                                and s["next_pass_minutes"] > 0
                                and s["next_pass_minutes"] < current_station_next_pass
                            ]
                            
                            if better_stations:
                                better_stations.sort(key=lambda s: s["next_pass_minutes"])
                                next_hop_station = better_stations[0]["id"]
                                
                                retry_count = None
                                if next_bundle_id in retransmission_map:
                                    retry_count, stored_data_rate = retransmission_map[next_bundle_id]
                                elif next_bundle_id in dtn_manager.bundle_retry_counts:
                                    retry_count = dtn_manager.bundle_retry_counts[next_bundle_id]
                                
                                retry_msg = f" (retry {retry_count + 1})" if retry_count and retry_count > 0 else ""
                                print(f"📨 {station_id.upper()} forwarding {next_bundle.priority.value} priority bundle to {next_hop_station.upper()}{retry_msg} (sooner pass: {better_stations[0]['next_pass_minutes']} min vs {current_station_next_pass} min)")
                                
                                ground_link_bps = 100_000_000
                                dtn_manager.start_transmission(
                                    next_bundle_id,
                                    station_id,
                                    next_hop_station,
                                    ground_link_bps,
                                    retransmission_count=retry_count
                                )
                                continue
                    # else: Current station is tracking ISS or no better option - keep bundle here and wait
            
            # Cleanup expired bundles every 60 seconds
            if iteration % 60 == 0:
                dtn_manager.cleanup_expired()
            
            # Update orbital path every 60 seconds
            if (now - last_path_update).total_seconds() > 60:
                orbital_path = tracker.get_orbital_path(minutes=95, points=150)
                last_path_update = now
            
            # Build orbital parameters
            active_station_data = None
            if current_active_station:
                active_station_data = next(
                    (s for s in stations_data if s["id"] == current_active_station), 
                    None
                )
            
            orbital_parameters = None
            if active_station_data:
                orbital_parameters = {
                    "active_station": active_station_data["name"],
                    "latitude": iss_position["latitude"],
                    "longitude": iss_position["longitude"],
                    "altitude_km": iss_position["altitude_km"],
                    "velocity_kmps": iss_position["velocity_kmps"],
                    "azimuth": active_station_data["look_angles"]["azimuth"],
                    "elevation": active_station_data["look_angles"]["elevation"],
                    "range_km": active_station_data["look_angles"]["range_km"],
                    "next_pass_time": active_station_data["next_pass_time"],
                    "next_pass_minutes": active_station_data["next_pass_minutes"],
                    "aos_time": active_station_data["pass_window"]["aos_time"] if active_station_data["pass_window"] else None,
                    "los_time": active_station_data["pass_window"]["los_time"] if active_station_data["pass_window"] else None,
                    "pass_duration_minutes": active_station_data["pass_window"]["duration_minutes"] if active_station_data["pass_window"] else 0,
                    "is_in_pass": active_station_data["pass_window"]["is_in_pass"] if active_station_data["pass_window"] else False
                }
            
            # Calculate link budget
            link_status = None
            if active_station_data:
                radial_velocity_data = tracker.calculate_radial_velocity(
                    active_station_data["lat"],
                    active_station_data["lon"]
                )
                
                link_budget = link_budget_calc.calculate_link_budget(
                    active_station_data["look_angles"]["range_km"],
                    active_station_data["look_angles"]["elevation"],
                    radial_velocity_data["radial_velocity_kmps"]
                )
                
                link_status = {
                    "signal_strength_dbm": link_budget["signal_strength_dbm"],
                    "connection_state": link_budget["connection_state"],
                    "latency_ms": link_budget["latency_ms"],
                    "doppler_shift_khz": link_budget["doppler_shift_khz"],
                    "snr_db": link_budget["snr_db"],
                    "range_km": link_budget["range_km"],
                    "radial_velocity_kmps": radial_velocity_data["radial_velocity_kmps"],
                    "data_rate_bps": link_budget.get("data_rate_bps", 0),
                    "data_rate_kbps": link_budget.get("data_rate_kbps", 0),
                }
                
                link_budget_history.append({
                    "timestamp": now.isoformat(),
                    "snr_db": link_budget["snr_db"],
                    "signal_strength_dbm": link_budget["signal_strength_dbm"]
                })
            else:
                link_status = {
                    "signal_strength_dbm": -120.0,
                    "connection_state": "IDLE",
                    "latency_ms": 0.0,
                    "doppler_shift_khz": 0.0,
                    "snr_db": -50.0,
                    "range_km": 0.0,
                    "radial_velocity_kmps": 0.0,
                    "data_rate_bps": 0.0,
                    "data_rate_kbps": 0.0,
                }
            
            # Calculate link budgets for ALL VISIBLE stations
            visible_links = []
            should_log_link_updates = USE_MININET and topology and link_param_manager and (now - last_link_log_time).total_seconds() >= 5.0
            
            updated_stations = set()
            
            for station_data in stations_data:
                if station_data["is_visible"]:
                    radial_velocity_data = tracker.calculate_radial_velocity(
                        station_data["lat"],
                        station_data["lon"]
                    )
                    
                    link_budget = link_budget_calc.calculate_link_budget(
                        station_data["look_angles"]["range_km"],
                        station_data["look_angles"]["elevation"],
                        radial_velocity_data["radial_velocity_kmps"]
                    )
                    
                    visible_links.append({
                        "station_id": station_data["id"],
                        "station_name": station_data["name"],
                        "signal_strength_dbm": link_budget["signal_strength_dbm"],
                        "connection_state": link_budget["connection_state"],
                        "snr_db": link_budget["snr_db"],
                        "data_rate_kbps": link_budget.get("data_rate_kbps", 0),
                    })
                    
                    # Update Mininet link parameters if enabled (only for visible stations)
                    if USE_MININET and topology and link_param_manager:
                        mininet_params = link_param_manager.link_budget_to_mininet_params(link_budget)
                        topology.update_iss_link(
                            station_data["id"],
                            mininet_params["bandwidth_mbps"],
                            mininet_params["delay_ms"],
                            mininet_params["loss_percent"],
                            log_update=should_log_link_updates
                        )
                        updated_stations.add(station_data["id"])
            
            # Update non-visible stations to minimal link parameters
            if USE_MININET and topology and link_param_manager:
                for station_data in stations_data:
                    station_id = station_data["id"]
                    if not station_data["is_visible"] and station_id not in updated_stations:
                        # Set minimal parameters for non-visible stations
                        min_params = {
                            "bandwidth_mbps": link_param_manager.MIN_BANDWIDTH_MBPS,
                            "delay_ms": 100.0,  # Default delay when not visible
                            "loss_percent": link_param_manager.MAX_LOSS_PERCENT,
                        }
                        topology.update_iss_link(
                            station_id,
                            min_params["bandwidth_mbps"],
                            min_params["delay_ms"],
                            min_params["loss_percent"],
                            log_update=False  # Don't spam logs for non-visible stations
                        )
            
            # Update log time after processing all stations (only once per iteration)
            if should_log_link_updates:
                last_link_log_time = now
            
            # Get DTN bundle queues for all stations
            dtn_queues = dtn_manager.get_all_queues()

            # Get ISS queue
            iss_queue = dtn_manager.get_iss_queue()

            # Get delivered bundles for history
            delivered_bundles = dtn_manager.get_delivered_bundles() 
            
            # Get failed bundles for history
            failed_bundles = dtn_manager.get_failed_bundles()
            
            # Get active transmissions
            active_transmissions = dtn_manager.get_active_transmissions()
            
            # Get custody ACKs
            pending_acks = dtn_manager.get_pending_acks()
            
            # Get mesh topology connections (if using Mininet)
            mesh_connections = []
            if USE_MININET and topology:
                mesh_connections = [
                    {"from": conn[0], "to": conn[1]} 
                    for conn in topology.get_mesh_connections()
                ]
            
            # Prepare data packet
            data = {
                "type": "orbital_update",
                "timestamp": now.isoformat(),
                "iss_position": iss_position,
                "orbital_path": orbital_path,
                "stations": stations_data,
                "active_station_id": current_active_station,
                "visible_stations_count": len(visible_stations),
                "min_elevation": MIN_ELEVATION_FOR_VISIBILITY,
                "orbital_parameters": orbital_parameters,
                "visible_links": visible_links,
                "link_status": link_status,
                "link_budget_history": list(link_budget_history),
                "dtn_queues": dtn_queues,
                "iss_queue": iss_queue,
                "delivered_bundles": delivered_bundles,
                "failed_bundles": failed_bundles,
                "custody_acks": pending_acks,
                "active_transmissions": active_transmissions,
                "mesh_connections": mesh_connections
            }
            
            try:
                await websocket.send_json(data)
            except Exception as send_error:
                print(f"❌ Error sending websocket data: {send_error}")
                # Check if it's a connection error
                if "connection closed" in str(send_error).lower() or "1005" in str(send_error):
                    print("   Connection closed by client, stopping...")
                    break
                raise
            
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        print("❌ Client disconnected")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

@app.options("/api/bundle/create")
async def bundle_create_options():
    """Handle CORS preflight for bundle creation"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

@app.post("/api/bundle/create")
async def create_bundle(request: BundleCreateRequest):
    """Create a new DTN bundle"""
    try:
        print(f"📦 Received bundle request: {request.source_station} -> {request.destination}")
        bundle = dtn_manager.create_bundle(
            source_station=request.source_station,
            destination=request.destination,
            payload=request.payload,
            priority=request.priority,
            ttl_hours=request.ttl_hours
        )
        return {"success": True, "bundle": bundle.to_dict()}
    except Exception as e:
        print(f"❌ Error creating bundle: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# ISS Interface API Endpoints
class ISSReplyRequest(BaseModel):
    destination_station: str
    payload: str
    priority: str = "NORMAL"
    ttl_hours: int = 24
    is_broadcast: bool = False

@app.get("/api/iss/messages")
async def get_iss_messages():
    """Get all bundles delivered to ISS with fragment status"""
    try:
        messages = dtn_manager.get_iss_delivered_bundles()
        return {"messages": messages}
    except Exception as e:
        print(f"❌ Error getting ISS messages: {e}")
        import traceback
        traceback.print_exc()
        return {"messages": [], "error": str(e)}

@app.get("/api/iss/fragments/{bundle_id}")
async def get_fragment_status(bundle_id: str):
    """Get fragment status for a bundle"""
    try:
        status = dtn_manager.get_fragment_status(bundle_id)
        if status:
            return status
        else:
            return {"error": "Bundle not found"}
    except Exception as e:
        print(f"❌ Error getting fragment status: {e}")
        return {"error": str(e)}

@app.post("/api/iss/messages/{bundle_id}/reassemble")
async def reassemble_message(bundle_id: str):
    """Reassemble fragments and decrypt message"""
    try:
        result = dtn_manager.reassemble_and_decrypt_bundle(bundle_id)
        if result:
            return {"success": True, "message": result}
        else:
            return {"success": False, "error": "Fragments incomplete or bundle not found"}
    except Exception as e:
        print(f"❌ Error reassembling message: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/iss/messages/reply")
async def create_iss_reply(request: ISSReplyRequest):
    """Create reply bundle from ISS to ground station (or broadcast)"""
    try:
        if request.is_broadcast:
            print(f"📡 ISS creating broadcast bundle to all stations")
            bundle = dtn_manager.create_iss_reply_bundle(
                destination_station="BROADCAST",
                payload=request.payload,
                priority=request.priority,
                ttl_hours=request.ttl_hours
            )
        else:
            print(f"📤 ISS creating reply bundle to {request.destination_station}")
            bundle = dtn_manager.create_iss_reply_bundle(
                destination_station=request.destination_station,
                payload=request.payload,
                priority=request.priority,
                ttl_hours=request.ttl_hours
            )
        
        # Calculate route for the reply
        # We need station data - get it from the latest orbital data if available
        # For now, route will be calculated during transmission
        return {"success": True, "bundle": bundle.to_dict()}
    except Exception as e:
        print(f"❌ Error creating ISS reply: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if USE_MININET and topology:
        print("🛑 Shutting down Mininet topology...")
        if hasattr(dtn_manager, 'stop_servers'):
            dtn_manager.stop_servers()
        topology.stop()

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if USE_MININET and topology:
            if hasattr(dtn_manager, 'stop_servers'):
                dtn_manager.stop_servers()
            topology.stop()