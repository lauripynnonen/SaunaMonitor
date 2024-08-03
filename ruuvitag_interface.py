from config import DATATYPE_LOG, LOG_SECONDS, RUUVITAG_MAC, UART_RX_CHAR_UUID, UART_TX_CHAR_UUID
import asyncio
import time
import struct
from datetime import datetime, timedelta
import threading
import random
import os

from config import DATATYPE_LOG, LOG_SECONDS, RUUVITAG_MAC
from database import store_measurement

# Check if we're running on a Raspberry Pi
ON_RASPBERRY_PI = os.uname()[4][:3] == 'arm'

if ON_RASPBERRY_PI:
    from ruuvitag_sensor.ruuvi import RuuviTagSensor
    RUUVITAG_AVAILABLE = True
else:
    print("Not running on Raspberry Pi. Using mock RuuviTag sensor.")
    RUUVITAG_AVAILABLE = False

try:
    import bleak
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    print("Warning: bleak library not found. Historical data download will not be available.")

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

    @staticmethod
    def get_datas(handle_data, macs, run_flag=None):
        while run_flag is None or not run_flag.is_set():
            data = MockRuuviTagSensor.get_data_for_sensors(macs)
            handle_data(data)
            time.sleep(1)

class RuuviTagInterface:
    def __init__(self):
        self.current_temp = 0
        self.current_humidity = 0
        self.last_update_time = None
        self.last_data_store_time = None
        self._stop_event = threading.Event()
        self._listener_thread = None

    def handle_data(self, found_data):
        if RUUVITAG_MAC in found_data:
            data = found_data[RUUVITAG_MAC]
            self.current_temp = data['temperature']
            self.current_humidity = data['humidity']
            current_time = datetime.now()

            # Store data every minute
            if self.last_data_store_time is None or (current_time - self.last_data_store_time).total_seconds() >= 60:
                store_measurement(current_time.strftime('%Y-%m-%d %H:%M:%S'), self.current_temp, self.current_humidity)
                self.last_data_store_time = current_time
                print(f"Stored measurement: Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {self.current_temp:.2f}°C, Humidity: {self.current_humidity:.2f}%")

            self.last_update_time = current_time

    def start_realtime_listener(self):
        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._listener_thread.start()
        print("Real-time listener started.")

    def _listener_loop(self):
        sensor = RuuviTagSensor if RUUVITAG_AVAILABLE else MockRuuviTagSensor
        while not self._stop_event.is_set():
            try:
                sensor.get_datas(self.handle_data, [RUUVITAG_MAC], run_flag=self._stop_event)
            except Exception as e:
                print(f"Error in listener loop: {e}")
                time.sleep(5)  # Wait a bit before retrying

    def stop_listener(self):
        if self._listener_thread and self._listener_thread.is_alive():
            self._stop_event.set()
            self._listener_thread.join(timeout=5)  # Wait up to 5 seconds for the thread to finish
            if self._listener_thread.is_alive():
                print("Warning: Listener thread did not stop gracefully.")
            else:
                print("Listener stopped successfully.")

    async def download_historical_data(self):
        if not BLEAK_AVAILABLE:
            print("Error: bleak library is not available. Cannot download historical data.")
            return

        if not ON_RASPBERRY_PI:
            print("Simulating historical data download...")
            for i in range(10):  # Generate 10 mock historical data points
                timestamp = datetime.now() - timedelta(minutes=random.randint(1, 120))
                temperature = random.uniform(20, 80)
                humidity = random.uniform(20, 80)
                store_measurement(timestamp.strftime('%Y-%m-%d %H:%M:%S'), temperature, humidity)
                print(f"Generated historical data point {i+1}: Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {temperature:.2f}°C, Humidity: {humidity:.2f}%")
            print("Mock historical data download complete.")
            return
        
        log_data_end_of_data = False
        historical_data = []

        def handle_rx(_: int, data: bytearray):
            nonlocal log_data_end_of_data, historical_data
            if len(data) > 0 and data[0] == DATATYPE_LOG:
                if len(data) == 11:
                    dat = struct.unpack('>BBBII', data)
                    if dat[3] == 0xFFFFFFFF and dat[4] == 0xFFFFFFFF:
                        log_data_end_of_data = True
                    else:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dat[3]))
                        if dat[1] == 0x30:  # Temperature
                            historical_data.append((timestamp, dat[4]/100.0, None))
                        elif dat[1] == 0x31:  # Humidity
                            # Find the matching temperature entry and update it
                            for i, (t, temp, _) in enumerate(historical_data):
                                if t == timestamp:
                                    historical_data[i] = (t, temp, dat[4]/100.0)
                                    break

        try:
            async with bleak.BleakClient(RUUVITAG_MAC) as client:
                await client.start_notify(UART_TX_CHAR_UUID, handle_rx)

                # Request log data
                timenow = int(time.time())
                timeprv = timenow - LOG_SECONDS
                data_tx = struct.pack('>BBBIIII', DATATYPE_LOG, DATATYPE_LOG, 0x11, timenow, timeprv)
                await client.write_gatt_char(UART_RX_CHAR_UUID, data_tx)

                while not log_data_end_of_data:
                    await asyncio.sleep(1)

            # Store the downloaded historical data
            for timestamp, temperature, humidity in historical_data:
                if temperature is not None and humidity is not None:
                    store_measurement(timestamp, temperature, humidity)
        except Exception as e:
            print(f"Error downloading historical data: {e}")

    def get_current_data(self):
        sensor = RuuviTagSensor if RUUVITAG_AVAILABLE else MockRuuviTagSensor
        data = sensor.get_data_for_sensors([RUUVITAG_MAC], 5)
        if RUUVITAG_MAC in data:
            return data[RUUVITAG_MAC]
        return None

    def get_current_temp(self):
        return self.current_temp

    def get_current_humidity(self):
        return self.current_humidity