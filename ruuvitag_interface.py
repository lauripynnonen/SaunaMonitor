import asyncio
import time
from datetime import datetime, timedelta
import threading
import random
import os
import struct

from config import DATATYPE_LOG, LOG_SECONDS, RUUVITAG_MAC, USE_MOCK_DATA
from database import store_measurement

# Check if we're running on a Raspberry Pi
ON_RASPBERRY_PI = os.uname()[4][:3] == 'arm'

try:
    import bleak
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    print("Warning: bleak library not found. Install it with 'pip install bleak' for RuuviTag support.")

class MockRuuviTagSensor:
    @staticmethod
    def get_data_for_sensors(macs, retry_count=5):
        data = {
            RUUVITAG_MAC: {
                'temperature': random.uniform(20, 80),
                'humidity': random.uniform(20, 80),
                'pressure': random.uniform(950, 1050),
                'acceleration': random.uniform(990, 1010),
                'acceleration_x': random.uniform(-500, 500),
                'acceleration_y': random.uniform(-500, 500),
                'acceleration_z': random.uniform(-500, 500),
                'battery': random.randint(2000, 3200),
                'tx_power': 4,
                'movement_counter': random.randint(0, 100),
                'measurement_sequence_number': random.randint(0, 65535),
                'mac': RUUVITAG_MAC
            }
        }
        print(f"Mock RuuviTag data generated: Temp: {data[RUUVITAG_MAC]['temperature']:.2f}°C, Humidity: {data[RUUVITAG_MAC]['humidity']:.2f}%")
        return data

class RuuviTagInterface:
    def __init__(self):
        self.current_temp = 0
        self.current_humidity = 0
        self.last_update_time = None
        self.last_data_store_time = None
        self._stop_event = threading.Event()
        self._listener_thread = None
        self.use_mock_data = USE_MOCK_DATA
        self.bluetooth_error = False

    def parse_ruuvi_data(self, data):
        """Parse raw data from RuuviTag."""
        if data[0] == 0x05:
            (_, temp, humidity, pressure, acc_x, acc_y, acc_z, voltage) = struct.unpack('>BBhHHhhhH', data)
            return {
                'temperature': temp * 0.005,
                'humidity': humidity * 0.0025,
                'pressure': pressure + 50000,
                'acceleration_x': acc_x,
                'acceleration_y': acc_y,
                'acceleration_z': acc_z,
                'battery': voltage,
            }
        return None

    def handle_data(self, data):
        if self.use_mock_data or self.bluetooth_error:
            parsed_data = data[RUUVITAG_MAC]
        else:
            parsed_data = self.parse_ruuvi_data(data)
        
        if parsed_data:
            self.current_temp = parsed_data['temperature']
            self.current_humidity = parsed_data['humidity']
            current_time = datetime.now()

            # Store data every minute
            if self.last_data_store_time is None or (current_time - self.last_data_store_time).total_seconds() >= 60:
                store_measurement(current_time.strftime('%Y-%m-%d %H:%M:%S'), self.current_temp, self.current_humidity)
                self.last_data_store_time = current_time
                print(f"Stored measurement: Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {self.current_temp:.2f}°C, Humidity: {self.current_humidity:.2f}%")

            self.last_update_time = current_time

    async def scan_for_ruuvitag(self):
        try:
            def callback(device, advertising_data):
                if device.address == RUUVITAG_MAC:
                    manufacturer_data = advertising_data.manufacturer_data
                    if 0x0499 in manufacturer_data:
                        self.handle_data(manufacturer_data[0x0499])

            scanner = bleak.BleakScanner(callback)
            await scanner.start()
            await asyncio.sleep(5.0)
            await scanner.stop()
        except Exception as e:
            print(f"Error scanning for RuuviTag: {e}")
            print("Falling back to mock data.")
            self.bluetooth_error = True

    def start_realtime_listener(self):
        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._listener_thread.start()
        print(f"Real-time listener started. Using {'mock' if self.use_mock_data else 'real'} data.")

    def _listener_loop(self):
        while not self._stop_event.is_set():
            if self.use_mock_data or self.bluetooth_error:
                mock_data = MockRuuviTagSensor.get_data_for_sensors([RUUVITAG_MAC])
                self.handle_data(mock_data)
                time.sleep(1)
            else:
                try:
                    asyncio.run(self.scan_for_ruuvitag())
                except Exception as e:
                    print(f"Error in listener loop: {e}")
                    print("Falling back to mock data.")
                    self.bluetooth_error = True

    def stop_listener(self):
        if self._listener_thread and self._listener_thread.is_alive():
            self._stop_event.set()
            self._listener_thread.join(timeout=5)  # Wait up to 5 seconds for the thread to finish
            if self._listener_thread.is_alive():
                print("Warning: Listener thread did not stop gracefully.")
            else:
                print("Listener stopped successfully.")

    async def download_historical_data(self):
        if self.use_mock_data or self.bluetooth_error:
            print("Simulating historical data download...")
            for i in range(10):  # Generate 10 mock historical data points
                timestamp = datetime.now() - timedelta(minutes=random.randint(1, 120))
                temperature = random.uniform(20, 80)
                humidity = random.uniform(20, 80)
                store_measurement(timestamp.strftime('%Y-%m-%d %H:%M:%S'), temperature, humidity)
                print(f"Generated historical data point {i+1}: Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {temperature:.2f}°C, Humidity: {humidity:.2f}%")
            print("Mock historical data download complete.")
        else:
            print("Historical data download not implemented for real RuuviTag on PC.")
            print("Using real-time data collection instead.")

    def get_current_temp(self):
        return self.current_temp

    def get_current_humidity(self):
        return self.current_humidity

# Constants
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"