# -*- coding: utf-8 -*-
"""
Rework Tracking System

This module handles tracking faults and correlating them with rework solutions
across multiple test runs for the same stage serial number.

@author: TBates
"""

import sqlite3
import os
import json
import datetime
from typing import Optional, Dict, List, Tuple

class ReworkTracker:
    """
    Tracks faults and rework solutions across multiple test runs.
    Uses a local SQLite database to maintain state between runs.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the rework tracker.
        
        Args:
            db_path: Path to the SQLite database. If None, uses default location.
        """
        if db_path is None:
            # Use a central location for the rework tracking database
            base_dir = r"O:\CMP Check-out"
            os.makedirs(base_dir, exist_ok=True)
            self.db_path = os.path.join(base_dir, "rework_tracker.db")
        else:
            self.db_path = db_path
            
        self._initialize_database()
    
    def _initialize_database(self):
        """Create the rework tracking table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rework_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage_serial_number TEXT NOT NULL,
                    fault_run_timestamp TEXT NOT NULL,
                    fault_type TEXT NOT NULL,
                    fault_description TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    rework_solution TEXT,
                    rework_timestamp TEXT,
                    rework_emp_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stage_serial 
                ON rework_tracking(stage_serial_number, resolved)
            """)
    
    def log_fault(self, stage_serial: str, fault_type: str, fault_description: str = None) -> int:
        """
        Log a fault that occurred during testing.
        
        Args:
            stage_serial: Stage serial number (e.g., "ABC123456-01")
            fault_type: Type of fault that occurred
            fault_description: Optional detailed description
            
        Returns:
            The ID of the created rework tracking record
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO rework_tracking 
                (stage_serial_number, fault_run_timestamp, fault_type, fault_description)
                VALUES (?, ?, ?, ?)
            """, (stage_serial, timestamp, fault_type, fault_description))
            
            return cursor.lastrowid
    
    def get_pending_rework(self, stage_serial: str) -> Optional[Dict]:
        """
        Check if there are any unresolved faults for this stage serial number.
        
        Args:
            stage_serial: Stage serial number to check
            
        Returns:
            Dictionary with fault information if pending rework exists, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, fault_run_timestamp, fault_type, fault_description
                FROM rework_tracking 
                WHERE stage_serial_number = ? AND resolved = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            """, (stage_serial,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "fault_run_timestamp": row[1],
                    "fault_type": row[2],
                    "fault_description": row[3]
                }
        
        return None
    
    def log_rework_solution(self, stage_serial: str, rework_solution: str, emp_number: int) -> bool:
        """
        Log the rework solution for the most recent unresolved fault.
        
        Args:
            stage_serial: Stage serial number
            rework_solution: Description of what was done to fix the issue
            emp_number: Employee number of person who performed rework
            
        Returns:
            True if rework was logged successfully, False if no pending fault found
        """
        rework_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE rework_tracking 
                SET resolved = TRUE, 
                    rework_solution = ?, 
                    rework_timestamp = ?,
                    rework_emp_number = ?
                WHERE stage_serial_number = ? AND resolved = FALSE
            """, (rework_solution, rework_timestamp, emp_number, stage_serial))
            
            return cursor.rowcount > 0
    
    def get_rework_history(self, stage_serial: str) -> List[Dict]:
        """
        Get complete rework history for a stage serial number.
        
        Args:
            stage_serial: Stage serial number
            
        Returns:
            List of rework records for this stage
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT fault_run_timestamp, fault_type, fault_description, 
                       resolved, rework_solution, rework_timestamp, rework_emp_number
                FROM rework_tracking 
                WHERE stage_serial_number = ?
                ORDER BY created_at DESC
            """, (stage_serial,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "fault_run_timestamp": row[0],
                    "fault_type": row[1],
                    "fault_description": row[2],
                    "resolved": bool(row[3]),
                    "rework_solution": row[4],
                    "rework_timestamp": row[5],
                    "rework_emp_number": row[6]
                })
            
            return results
    
    def cleanup_old_records(self, days_old: int = 90):
        """
        Clean up old resolved rework records.
        
        Args:
            days_old: Remove resolved records older than this many days
        """
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM rework_tracking 
                WHERE resolved = TRUE AND created_at < ?
            """, (cutoff_str,))
            
            return cursor.rowcount