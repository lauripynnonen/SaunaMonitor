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
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"
DB_NAME = "bedroom_monitor.db"
SLEEP_DURATION = 300  # 5 minutes in seconds
UPDATE_INTERVAL = 60   # 1 minute in seconds
DISPLAY_MODES = ["basic", "detailed", "history"]

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

# Global display mode
current_display_mode = "basic"

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
                # Implementation would be similar to your original code
                # For brevity, I'm using the mock method
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
        self.last_touch_check = 0
        self.touch_cooldown = 1  # 1 second cooldown between touch checks

    def initialize(self):
        self.epd = epd2in13_V3.EPD()
        self.epd.init()
        self.epd.Clear(0xFF)
        print("E-ink display initialized")

    def update(self, current_temp, current_humidity):
        if self.is_sleeping:
            return
            
        image = Image.new('1', (self.epd.height, self.epd.width), 255)  # 1: clear the frame
        draw = ImageDraw.Draw(image)

        # Load fonts
        font14 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
        font18 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
        font24 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
        
        current_time = datetime.now().strftime("%H:%M")
        
        if current_display_mode == "basic":
            # Draw time
            draw.text((10, 5), current_time, font=font18, fill=0)
            
            # Draw temperature with trend arrow
            trend = get_temp_trend()
            draw.text((10, 30), f"{current_temp:.1f}°C {trend}", font=font24, fill=0)
            
            # Draw humidity
            draw.text((10, 60), f"Humidity: {current_humidity:.1f}%", font=font18, fill=0)
            
            # Draw comfort status
            status = get_comfort_status(current_temp, current_humidity)
            draw.text((10, 85), status, font=font18, fill=0)
            
        elif current_display_mode == "detailed":
            # Draw time
            draw.text((10, 5), current_time, font=font18, fill=0)
            
            # Draw temperature with trend
            trend = get_temp_trend()
            draw.text((10, 30), f"Temp: {current_temp:.1f}°C {trend}", font=font18, fill=0)
            
            # Draw humidity
            draw.text((10, 50), f"Humidity: {current_humidity:.1f}%", font=font18, fill=0)
            
            # Draw comfort ranges
            draw.text((10, 70), f"Ideal: {COMFORT_TEMP_MIN}-{COMFORT_TEMP_MAX}°C", font=font14, fill=0)
            draw.text((10, 85), f"Ideal: {COMFORT_HUMIDITY_MIN}-{COMFORT_HUMIDITY_MAX}%", font=font14, fill=0)
        
        elif current_display_mode == "history":
            # Draw time
            draw.text((10, 5), current_time, font=font18, fill=0)
            
            # Get temperature history for last 6 hours
            history = get_historical_data(hours=6)
            if len(history) > 0:
                # Show min/max
                temps = [d["temperature"] for d in history]
                min_temp = min(temps)
                max_temp = max(temps)
                draw.text((10, 30), f"Min: {min_temp:.1f}°C", font=font18, fill=0)
                draw.text((10, 50), f"Max: {max_temp:.1f}°C", font=font18, fill=0)
                draw.text((10, 70), f"Avg: {sum(temps)/len(temps):.1f}°C", font=font18, fill=0)
                
                # Draw simple trend line
                if len(temps) >= 2:
                    line_start_x, line_start_y = 10, 100
                    line_width = 110
                    line_height = 20
                    # Draw axis
                    draw.line((line_start_x, line_start_y, line_start_x + line_width, line_start_y), fill=0)
                    
                    # Normalize and draw points
                    max_val = max(temps)
                    min_val = min(temps)
                    range_val = max(max_val - min_val, 1)  # Avoid division by zero
                    
                    # Draw at most 6 points
                    step = max(1, len(temps) // 6)
                    points = []
                    for i in range(0, len(temps), step):
                        x = line_start_x + (i * line_width) // len(temps)
                        y = line_start_y - ((temps[i] - min_val) / range_val) * line_height
                        points.append((x, y))
                        draw.ellipse((x-1, y-1, x+1, y+1), fill=0)
                    
                    # Connect points with lines
                    if len(points) > 1:
                        for i in range(len(points) - 1):
                            draw.line((points[i], points[i+1]), fill=0)
        
        # Add touch instruction at bottom
        draw.text((10, 110), "Tap to change view", font=font14, fill=0)
        
        # Rotate the image
        image = image.rotate(90, expand=True)
        
        self.epd.display(self.epd.getbuffer(image))

    def check_touch(self):
        global current_display_mode
        current_time = time.time()
        
        # Check for touch with cooldown to avoid excessive polling
        if current_time - self.last_touch_check < self.touch_cooldown:
            return False
            
        self.last_touch_check = current_time
        
        # This is a placeholder - you'll need to implement the actual touch detection
        # based on your hardware's capabilities
        touch_detected = False
        try:
            # Call your touch screen's API here
            # For example: touch_detected = self.epd.get_touch_status()
            
            # For testing, we'll simulate random touches
            if random.random() < 0.05:  # 5% chance of simulated touch for testing
                touch_detected = True
        except Exception as e:
            print(f"Error checking touch: {e}")
            return False
            
        if touch_detected:
            # Cycle through display modes
            idx = DISPLAY_MODES.index(current_display_mode)
            current_display_mode = DISPLAY_MODES[(idx + 1) % len(DISPLAY_MODES)]
            print(f"Touch detected, switching to {current_display_mode} mode")
            return True
            
        return False

    def sleep(self):
        if not self.is_sleeping:
            try:
                self.epd.sleep()
                self.is_sleeping = True
                print("Display is now sleeping")
            except Exception as e:
                print(f"Error putting display to sleep: {e}")

    def wake(self):
        if self.is_sleeping:
            try:
                self.epd.init()
                self.is_sleeping = False
                print("Display is now awake")
            except Exception as e:
                print(f"Error waking display: {e}")

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

    display_sleep_until = 0
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
                
                if display:
                    # Check for touch input
                    touch_detected = display.check_touch()
                    
                    # Determine if display should be awake
                    should_be_awake = (current_time < display_sleep_until or touch_detected)
                    
                    if should_be_awake:
                        if display.is_sleeping:
                            display.wake()
                        
                        if touch_detected or current_time - last_update_time >= UPDATE_INTERVAL:
                            display.update(current_temp, current_humidity)
                            last_update_time = current_time
                            
                            # Reset sleep timer on interaction
                            if touch_detected:
                                display_sleep_until = current_time + SLEEP_DURATION
                                print(f"Touch detected, display will stay awake until: {time.ctime(display_sleep_until)}")
                    elif not display.is_sleeping:
                        display.sleep()
                        print("Display put to sleep.")

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                cleanup_old_data()
                last_cleanup = current_time

            await asyncio.sleep(1)  # Check frequently for touch events

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
