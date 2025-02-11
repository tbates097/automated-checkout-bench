import tkinter as tk
from tkinter import Text
import threading


class SecondaryUI:
    def __init__(self):
        # Initialize the window
        self.window = tk.Tk()
        self.window.title("Station Monitor")
        self.window.attributes("-fullscreen", True)
        self.window.configure(bg="#1e1e1e")  # Night mode background

        self.station_widgets = {}  # Store widgets for each station
        self.lock = threading.Lock()  # Ensure thread-safe updates

        # Configure grid layout for consistent frame scaling
        for row in range(2):  # 2 rows
            self.window.grid_rowconfigure(row, weight=1)
        for col in range(5):  # 5 columns
            self.window.grid_columnconfigure(col, weight=1)

        # Create frames for 10 stations
        for i in range(1, 11):
            frame = tk.Frame(
                self.window,
                bg="#1e1e1e",
                highlightbackground="#444",
                highlightthickness=1,
            )
            frame.grid(
                row=(i - 1) // 5,
                column=(i - 1) % 5,
                padx=10,
                pady=10,
                sticky="nsew",
            )

            # Main label for station (e.g., "Station 1")
            lbl_station = tk.Label(
                frame,
                text=f"Station {i}",
                fg="white",
                bg="#1e1e1e",
                font=("Arial", 16, "bold"),
            )
            lbl_station.pack(pady=(5, 10))

            # Status label with colored indicator
            lbl_status = tk.Label(
                frame,
                text="Test Running:",
                fg="white",
                bg="#1e1e1e",
                font=("Arial", 14),
            )
            lbl_status.pack(pady=(10, 5))

            indicator = tk.Label(
                frame,
                bg="red",
                width=2,
                height=1,
                relief="flat",
            )
            indicator.pack(pady=(0, 10))

            # Serial number field
            lbl_serial = tk.Label(
                frame,
                text="Serial Number:",
                fg="white",
                bg="#1e1e1e",
                font=("Arial", 12),
            )
            lbl_serial.pack(pady=(0, 5))

            entry_serial = tk.Entry(
                frame,
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 12),
                justify="center",
                relief="flat",
            )
            entry_serial.pack(pady=(0, 10), ipadx=10, ipady=5)

            # Text widget for logs
            txt_logs = Text(
                frame,
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10),
                wrap="word",
                state="disabled",
            )
            txt_logs.pack(expand=True, fill="both", padx=5, pady=5)

            # Save references to widgets
            self.station_widgets[i] = {
                "frame": frame,
                "lbl_station": lbl_station,
                "indicator": indicator,
                "entry_serial": entry_serial,
                "txt_logs": txt_logs,
            }

    def update_station_status(self, stations, running=False, serial=None):
        """
        Update the status and serial number of multiple stations.

        Parameters:
            stations (list[int]): List of station IDs (1-10).
            running (bool): True if the stations are running, False otherwise.
            serial (str): Optional serial number to display (applies to all stations).
        """
        with self.lock:
            for station in stations:
                widget = self.station_widgets.get(station)
                if widget:
                    # Update indicator color
                    color = "green" if running else "red"
                    widget["indicator"].config(bg=color)

                    # Update serial number
                    if serial:
                        widget["entry_serial"].delete(0, tk.END)
                        widget["entry_serial"].insert(0, serial)

    def append_logs(self, stations, message):
        """
        Append a message to the text widgets of multiple stations.

        Parameters:
            stations (list[int]): List of station IDs (1-10).
            message (str): Log message to append.
        """
        with self.lock:
            for station in stations:
                widget = self.station_widgets.get(station)
                if widget:
                    txt_logs = widget["txt_logs"]
                    txt_logs.config(state="normal")  # Enable editing
                    txt_logs.insert(tk.END, message + "\n")
                    txt_logs.see(tk.END)  # Scroll to the end
                    txt_logs.config(state="disabled")  # Disable editing

    def clear_logs(self, stations):
        """
        Clear the logs for multiple stations.

        Parameters:
            stations (list[int]): List of station IDs (1-10).
        """
        with self.lock:
            for station in stations:
                widget = self.station_widgets.get(station)
                if widget:
                    txt_logs = widget["txt_logs"]
                    txt_logs.config(state="normal")  # Enable editing
                    txt_logs.delete(1.0, tk.END)
                    txt_logs.config(state="disabled")  # Disable editing

    def run(self):
        """Run the secondary UI."""
        self.window.mainloop()


# Example Usage
if __name__ == "__main__":
    ui = SecondaryUI()

    # Simulate station updates
    ui.update_station_status([1, 2], running=True, serial="SN12345")
    ui.append_logs([1, 2], "Stations 1 and 2 started.")
    ui.append_logs([1, 2], "Performing test...")

    ui.update_station_status([3], running=False)
    ui.append_logs([3], "Station 3 is free.")

    ui.run()
