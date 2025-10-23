import requests
from datetime import datetime, timedelta
import os

class TLEFetcher:
    """Fetches and caches ISS TLE data from CelesTrak"""
    
    def __init__(self, cache_hours=6):
        self.tle_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
        self.cache_file = "iss_tle_cache.txt"
        self.cache_hours = cache_hours
        self.tle_lines = None
        self.last_fetch = None
        
    def fetch_tle(self):
        """Fetch fresh TLE data from CelesTrak"""
        try:
            print("📡 Fetching fresh TLE data from CelesTrak...")
            response = requests.get(self.tle_url, timeout=10)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            
            # Find ISS (ZARYA) in the TLE data
            for i in range(0, len(lines)-2, 3):
                if 'ISS (ZARYA)' in lines[i]:
                    self.tle_lines = (lines[i].strip(), lines[i+1].strip(), lines[i+2].strip())
                    self.last_fetch = datetime.utcnow()
                    
                    # Cache to file
                    with open(self.cache_file, 'w') as f:
                        f.write(f"{self.last_fetch.isoformat()}\n")
                        f.write(f"{self.tle_lines[0]}\n")
                        f.write(f"{self.tle_lines[1]}\n")
                        f.write(f"{self.tle_lines[2]}\n")
                    
                    print(f"✅ TLE data cached: {self.tle_lines[0]}")
                    return self.tle_lines
            
            raise Exception("ISS TLE not found in CelesTrak data")
            
        except Exception as e:
            print(f"❌ Error fetching TLE: {e}")
            return self._load_from_cache()
    
    def _load_from_cache(self):
        """Load TLE from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    lines = f.readlines()
                    cache_time = datetime.fromisoformat(lines[0].strip())
                    
                    # Check if cache is still valid
                    age = datetime.utcnow() - cache_time
                    if age < timedelta(hours=self.cache_hours):
                        self.tle_lines = (lines[1].strip(), lines[2].strip(), lines[3].strip())
                        self.last_fetch = cache_time
                        print(f"✅ Loaded TLE from cache (age: {age})")
                        return self.tle_lines
                    else:
                        print(f"⚠️ Cache expired (age: {age})")
        except Exception as e:
            print(f"❌ Error loading cache: {e}")
        
        return None
    
    def get_tle(self):
        """Get current TLE (from cache or fetch fresh)"""
        # Check if we need to fetch fresh data
        if self.tle_lines is None:
            return self.fetch_tle()
        
        if self.last_fetch:
            age = datetime.utcnow() - self.last_fetch
            if age > timedelta(hours=self.cache_hours):
                print(f"⏰ TLE cache expired, fetching fresh data...")
                return self.fetch_tle()
        
        return self.tle_lines