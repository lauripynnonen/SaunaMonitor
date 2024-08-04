import asyncio
import time
from datetime import datetime, timedelta
import random
import struct
import base64
from bleak import BleakClient, BleakScanner

from config import DATATYPE_LOG, LOG_SECONDS, RUUVITAG_MAC, USE_MOCK_DATA
from database import store_measurement

class RuuviTagInterface:
    def __init__(self):
        self.current_temp = None
        self.current_humidity = None
        self.last_update_time = None
        self.last_data_store_time = None
        self.use_mock_data = USE_MOCK_DATA
        self.bluetooth_error = False
        self.temp_humidity_buffer = {}
        self.historical_data_ended = False
        self.historical_data_received = False
        self.historical_data_count = 0

    async def start_realtime_listener(self):
        while True:
            if self.use_mock_data or self.bluetooth_error:
                mock_data = self.get_mock_data()
                self.handle_data(mock_data)
                await asyncio.sleep(1)
            else:
                try:
                    await self.scan_for_ruuvitag()
                except Exception as e:
                    print(f"Error in listener loop: {e}")
                    print("Falling back to mock data.")
                    self.bluetooth_error = True
                await asyncio.sleep(1)

    async def scan_for_ruuvitag(self):
        def detection_callback(device, advertising_data):
            if device.address == RUUVITAG_MAC:
                manufacturer_data = advertising_data.manufacturer_data
                if 0x0499 in manufacturer_data:
                    self.handle_data(manufacturer_data[0x0499])

        scanner = BleakScanner()
        scanner.register_detection_callback(detection_callback)
        await scanner.start()
        await asyncio.sleep(5.0)
        await scanner.stop()

    def handle_data(self, data):
        if self.use_mock_data or self.bluetooth_error:
            parsed_data = data[RUUVITAG_MAC]
        else:
            parsed_data = self.parse_ruuvi_data(data)
        
        if parsed_data:
            self.current_temp = parsed_data.get('temperature', 0)
            self.current_humidity = parsed_data.get('humidity', 0)
            current_time = datetime.now()

            print(f"Parsed data:")
            print(f"  Temperature: {self.current_temp:.2f}°C")
            print(f"  Humidity: {self.current_humidity:.2f}%")
            print(f"  Pressure: {parsed_data.get('pressure', 'N/A')} Pa")
            print(f"  Acceleration: X={parsed_data.get('acceleration_x', 'N/A')}, Y={parsed_data.get('acceleration_y', 'N/A')}, Z={parsed_data.get('acceleration_z', 'N/A')}")
            print(f"  Battery: {parsed_data.get('battery', 'N/A')} mV")
            print(f"  TX Power: {parsed_data.get('tx_power', 'N/A')} dBm")
            if 'mac_address' in parsed_data:
                print(f"  MAC Address: {parsed_data['mac_address']}")

            # Store data every minute
            if self.last_data_store_time is None or (current_time - self.last_data_store_time).total_seconds() >= 60:
                store_measurement(current_time.strftime('%Y-%m-%d %H:%M:%S'), self.current_temp, self.current_humidity)
                self.last_data_store_time = current_time
                print(f"Stored measurement: Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {self.current_temp:.2f}°C, Humidity: {self.current_humidity:.2f}%")

            self.last_update_time = current_time
        else:
            print("Failed to parse RuuviTag data")

    def parse_ruuvi_data(self, data):
        """Parse raw data from RuuviTag."""
        print(f"Received data: {data.hex()}")  # Debug print
        if isinstance(data, str):
            # If data is a string, assume it's base64 encoded
            data = base64.b64decode(data)
        
        data_format = data[0]
        
        if data_format == 0x05:
            # Data Format 5 (extended)
            if len(data) == 24:  # Extended format with MAC address
                try:
                    (temp, humidity, pressure, acc_x, acc_y, acc_z, power_info) = struct.unpack('>hHHhhhH', data[1:15])
                    mac_address = data[15:].hex()
                    return {
                        'temperature': temp * 0.005,
                        'humidity': humidity * 0.0025,
                        'pressure': pressure + 50000,
                        'acceleration_x': acc_x,
                        'acceleration_y': acc_y,
                        'acceleration_z': acc_z,
                        'battery': power_info >> 5,
                        'tx_power': (power_info & 0x1F) * 2 - 40,
                        'mac_address': mac_address
                    }
                except struct.error as e:
                    print(f"Error unpacking extended data: {e}")
                    return None
            elif len(data) == 16:  # Original format without MAC address
                try:
                    (_, temp, humidity, pressure, acc_x, acc_y, acc_z, power_info) = struct.unpack('>BhHHhhhH', data)
                    return {
                        'temperature': temp * 0.005,
                        'humidity': humidity * 0.0025,
                        'pressure': pressure + 50000,
                        'acceleration_x': acc_x,
                        'acceleration_y': acc_y,
                        'acceleration_z': acc_z,
                        'battery': power_info >> 5,
                        'tx_power': (power_info & 0x1F) * 2 - 40
                    }
                except struct.error as e:
                    print(f"Error unpacking data: {e}")
                    return None
            else:
                print(f"Unexpected data length for format 5: {len(data)} bytes")
                return None
        else:
            print(f"Unknown data format: {data_format}")
            return None

    def get_mock_data(self):
        return {
            RUUVITAG_MAC: {
                'temperature': random.uniform(20, 80),
                'humidity': random.uniform(20, 80),
                'pressure': random.uniform(950, 1050),
                'acceleration_x': random.uniform(-500, 500),
                'acceleration_y': random.uniform(-500, 500),
                'acceleration_z': random.uniform(-500, 500),
                'battery': random.randint(2000, 3200),
                'tx_power': 4,
            }
        }

    async def download_historical_data(self):
        print("Starting historical data download...")
        if self.use_mock_data or self.bluetooth_error:
            print("Using mock data for historical download.")
            await self.mock_historical_data_download()
            return

        try:
            async with BleakClient(RUUVITAG_MAC, timeout=30.0) as client:
                print(f"Connected to RuuviTag: {RUUVITAG_MAC}")

                await client.start_notify(UART_TX_CHAR_UUID, self.handle_historical_data)

                print("Requesting log data...")
                current_time = int(time.time())
                start_time = current_time - LOG_SECONDS
                request_data = struct.pack('>BBBIIII', DATATYPE_LOG, DATATYPE_LOG, 0x11, current_time, start_time, 0, 0)
                await client.write_gatt_char(UART_RX_CHAR_UUID, request_data)

                print("Waiting for historical data...")
                await asyncio.sleep(60)  # Wait for up to 60 seconds for data

                await client.stop_notify(UART_TX_CHAR_UUID)

            print("Historical data download process completed.")
            if not self.historical_data_received:
                print("Warning: No historical data was received during the download process.")
                await self.mock_historical_data_download()
            else:
                print(f"Received {self.historical_data_count} historical data points.")

        except Exception as e:
            print(f"Error during historical data download: {e}")
            if "The operation was canceled by the user" in str(e):
                print("This error is expected and doesn't indicate a failure in data retrieval.")
                if self.historical_data_received:
                    print("Historical data was successfully retrieved before the connection closed.")
                    return
            print("Falling back to mock historical data.")
            await self.mock_historical_data_download()

    def handle_historical_data(self, sender, data):
        if self.historical_data_ended:
            return

        print(f"Received historical data packet: {data.hex()}")
        if len(data) == 11 and data[0] == DATATYPE_LOG:
            timestamp, value = struct.unpack('>II', data[3:11])
            if timestamp == 0xFFFFFFFF and value == 0xFFFFFFFF:
                print("End of historical data reached.")
                self.historical_data_ended = True
                return

            timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            if data[1] == 0x30:  # Temperature
                temperature = value / 100.0
                print(f"Historical temperature: {temperature}°C at {timestamp_str}")
                if timestamp_str in self.temp_humidity_buffer:
                    humidity = self.temp_humidity_buffer.pop(timestamp_str)
                    store_measurement(timestamp_str, temperature, humidity)
                    print(f"Stored combined measurement: Timestamp: {timestamp_str}, Temp: {temperature}, Humidity: {humidity}")
                    self.historical_data_count += 1
                else:
                    self.temp_humidity_buffer[timestamp_str] = temperature
            elif data[1] == 0x31:  # Humidity
                humidity = value / 100.0
                print(f"Historical humidity: {humidity}% at {timestamp_str}")
                if timestamp_str in self.temp_humidity_buffer:
                    temperature = self.temp_humidity_buffer.pop(timestamp_str)
                    store_measurement(timestamp_str, temperature, humidity)
                    print(f"Stored combined measurement: Timestamp: {timestamp_str}, Temp: {temperature}, Humidity: {humidity}")
                    self.historical_data_count += 1
                else:
                    self.temp_humidity_buffer[timestamp_str] = humidity

            self.historical_data_received = True
        elif data[0] == 0x05:
            print("Received real-time data packet. Ignoring for historical download.")
        else:
            print(f"Unexpected data format: {data.hex()}")

    async def mock_historical_data_download(self):
        print("Generating mock historical data...")
        current_time = datetime.now()
        for i in range(10):  # Generate 10 mock historical data points
            timestamp = current_time - timedelta(minutes=i*10)
            temperature = 20 + i  # Mock temperature increasing over time
            humidity = 50 + i  # Mock humidity increasing over time
            store_measurement(timestamp.strftime('%Y-%m-%d %H:%M:%S'), temperature, humidity)
            print(f"Generated mock data point {i+1}: Time: {timestamp}, Temp: {temperature}°C, Humidity: {humidity}%")
        print("Mock historical data generation complete.")

    def get_current_temp(self):
        return self.current_temp

    def get_current_humidity(self):
        return self.current_humidity

# Constants
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"