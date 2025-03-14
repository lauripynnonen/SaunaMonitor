import asyncio
import time
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V3
import random
import struct
import base64
from bleak import BleakClient, BleakScanner

# Configuration
RUUVITAG_MAC = "C3:94:E8:74:FB:D3"  # Updated MAC address
DB_NAME = "bedroom_monitor.db"
UPDATE_INTERVAL = 60   # 1 minute in seconds

# RuuviTag BLE constants
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
DATATYPE_LOG = 0x11

# Comfort ranges
COMFORT_TEMP_MIN = 18  # 18°C (64.4°F)
COMFORT_TEMP_MAX = 22  # 22°C (71.6°F)
COMFORT_HUMIDITY_MIN = 40
COMFORT_HUMIDITY_MAX = 60

class RuuviTagInterface:
    def __init__(self):
        self.current_temp = None
        self.current_humidity = None
        self.last_update_time = None
        self.last_data_store_time = None
        self.use_mock_data = False
        self.bluetooth_error = False
        self.temp_humidity_buffer = {}
        self.historical_data_received = False
        self.historical_data_count = 0

    async def start_realtime_listener(self):
        while True:
            if self.use_mock_data or self.bluetooth_error:
                mock_data = self.get_mock_data()
                self.handle_data(mock_data)
                await asyncio.sleep(10)  # Slower refresh for mock data
            else:
                try:
                    await self.scan_for_ruuvitag()
                except Exception as e:
                    print(f"Error in listener loop: {e}")
                    print("Falling back to mock data.")
                    self.bluetooth_error = True
                await asyncio.sleep(10)  # Check every 10 seconds

    async def scan_for_ruuvitag(self):
        def detection_callback(device, advertising_data):
            if device.address == RUUVITAG_MAC:
                manufacturer_data = advertising_data.manufacturer_data
                if 0x0499 in manufacturer_data:
                    self.handle_data(manufacturer_data[0x0499])

        async with BleakScanner(detection_callback=detection_callback) as scanner:
            await asyncio.sleep(5.0)

    def handle_data(self, data):
        if self.use_mock_data or self.bluetooth_error:
            parsed_data = data[RUUVITAG_MAC]
        else:
            parsed_data = self.parse_ruuvi_data(data)
        
        if parsed_data:
            self.current_temp = parsed_data.get('temperature', 0)
            self.current_humidity = parsed_data.get('humidity', 0)
            current_time = datetime.now()

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
                'temperature': random.uniform(18, 24),  # Bedroom temperatures
                'humidity': random.uniform(40, 60),     # Comfortable humidity range
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
                await self.mock_historical_data_download()
        except Exception as e:
            print(f"Error during historical data download: {e}")
            print("Falling back to mock historical data.")
            await self.mock_historical_data_download()

    async def mock_historical_data_download(self):
        print("Generating mock historical data...")
        current_time = datetime.now()
        for i in range(24):  # Generate 24 hours of mock data points
            timestamp = current_time - timedelta(hours=i)
            # Create realistic temperature patterns (warmer during day, cooler at night)
            hour = timestamp.hour
            base_temp = 21  # Base temperature
            day_variation = 2 * abs(12 - hour) / 12  # 0-2 degrees variation based on hour of day
            random_variation = random.uniform(-0.5, 0.5)  # Small random variation
            
            temperature = base_temp - day_variation + random_variation
            humidity = 50 + random.uniform(-5, 5)  # Random humidity around 50%
            
            store_measurement(timestamp.strftime('%Y-%m-%d %H:%M:%S'), temperature, humidity)
        print("Mock historical data generation complete.")

    def get_current_temp(self):
        return self.current_temp

    def get_current_humidity(self):
        return self.current_humidity

class Display:
    def __init__(self):
        self.epd = None
        self.is_sleeping = False

    def initialize(self):
        self.epd = epd2in13_V3.EPD()
        self.epd.init()
        self.epd.Clear(0xFF)
        print("E-ink display initialized")

    def update(self, current_temp, current_humidity):
        if self.is_sleeping:
            return
            
        # Reverse colors: black background with white text
        image = Image.new('1', (self.epd.height, self.epd.width), 0)  # 0: black background
        draw = ImageDraw.Draw(image)

        # Load fonts - make temperature font even larger
        font16 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
        font18 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
        # Increased font size for temperature
        font48 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 48)
        
        current_time = datetime.now().strftime("%H:%M")
        
        # Get screen dimensions for positioning
        screen_width = image.width
        screen_height = image.height
        
        # Draw temperature in large font, centered horizontally
        trend = get_temp_trend()
        temp_text = f"{current_temp:.1f}°C"
        
        # Get temp text dimensions to position it better
        temp_width = font48.getbbox(temp_text)[2]
        temp_height = font48.getbbox(temp_text)[3]
        
        # Center temperature text
        temp_x = (screen_width - temp_width) // 2
        draw.text((temp_x, 15), temp_text, font=font48, fill=255)
        
        # Draw trend arrow separated from the temperature to avoid clipping
        # Position it to the left of the temperature instead of right
        trend_x = temp_x - 35
        draw.text((trend_x, 15), trend, font=font48, fill=255)
        
        # Format humidity with label on left and value right-aligned
        humidity_label = "Humidity %"
        humidity_value = f"{current_humidity:.1f}"
        humidity_value_width = font18.getbbox(humidity_value)[2]
        
        # Draw humidity label on left
        draw.text((10, 75), humidity_label, font=font18, fill=255)
        
        # Draw humidity value aligned to right, similar to time
        draw.text((screen_width - humidity_value_width - 10, 75), humidity_value, font=font18, fill=255)
        
        # Draw comfort status
        status = get_comfort_status(current_temp, current_humidity)
        draw.text((10, 100), status, font=font18, fill=255)
        
        # Draw time at bottom right corner
        time_width = font18.getbbox(current_time)[2]
        draw.text((screen_width - time_width - 10, screen_height - 25), current_time, font=font18, fill=255)
        
        # Rotate the image
        image = image.rotate(90, expand=True)
        
        self.epd.display(self.epd.getbuffer(image))

    def sleep(self):
        if not self.is_sleeping:
            try:
                self.epd.sleep()
                self.is_sleeping = True
                print("Display is now sleeping")
            except Exception as e:
                print(f"Error putting display to sleep: {e}")

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS measurements
                 (timestamp TEXT PRIMARY KEY, temperature REAL, humidity REAL)''')
    conn.commit()
    conn.close()
    print("Database setup complete")

def store_measurement(timestamp, temperature, humidity):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO measurements VALUES (?, ?, ?)",
              (timestamp, temperature, humidity))
    conn.commit()
    conn.close()

def get_historical_data(hours=2):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("SELECT * FROM measurements WHERE timestamp > ? ORDER BY timestamp", (time_threshold,))
    data = c.fetchall()
    conn.close()
    return [{"time": row[0], "temperature": row[1], "humidity": row[2]} for row in data]

def get_temp_trend(hours=1):
    data = get_historical_data(hours=hours)
    if len(data) < 5:  # Need at least a few data points
        return "→"
    
    # Use the last 5 measurements to determine trend
    recent_temps = [entry["temperature"] for entry in data[-5:]]
    
    # Calculate average change
    changes = [recent_temps[i] - recent_temps[i-1] for i in range(1, len(recent_temps))]
    avg_change = sum(changes) / len(changes)
    
    if avg_change > 0.2:  # Rising significantly
        return "↑"
    elif avg_change < -0.2:  # Falling significantly
        return "↓"
    else:  # Stable
        return "→"

def get_comfort_status(temp, humidity):
    if (COMFORT_TEMP_MIN <= temp <= COMFORT_TEMP_MAX and 
        COMFORT_HUMIDITY_MIN <= humidity <= COMFORT_HUMIDITY_MAX):
        return "Ideal"
    elif temp < COMFORT_TEMP_MIN:
        return "Too Cold"
    elif temp > COMFORT_TEMP_MAX:
        return "Too Warm"
    elif humidity < COMFORT_HUMIDITY_MIN:
        return "Too Dry"
    else:
        return "Too Humid"

def cleanup_old_data(days=7):
    """Remove data older than the specified number of days"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("DELETE FROM measurements WHERE timestamp < ?", (threshold,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    print(f"Cleaned up {deleted_count} old data points")

async def main():
    print("Initializing Bedroom Temperature Monitor...")
    
    try:
        setup_database()
    except Exception as e:
        print(f"Error setting up database: {e}")
        return

    ruuvi = RuuviTagInterface()
    
    print("Attempting to download historical data...")
    try:
        await ruuvi.download_historical_data()
    except Exception as e:
        print(f"Error during historical data download: {e}")
        print("Continuing with real-time data only.")

    try:
        cleanup_old_data()
    except Exception as e:
        print(f"Error during old data cleanup: {e}")

    try:
        display = Display()
        display.initialize()
        print("Display initialized successfully.")

        # Get the latest data to update the display initially
        historical_data = get_historical_data(hours=1)
        if historical_data:
            latest_data = historical_data[-1]
            display.update(latest_data['temperature'], latest_data['humidity'])
            print("Display updated with historical data.")
        else:
            print("No historical data available for initial display update.")
    except Exception as e:
        print(f"Error initializing or updating display: {e}")
        print("Continuing without display updates.")
        display = None

    print("Starting real-time listener...")
    listener_task = asyncio.create_task(ruuvi.start_realtime_listener())

    last_update_time = 0
    last_cleanup = time.time()
    
    print("Entering main loop...")
    try:
        while True:
            current_time = time.time()

            current_temp = ruuvi.get_current_temp()
            current_humidity = ruuvi.get_current_humidity()

            if current_temp is not None and current_humidity is not None:
                print(f"Current readings - Temperature: {current_temp:.2f}°C, Humidity: {current_humidity:.2f}%")
                
                if display and current_time - last_update_time >= UPDATE_INTERVAL:
                    display.update(current_temp, current_humidity)
                    last_update_time = current_time

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                cleanup_old_data()
                last_cleanup = current_time

            await asyncio.sleep(10)

    except asyncio.CancelledError:
        print("Main loop cancelled. Cleaning up...")
    finally:
        print("Stopping listener and exiting...")
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        
        if display and not display.is_sleeping:
            display.sleep()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Exiting gracefully.")
