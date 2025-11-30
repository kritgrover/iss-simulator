import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

class DatabaseManager:
    """
    Manages SQLite database interactions for DTN bundle persistence.
    """
    
    def __init__(self, db_path: str = "dtn_bundles.db"):
        self.db_path = db_path
        self.init_db()
        
    def _recreate_database(self):
        """Delete corrupted database file and recreate it."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                print(f"🗑️  Removed corrupted database file: {self.db_path}")
            except Exception as e:
                print(f"⚠️  Warning: Could not remove corrupted database file: {e}")
        
    def get_connection(self):
        """Get a database connection with row factory."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Test the connection by executing a simple query
            conn.execute("SELECT 1")
            return conn
        except sqlite3.DatabaseError as e:
            # Database is corrupted, recreate it
            print(f"⚠️  Database corruption detected: {e}")
            try:
                conn.close()  # Try to close the corrupted connection if it exists
            except:
                pass
            self._recreate_database()
            # Try again after recreation
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        
    def init_db(self):
        """Initialize the database schema."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create bundles table
            # We store complex objects like hops and route as JSON strings
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                bundle_id TEXT PRIMARY KEY,
                source_station TEXT,
                destination_station TEXT,
                payload TEXT,
                priority TEXT,
                status TEXT,
                created_at TEXT,
                ttl_hours INTEGER,
                current_custodian TEXT,
                forwarded_to TEXT,
                delivered_at TEXT,
                hops TEXT,
                route TEXT,
                size_bytes INTEGER,
                checksum INTEGER,
                failure_reason TEXT,
                updated_at TEXT
            )
            ''')
            
            conn.commit()
            conn.close()
            print(f"💾 Database initialized at {self.db_path}")
        except sqlite3.DatabaseError as e:
            # Database is corrupted, recreate it
            print(f"⚠️  Database corruption detected during initialization: {e}")
            self._recreate_database()
            # Retry initialization
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                bundle_id TEXT PRIMARY KEY,
                source_station TEXT,
                destination_station TEXT,
                payload TEXT,
                priority TEXT,
                status TEXT,
                created_at TEXT,
                ttl_hours INTEGER,
                current_custodian TEXT,
                forwarded_to TEXT,
                delivered_at TEXT,
                hops TEXT,
                route TEXT,
                size_bytes INTEGER,
                checksum INTEGER,
                failure_reason TEXT,
                updated_at TEXT
            )
            ''')
            conn.commit()
            conn.close()
            print(f"💾 Database recreated and initialized at {self.db_path}")
        
    def save_bundle(self, bundle_data: Dict[str, Any]):
        """
        Save a new bundle or update an existing one.
        Expects a dictionary representation of the bundle.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Prepare data for insertion
        # Convert list/dict fields to JSON
        hops_json = json.dumps(bundle_data.get('hops', []))
        route_json = json.dumps(bundle_data.get('route', []))
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO bundles (
                bundle_id, source_station, destination_station, payload, 
                priority, status, created_at, ttl_hours, current_custodian, 
                forwarded_to, delivered_at, hops, route, size_bytes, 
                checksum, failure_reason, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bundle_data['bundle_id'],
                bundle_data['source_station'],
                bundle_data['destination_station'],
                bundle_data['payload'],
                str(bundle_data['priority']), # Ensure enum string value
                str(bundle_data['status']),   # Ensure enum string value
                bundle_data['created_at'],
                bundle_data['ttl_hours'],
                bundle_data.get('current_custodian', ''),
                bundle_data.get('forwarded_to'),
                bundle_data.get('delivered_at'),
                hops_json,
                route_json,
                bundle_data.get('size_bytes', 0),
                bundle_data.get('checksum', 0),
                bundle_data.get('failure_reason'),
                now
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Database error saving bundle {bundle_data.get('bundle_id')}: {e}")
        finally:
            conn.close()

    def update_bundle_status(self, bundle_id: str, status: str, 
                            current_custodian: Optional[str] = None,
                            forwarded_to: Optional[str] = None,
                            delivered_at: Optional[str] = None,
                            failure_reason: Optional[str] = None):
        """Update specific fields of a bundle."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        updates = ["status = ?", "updated_at = ?"]
        params = [status, now]
        
        if current_custodian is not None:
            updates.append("current_custodian = ?")
            params.append(current_custodian)
            
        if forwarded_to is not None:
            updates.append("forwarded_to = ?")
            params.append(forwarded_to)
            
        if delivered_at is not None:
            updates.append("delivered_at = ?")
            params.append(delivered_at)
            
        if failure_reason is not None:
            updates.append("failure_reason = ?")
            params.append(failure_reason)
            
        params.append(bundle_id)
        
        query = f"UPDATE bundles SET {', '.join(updates)} WHERE bundle_id = ?"
        
        try:
            cursor.execute(query, params)
            conn.commit()
        except Exception as e:
            print(f"❌ Database error updating bundle {bundle_id}: {e}")
        finally:
            conn.close()

    def update_bundle_hops(self, bundle_id: str, hops: List[str]):
        """Update the hops list for a bundle."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        hops_json = json.dumps(hops)
        
        try:
            cursor.execute('''
            UPDATE bundles SET hops = ?, updated_at = ? WHERE bundle_id = ?
            ''', (hops_json, now, bundle_id))
            conn.commit()
        except Exception as e:
            print(f"❌ Database error updating hops for bundle {bundle_id}: {e}")
        finally:
            conn.close()

    def update_bundle_route(self, bundle_id: str, route: List[str]):
        """Update the route for a bundle."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        route_json = json.dumps(route)
        
        try:
            cursor.execute('''
            UPDATE bundles SET route = ?, updated_at = ? WHERE bundle_id = ?
            ''', (route_json, now, bundle_id))
            conn.commit()
        except Exception as e:
            print(f"❌ Database error updating route for bundle {bundle_id}: {e}")
        finally:
            conn.close()

    def get_all_bundles(self) -> List[Dict[str, Any]]:
        """Retrieve all bundles from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        bundles = []
        try:
            cursor.execute("SELECT * FROM bundles")
            rows = cursor.fetchall()
            
            for row in rows:
                bundle_dict = dict(row)
                # Parse JSON fields
                try:
                    bundle_dict['hops'] = json.loads(bundle_dict['hops']) if bundle_dict['hops'] else []
                    bundle_dict['route'] = json.loads(bundle_dict['route']) if bundle_dict['route'] else []
                except json.JSONDecodeError:
                    bundle_dict['hops'] = []
                    bundle_dict['route'] = []
                
                bundles.append(bundle_dict)
        except Exception as e:
            print(f"❌ Database error fetching bundles: {e}")
        finally:
            conn.close()
            
        return bundles

    def delete_bundle(self, bundle_id: str):
        """Delete a bundle from the database (useful for cleanup if needed)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM bundles WHERE bundle_id = ?", (bundle_id,))
            conn.commit()
        except Exception as e:
            print(f"❌ Database error deleting bundle {bundle_id}: {e}")
        finally:
            conn.close()

