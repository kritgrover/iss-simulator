from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, timezone, timedelta
import numpy as np
from typing import Dict, List, Tuple

class OrbitalTracker:
    """Tracks ISS position using SGP4 propagation"""
    
    def __init__(self, tle_lines: Tuple[str, str, str]):
        self.ts = load.timescale()
        
        # Create satellite object from TLE
        name, line1, line2 = tle_lines
        self.satellite = EarthSatellite(line1, line2, name, self.ts)
        
        print(f"🛰️  Initialized tracker for: {name}")
    
    def get_current_position(self) -> Dict:
        """Get current ISS position"""
        t = self.ts.now()
        geocentric = self.satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
        
        # Get velocity for speed calculation
        position = geocentric.position.km
        velocity = geocentric.velocity.km_per_s
        speed = np.linalg.norm(velocity)
        
        return {
            "latitude": float(subpoint.latitude.degrees),
            "longitude": float(subpoint.longitude.degrees),
            "altitude_km": float(subpoint.elevation.km),
            "velocity_kmps": float(speed)
        }
    
    def get_orbital_path(self, minutes=95, points=100) -> List[Dict]:
        """Generate orbital path points for next N minutes"""
        t_start = self.ts.now()
        
        # Create time array
        times = self.ts.utc(
            t_start.utc_datetime().year,
            t_start.utc_datetime().month,
            t_start.utc_datetime().day,
            t_start.utc_datetime().hour,
            t_start.utc_datetime().minute,
            np.linspace(0, minutes * 60, points)
        )
        
        path = []
        for t in times:
            geocentric = self.satellite.at(t)
            subpoint = wgs84.subpoint(geocentric)
            
            path.append({
                "lat": float(subpoint.latitude.degrees),
                "lon": float(subpoint.longitude.degrees),
                "alt": float(subpoint.elevation.km)
            })
        
        return path
    
    def calculate_look_angles(self, ground_lat: float, ground_lon: float) -> Dict:
        """Calculate azimuth, elevation, and range from ground station"""
        t = self.ts.now()
        
        # Ground station location
        ground_station = wgs84.latlon(ground_lat, ground_lon)
        
        # Calculate difference
        difference = self.satellite - ground_station
        topocentric = difference.at(t)
        
        alt, az, distance = topocentric.altaz()
        
        return {
            "azimuth": float(az.degrees),
            "elevation": float(alt.degrees),
            "range_km": float(distance.km),
            "is_visible": bool(alt.degrees > 0)
        }
    
    def calculate_radial_velocity(self, ground_lat: float, ground_lon: float) -> Dict:
        """
        Calculate actual radial velocity component (velocity toward/away from ground station)
        Positive = approaching (blue shift)
        Negative = receding (red shift)
        """
        t = self.ts.now()
        ground_station = wgs84.latlon(ground_lat, ground_lon)
        
        # Get satellite position and velocity
        difference = self.satellite - ground_station
        topocentric = difference.at(t)
        
        # Get position vector (km) and velocity vector (km/s)
        position_km = topocentric.position.km
        velocity_km_s = topocentric.velocity.km_per_s
        
        # Calculate range (distance)
        range_km = np.linalg.norm(position_km)
        
        if range_km < 0.001:  # Avoid division by zero
            return {
                "radial_velocity_kmps": 0.0,
                "range_km": range_km,
                "range_rate_kmps": 0.0
            }
        
        # Unit vector pointing from ground station to satellite
        range_unit_vector = position_km / range_km
        
        # Radial velocity = dot product of velocity with range unit vector
        # Positive = satellite moving away from station (receding)
        # Negative = satellite moving toward station (approaching)
        radial_velocity = float(np.dot(velocity_km_s, range_unit_vector))
        
        return {
            "radial_velocity_kmps": radial_velocity,  # This is the TRUE radial velocity
            "range_km": float(range_km),
            "range_rate_kmps": radial_velocity  # Same as radial velocity
        }
    
    def predict_next_pass(self, ground_lat: float, ground_lon: float, 
                         min_elevation: float = 10.0, max_hours: int = 48) -> Dict:
        """
        Predict next pass over ground station
        Finds the next AOS (Acquisition of Signal) event
        """
        t_start = self.ts.now()
        ground_station = wgs84.latlon(ground_lat, ground_lon)
        
        # Check if currently in a pass
        difference = self.satellite - ground_station
        current_topo = difference.at(t_start)
        current_alt, _, _ = current_topo.altaz()
        currently_visible = current_alt.degrees > min_elevation
        
        # If currently visible, skip ahead to find LOS first, then next AOS
        start_offset_minutes = 0
        if currently_visible:
            # Find when satellite sets (LOS)
            for minutes_ahead in range(1, 30):
                t_future = self._add_minutes_to_time(t_start, minutes_ahead)
                topo_future = difference.at(t_future)
                alt_future, _, _ = topo_future.altaz()
                
                if alt_future.degrees <= min_elevation:
                    # Found LOS, start searching from here
                    start_offset_minutes = minutes_ahead + 1
                    break
        
        # Now search for next AOS
        for minutes_ahead in range(start_offset_minutes, max_hours * 60, 1):
            t_check = self._add_minutes_to_time(t_start, minutes_ahead)
            
            # Check current minute
            topo_check = difference.at(t_check)
            alt_check, az_check, dist_check = topo_check.altaz()
            
            # Check previous minute to detect rising
            t_prev = self._add_minutes_to_time(t_start, minutes_ahead - 1)
            topo_prev = difference.at(t_prev)
            alt_prev, _, _ = topo_prev.altaz()
            
            # Found AOS: satellite was below threshold and is now above
            if alt_prev.degrees <= min_elevation and alt_check.degrees > min_elevation:
                # Found next pass!
                return {
                    "start_time": t_check.utc_iso(),
                    "minutes_until": int(minutes_ahead),
                    "max_elevation": float(alt_check.degrees),  # Rough estimate
                    "azimuth": float(az_check.degrees)
                }
        
        # No pass found within max_hours
        return {
            "start_time": None,
            "minutes_until": -1,
            "max_elevation": 0.0,
            "azimuth": 0.0
        }
    
    def _add_minutes_to_time(self, time_obj, minutes: int):
        """Helper to add minutes to a Skyfield time object"""
        dt = time_obj.utc_datetime() + timedelta(minutes=minutes)
        return self.ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    
    def calculate_pass_window(self, ground_lat: float, ground_lon: float, 
                             min_elevation: float = 0.0) -> Dict:
        """Calculate current pass start (AOS) and end (LOS) times"""
        t_now = self.ts.now()
        ground_station = wgs84.latlon(ground_lat, ground_lon)
        
        # Check current elevation
        difference = self.satellite - ground_station
        topocentric = difference.at(t_now)
        current_alt, _, _ = topocentric.altaz()
        
        # If not currently visible, no pass window
        if current_alt.degrees <= min_elevation:
            return {
                "aos_time": None,
                "los_time": None,
                "duration_minutes": 0,
                "is_in_pass": False
            }
        
        # Find AOS (look backwards in time)
        aos_time = None
        for minutes_back in range(1, 30):
            t_past = self._add_minutes_to_time(t_now, -minutes_back)
            topocentric_past = difference.at(t_past)
            alt_past, _, _ = topocentric_past.altaz()
            
            if alt_past.degrees <= min_elevation:
                # Found AOS - it's between this minute and the next
                aos_time = self._add_minutes_to_time(t_now, -minutes_back + 1)
                break
        
        # Find LOS (look forwards in time)
        los_time = None
        for minutes_ahead in range(1, 30):
            t_future = self._add_minutes_to_time(t_now, minutes_ahead)
            topocentric_future = difference.at(t_future)
            alt_future, _, _ = topocentric_future.altaz()
            
            if alt_future.degrees <= min_elevation:
                # Found LOS
                los_time = t_future
                break
        
        # Calculate duration
        duration_minutes = 0
        if aos_time is not None and los_time is not None:
            aos_dt = aos_time.utc_datetime()
            los_dt = los_time.utc_datetime()
            duration_minutes = int((los_dt - aos_dt).total_seconds() / 60)
        
        return {
            "aos_time": aos_time.utc_iso() if aos_time is not None else None,
            "los_time": los_time.utc_iso() if los_time is not None else None,
            "duration_minutes": duration_minutes,
            "is_in_pass": True
        }
    
    def generate_coverage_cone(self, ground_lat: float, ground_lon: float, 
                               opening_angle: float = 70, segments: int = 32) -> Dict:
        """Generate 3D cone vertices for ground station coverage"""
        
        # Check if ISS is in view
        look_angles = self.calculate_look_angles(ground_lat, ground_lon)
        
        # Cone geometry (simplified for visualization)
        vertices = []
        
        # Apex at ground station
        apex = {"lat": float(ground_lat), "lon": float(ground_lon), "alt": 0.0}
        
        # Generate circle at top of cone
        for i in range(segments):
            angle = (2 * np.pi * i) / segments
            lat_offset = (opening_angle / 2) * np.cos(angle) / 111
            lon_offset = (opening_angle / 2) * np.sin(angle) / (111 * np.cos(np.radians(ground_lat)))
            
            vertices.append({
                "lat": float(ground_lat + lat_offset),
                "lon": float(ground_lon + lon_offset),
                "alt": 0.0
            })
        
        return {
            "apex": apex,
            "vertices": vertices,
            "opening_angle": float(opening_angle),
            "is_active": bool(look_angles["is_visible"])
        }