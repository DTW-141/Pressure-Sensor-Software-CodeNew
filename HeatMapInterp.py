"""PC heatmap for one Pico sensor. Run SensorTest.py as main.py on the Pico.

Install PC dependencies: python -m pip install numpy matplotlib pyserial
Close Thonny's serial connection before connecting here.
"""

import tkinter as tk
from tkinter import ttk
from time import monotonic

import numpy as np
import serial
from serial.tools import list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class ForceMapApp:
    ROWS = 1
    COLS = 1
    UPDATE_MS = 200

    def __init__(self, root):
        self.root = root
        self.root.title("Live FSR01 Sensor — GP27")
        self.running = True
        self.pending_update = None
        self.connection = None
        self.receive_buffer = b""
        self.connected_at = None
        self.last_reading_at = None
        self.received_bytes = 0

        controls = ttk.Frame(root)
        controls.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(controls, text="Pico USB port:").pack(side=tk.LEFT)
        self.port = ttk.Combobox(controls, width=16, state="readonly")
        self.port.pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT)
        self.connect_button = ttk.Button(
            controls, text="Connect", command=self.toggle_connection
        )
        self.connect_button.pack(side=tk.LEFT, padx=8)
        self.status = tk.StringVar(value="Select the Pico's port and click Connect.")
        ttk.Label(root, textvariable=self.status, wraplength=600).pack(padx=8)
        self.serial_preview = tk.StringVar(value="USB data: none received")
        ttk.Label(root, textvariable=self.serial_preview, wraplength=600).pack(padx=8)
        self.refresh_ports()

        figure = Figure(figsize=(7, 5), dpi=100)
        axes = figure.add_subplot(111)

        # Keep the color scale fixed so colors remain comparable over time.
        self.heatmap = axes.imshow(
            np.full((self.ROWS, self.COLS), np.nan),
            cmap="inferno",
            vmin=0,
            vmax=65535,
            interpolation="nearest",
            origin="upper",
        )

        axes.set(
            title="FSR01 — GP27",
            xticks=range(self.COLS),
            yticks=range(self.ROWS),
            xticklabels=range(1, self.COLS + 1),
            yticklabels=range(1, self.ROWS + 1),
        )
        self.reading_text = axes.text(
            0, 0, "Waiting for data", ha="center", va="center", color="white",
            bbox=dict(facecolor="black", alpha=0.6, edgecolor="none"),
        )

        figure.colorbar(self.heatmap, ax=axes, label="Raw sensor reading")
        figure.tight_layout()

        self.canvas = FigureCanvasTkAgg(figure, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.pause_button = tk.Button(
            root, text="Pause", command=self.toggle_running
        )
        self.pause_button.pack(pady=8)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.update_heatmap()

    def refresh_ports(self):
        ports = [port.device for port in list_ports.comports()]
        self.port["values"] = ports
        if self.port.get() not in ports:
            self.port.set(ports[0] if ports else "")

    def disconnect(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.receive_buffer = b""
        self.connected_at = None
        self.connect_button.config(text="Connect")

    def toggle_connection(self):
        if self.connection is not None:
            self.disconnect()
            self.status.set("Disconnected. Display holds the last reading.")
            return
        if not self.port.get():
            self.status.set("No port selected. Plug in the Pico and click Refresh.")
            return
        try:
            # Nonblocking reads keep the window responsive if no data arrives.
            self.connection = serial.Serial(self.port.get(), 115200, timeout=0)
        except (serial.SerialException, OSError) as error:
            self.status.set("Could not connect: {}. Close Thonny's connection.".format(error))
            return
        self.receive_buffer = b""
        self.connected_at = monotonic()
        self.last_reading_at = None
        self.received_bytes = 0
        self.serial_preview.set("USB data: none received")
        self.connect_button.config(text="Disconnect")
        self.status.set("Connected to {}. Waiting for Raw: readings...".format(self.port.get()))

    def read_sensors(self):
        """Return the newest complete Raw: reading, or None if none arrived."""
        if self.connection is None:
            return None
        chunk = self.connection.read(min(self.connection.in_waiting, 4096))
        if chunk:
            self.received_bytes += len(chunk)
            self.serial_preview.set(
                "Latest USB data: " + repr(chunk.decode("utf-8", errors="replace")[-200:])
            )
        self.receive_buffer += chunk
        lines = self.receive_buffer.split(b"\n")
        self.receive_buffer = lines.pop()
        if len(self.receive_buffer) > 4096:
            self.receive_buffer = b""
        latest = None
        for line in lines:
            text = line.decode("utf-8", errors="replace").strip()
            if not text.startswith("Raw:"):
                continue
            try:
                raw = int(text.split(":", 1)[1].split()[0])
            except (ValueError, IndexError):
                continue
            if 0 <= raw <= 65535:
                latest = raw
        return latest

    def update_heatmap(self):
        try:
            # Drain USB even while paused so Resume shows current data.
            readings = self.read_sensors()
        except (serial.SerialException, OSError) as error:
            self.disconnect()
            self.status.set("Serial connection lost: {}".format(error))
            readings = None
        if readings is not None:
            self.last_reading_at = monotonic()
            self.status.set(
                "Receiving live readings from {}{}".format(
                    self.connection.port, " (display paused)" if not self.running else ""
                )
            )
        elif self.connection is not None:
            last_activity = self.last_reading_at or self.connected_at
            if last_activity is not None and monotonic() - last_activity > 3:
                if self.last_reading_at is not None:
                    self.status.set("Readings stopped. Display holds the last value. Check the Pico script.")
                elif not self.received_bytes:
                    self.status.set(
                        "Port open, but the Pico is sending no data. Save SensorTest.py as "
                        "main.py on the Pico, close Thonny, and restart the Pico."
                    )
                else:
                    self.status.set(
                        "USB data received, but no valid Raw: readings. Check Latest USB data "
                        "below for a MicroPython prompt or an error."
                    )
        if self.running and readings is not None:
            voltage = readings * 3.3 / 65535
            self.heatmap.set_data([[readings]])
            self.reading_text.set_text("Raw: {}\n{:.3f} V".format(readings, voltage))
            self.canvas.draw_idle()

        # Schedule the next refresh without blocking Tkinter's event loop.
        self.pending_update = self.root.after(
            self.UPDATE_MS, self.update_heatmap
        )

    def toggle_running(self):
        self.running = not self.running
        self.pause_button.config(text="Pause" if self.running else "Resume")

    def close(self):
        if self.pending_update is not None:
            self.root.after_cancel(self.pending_update)
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ForceMapApp(root)
    root.mainloop()
