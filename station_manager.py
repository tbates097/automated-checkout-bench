import tkinter as tk
import threading
import time
import json
import os
import requests
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

STATION_CONFIG_FILE = "station_config.json"
station_update_queue = Queue()

class StationManager:
    def __init__(self, window):
        self.window = window
        self.station_dict = self.load_station_config()
        self.update_thread = None
        self.running = False
        
        # Initialize station states
        self.station_states = {
            station: {
                "status": "free",
                "serial_number": "",
                "program_id": None,
                "axis_name": station
            }
            for station in self.station_dict.keys()
        }
        
        # Add status display
        self.status_frame = tk.LabelFrame(window, text="Station Status")
        self.status_frame.grid(row=0, column=2, rowspan=2, padx=5, pady=5, sticky='nsew')
        self.status_labels = {}
    
    def load_station_config(self):
        """Load station configuration from file."""
        if os.path.exists(STATION_CONFIG_FILE):
            try:
                with open(STATION_CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading {STATION_CONFIG_FILE}. Using default configuration.")
        return {
            'ST01': '192.168.1.15',
            'ST02': '192.168.1.16',
            'ST03': '192.168.1.17'
        }

    def get_available_stations(self):
        """Return dictionary of available stations."""
        return {k: v for k, v in self.station_dict.items() 
                if self.station_states[k]["status"] == "free"}

    def is_station_available(self, station):
        """Check if a specific station is available."""
        return (station in self.station_dict and 
                self.station_states[station]["status"] == "free")

    def start(self):
        """Start the background station management thread"""
        self.running = True
        self.update_thread = threading.Thread(target=self._background_update_loop, daemon=True)
        self.update_thread.start()

    def stop(self):
        """Stop the background station management thread"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)

    def _background_update_loop(self):
        """Background loop to process station updates"""
        while self.running:
            try:
                self._check_station_connectivity()
                while not station_update_queue.empty():
                    update = station_update_queue.get_nowait()
                    self._process_station_update(update)
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in background update loop: {e}")

    def _check_station_connectivity(self):
        """Check connectivity of all stations"""
        with ThreadPoolExecutor() as executor:
            futures = []
            for station, ip in self.station_dict.items():
                futures.append(executor.submit(self._check_single_station, station, ip))
            
            for future in futures:
                try:
                    result = future.result(timeout=0.5)
                    if result:
                        station, is_connected = result
                        self._update_station_status(station, is_connected)
                except Exception as e:
                    print(f"Error checking station status: {e}")

    def _check_single_station(self, station, ip):
        """Check connectivity of a single station"""
        try:
            # Implement your actual connection test here
            # This is a placeholder - replace with actual connection test
            return station, True
        except Exception:
            return station, False

    def _update_station_status(self, station, is_connected):
        """Update the status display for a station"""
        if station in self.station_states:
            if not is_connected:
                self.station_states[station]["status"] = "error"
                self.update_station_display(station, "error")
            elif self.station_states[station]["status"] != "in-use":
                self.station_states[station]["status"] = "free"
                self.update_station_display(station, "free")

    def set_station_in_use(self, station, serial_number, program_id):
        """Mark a station as in-use"""
        if station in self.station_states:
            self.station_states[station].update({
                "status": "in-use",
                "serial_number": serial_number,
                "program_id": program_id
            })
            self.update_station_display(station, "in-use", serial_number)

    def release_station(self, station):
        """Release a station back to available pool"""
        if station in self.station_states:
            self.station_states[station].update({
                "status": "connected",
                "serial_number": "",
                "program_id": None
            })
            self.update_station_display(station, "connected")

    def get_station_status(self, station):
        """Get the current status of a station"""
        if station in self.station_states:
            return self.station_states[station].copy()
        return None

    def allocate_stations(self, num_stations, program_id, serial_number):
        """
        Attempt to allocate the requested number of stations.
        
        Returns:
            list: List of allocated station names, or None if not enough available
        """
        available = self.get_available_stations()
        if len(available) < num_stations:
            return None
        
        # Get the first num_stations available stations
        allocated = list(available.keys())[:num_stations]
        
        # Mark them as in-use
        for station in allocated:
            self.set_station_in_use(station, serial_number, program_id)
        
        return allocated

    def release_stations(self, stations):
        """Release a list of stations"""
        for station in stations:
            self.release_station(station)

    def update_station_display(self, station, status, serial=""):
        """Update the visual status of a station"""
        if station in self.status_labels:
            color = {
                'in-use': 'red',
                'free': 'green',
                'error': 'orange'
            }.get(status, 'gray')
            
            self.window.after(0, lambda: self._update_label(station, color, serial))

    def _update_label(self, station, color, serial):
        """Update label in the main thread"""
        self.status_labels[station]['indicator'].config(fg=color)
        self.status_labels[station]['serial'].config(text=serial)

    def _process_station_update(self, update):
        """Process a station update from the queue"""
        station, ip, available = update
        if available:
            self.station_dict[station] = ip
            if station not in self.station_states:
                self.station_states[station] = {
                    "status": "free",
                    "serial_number": "",
                    "program_id": None,
                    "axis_name": station
                }
        elif station in self.station_dict:
            del self.station_dict[station]
            if station in self.station_states:
                del self.station_states[station]
        self.save_station_config()

    def save_station_config(self):
        """Save station configuration to file."""
        with open(STATION_CONFIG_FILE, 'w') as f:
            json.dump(self.station_dict, f)

    def refresh_station_status(self):
        """Refresh the status of all stations."""
        for station_name in self.station_states:
            if self.station_states[station_name]["status"] != "connected":
                self.station_states[station_name]["status"] = "free"
                self.station_states[station_name]["program_id"] = None
                self.station_states[station_name]["serial_number"] = ""

    def release_station(self, station_id):
        """Release a specific station."""
        station_name = f'ST{station_id:02d}'
        if station_name in self.station_states:
            self.station_states[station_name]["status"] = "connected"  # Change to "connected" instead of "free"
            self.station_states[station_name]["program_id"] = None
            self.station_states[station_name]["serial_number"] = "" 