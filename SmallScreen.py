```python
""" 
This simplified version is optimized for a 2.13-inch e-ink display (250x122 pixels). Here are the key changes and features:

1. Display Size: Updated to use the `epd2in13_V3` module, which is compatible with the 2.13-inch display.

2. Simplified Layout:
   - Shows current temperature in large font
   - Displays current humidity
   - Shows estimated time to reach target temperature

3. Removed Features:
   - Removed the temperature gauge due to space constraints
   - Removed the historical data graph
   - Removed the detailed status messages

4. Optimized for Readability:
   - Uses larger fonts for key information
   - Rotates the display 90 degrees to make better use of the available space

5. Retained Core Functionality:
   - Still collects and stores data from the RuuviTag
   - Calculates estimated time to reach target temperature
   - Updates the display every minute

To use this version:

1. Make sure you have the correct Waveshare library installed for the 2.13-inch display (`epd2in13_V3`).
2. Update the `RUUVITAG_MAC` constant with your RuuviTag's MAC address.
3. Adjust the `TARGET_TEMP` if needed.
4. Run the script as before.
"""
import time
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V3
from ruuvitag_sensor.ruuvi import RuuviTagSensor

# Configuration
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"
TARGET_TEMP = 65
DB_NAME = "sauna_data.db"

# Global variables
current_temp = 0
current_humidity = 0
last_update_time = None

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS measurements
                 (timestamp TEXT PRIMARY KEY, temperature REAL, humidity REAL)''')
    conn.commit()
    conn.close()

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
    c.execute("SELECT * FROM measurements WHERE timestamp > ? ORDER BY timestamp DESC", (time_threshold,))
    data = c.fetchall()
    conn.close()
    return [{"time": row[0], "temperature": row[1], "humidity": row[2]} for row in data]

def handle_data(found_data):
    global current_temp, current_humidity, last_update_time
    if RUUVITAG_MAC in found_data:
        data = found_data[RUUVITAG_MAC]
        current_temp = data['temperature']
        current_humidity = data['humidity']
        last_update_time = datetime.now()
        store_measurement(last_update_time.strftime('%Y-%m-%d %H:%M:%S'), current_temp, current_humidity)

def start_realtime_listener():
    RuuviTagSensor.get_datas(handle_data, [RUUVITAG_MAC])

def get_estimated_time():
    historical_data = get_historical_data(hours=1)
    if len(historical_data) < 2:
        return "N/A"
    
    start_temp = historical_data[-1]['temperature']
    end_temp = historical_data[0]['temperature']
    time_diff = (datetime.strptime(historical_data[0]['time'], '%Y-%m-%d %H:%M:%S') -
                 datetime.strptime(historical_data[-1]['time'], '%Y-%m-%d %H:%M:%S')).total_seconds() / 3600
    
    if time_diff == 0 or start_temp == end_temp:
        return "N/A"
    
    temp_change_rate = (end_temp - start_temp) / time_diff
    if temp_change_rate <= 0:
        return "N/A"
    
    time_to_target = (TARGET_TEMP - end_temp) / temp_change_rate
    return f"{int(time_to_target * 60)}min"

def update_display(epd):
    image = Image.new('1', (epd.height, epd.width), 255)  # 1: clear the frame
    draw = ImageDraw.Draw(image)

    # Load fonts
    font18 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    font24 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)

    # Draw temperature
    draw.text((10, 10), f"Temp: {current_temp:.1f}°C", font=font24, fill=0)

    # Draw humidity
    draw.text((10, 40), f"Humidity: {current_humidity:.1f}%", font=font18, fill=0)

    # Draw estimated time to target
    est_time = get_estimated_time()
    draw.text((10, 70), f"Est. time to {TARGET_TEMP}°C:", font=font18, fill=0)
    draw.text((10, 95), est_time, font=font24, fill=0)

    # Rotate the image
    image = image.rotate(90, expand=True)

    epd.display(epd.getbuffer(image))

def main():
    setup_database()
    epd = epd2in13_V3.EPD()
    epd.init()
    epd.Clear(0xFF)

    start_realtime_listener()

    try:
        while True:
            if last_update_time:
                update_display(epd)
            time.sleep(60)  # Update every minute

    except KeyboardInterrupt:
        print("Exiting...")
        epd2in13_V3.epdconfig.module_exit()

if __name__ == "__main__":
    main()
```
