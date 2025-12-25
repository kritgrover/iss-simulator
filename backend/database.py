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
        
    def _migrate_database(self, cursor):
        """Migrate database schema to add new columns if they don't exist."""
        try:
            # Get existing columns
            cursor.execute("PRAGMA table_info(bundles)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Columns to add if missing
            new_columns = {
                'encrypted_payload': 'TEXT',
                'payload_hash': 'TEXT',
                'pcb': 'TEXT',
                'pib': 'TEXT',
                'bab': 'TEXT',
                'is_fragmented': 'INTEGER',
                'fragment_count': 'INTEGER',
                'fragment_number': 'INTEGER'
            }
            
            for column_name, column_type in new_columns.items():
                if column_name not in existing_columns:
                    cursor.execute(f'ALTER TABLE bundles ADD COLUMN {column_name} {column_type}')
                    print(f"   ➕ Added column: {column_name}")
        except Exception as e:
            print(f"⚠️  Migration warning: {e}")
    
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
            # encrypted_payload stores the encrypted payload (base64)
            # payload_hash stores hash for display purposes
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                bundle_id TEXT PRIMARY KEY,
                source_station TEXT,
                destination_station TEXT,
                payload TEXT,
                encrypted_payload TEXT,
                payload_hash TEXT,
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
                pcb TEXT,
                pib TEXT,
                bab TEXT,
                is_fragmented INTEGER,
                fragment_count INTEGER,
                fragment_number INTEGER,
                updated_at TEXT
            )
            ''')
            
            # Migrate existing database: add new columns if they don't exist
            self._migrate_database(cursor)
            
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
                encrypted_payload TEXT,
                payload_hash TEXT,
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
                pcb TEXT,
                pib TEXT,
                bab TEXT,
                is_fragmented INTEGER,
                fragment_count INTEGER,
                fragment_number INTEGER,
                updated_at TEXT
            )
            ''')
            # Migrate if needed
            self._migrate_database(cursor)
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
        
        # Prepare security blocks as JSON
        pcb_json = json.dumps(bundle_data.get('pcb')) if bundle_data.get('pcb') else None
        pib_json = json.dumps(bundle_data.get('pib')) if bundle_data.get('pib') else None
        bab_json = json.dumps(bundle_data.get('bab')) if bundle_data.get('bab') else None
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO bundles (
                bundle_id, source_station, destination_station, payload, 
                encrypted_payload, payload_hash, priority, status, created_at, 
                ttl_hours, current_custodian, forwarded_to, delivered_at, 
                hops, route, size_bytes, checksum, failure_reason, 
                pcb, pib, bab, is_fragmented, fragment_count, fragment_number, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bundle_data['bundle_id'],
                bundle_data['source_station'],
                bundle_data['destination_station'],
                bundle_data.get('payload', ''),  # Display hash
                bundle_data.get('encrypted_payload', ''),  # Actual encrypted payload
                bundle_data.get('payload_hash', ''),
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
                pcb_json,
                pib_json,
                bab_json,
                1 if bundle_data.get('is_fragmented', False) else 0,
                bundle_data.get('fragment_count', 1),
                bundle_data.get('fragment_number', 0),
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
                    bundle_dict['hops'] = json.loads(bundle_dict['hops']) if bundle_dict.get('hops') else []
                    bundle_dict['route'] = json.loads(bundle_dict['route']) if bundle_dict.get('route') else []
                    # Parse security blocks
                    if bundle_dict.get('pcb'):
                        bundle_dict['pcb'] = json.loads(bundle_dict['pcb']) if isinstance(bundle_dict['pcb'], str) else bundle_dict['pcb']
                    if bundle_dict.get('pib'):
                        bundle_dict['pib'] = json.loads(bundle_dict['pib']) if isinstance(bundle_dict['pib'], str) else bundle_dict['pib']
                    if bundle_dict.get('bab'):
                        bundle_dict['bab'] = json.loads(bundle_dict['bab']) if isinstance(bundle_dict['bab'], str) else bundle_dict['bab']
                    # Convert boolean fields
                    bundle_dict['is_fragmented'] = bool(bundle_dict.get('is_fragmented', 0))
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error for bundle {bundle_dict.get('bundle_id')}: {e}")
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

