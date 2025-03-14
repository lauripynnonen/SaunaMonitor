import time
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V3
from ruuvitag_sensor.ruuvi import RuuviTagSensor

# Configuration
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"
COMFORT_TEMP_MIN = 18  # 18°C (64.4°F)
COMFORT_TEMP_MAX = 22  # 22°C (71.6°F)
COMFORT_HUMIDITY_MIN = 40
COMFORT_HUMIDITY_MAX = 60
DB_NAME = "room_monitor.db"
DISPLAY_MODES = ["basic", "detailed", "history"]

# Global variables
current_temp = 0
current_humidity = 0
last_update_time = None
current_display_mode = "basic"

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

def get_comfort_status():
    if (COMFORT_TEMP_MIN <= current_temp <= COMFORT_TEMP_MAX and 
        COMFORT_HUMIDITY_MIN <= current_humidity <= COMFORT_HUMIDITY_MAX):
        return "Ideal"
    elif current_temp < COMFORT_TEMP_MIN:
        return "Too Cold"
    elif current_temp > COMFORT_TEMP_MAX:
        return "Too Warm"
    elif current_humidity < COMFORT_HUMIDITY_MIN:
        return "Too Dry"
    else:
        return "Too Humid"

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

def check_touch(epd):
    global current_display_mode
    # Simple implementation - in reality, you would use the touch screen's API
    # This is a placeholder for the touch functionality
    if epd.touch_detected():  # This is a hypothetical method
        touch_x, touch_y = epd.get_touch_position()  # This is a hypothetical method
        
        # If touch in top region, cycle display modes
        if touch_y < 30:
            idx = DISPLAY_MODES.index(current_display_mode)
            current_display_mode = DISPLAY_MODES[(idx + 1) % len(DISPLAY_MODES)]
            return True
    return False

def update_display(epd):
    image = Image.new('1', (epd.height, epd.width), 255)  # 1: clear the frame
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
        status = get_comfort_status()
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
        
        # Last update time
        if last_update_time:
            draw.text((10, 105), f"Updated: {last_update_time.strftime('%H:%M')}", font=font14, fill=0)
    
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
            
            # Draw simple graph (would need more sophisticated implementation)
            draw.text((10, 90), "6hr trend:", font=font14, fill=0)
            draw.line((10, 110, 120, 110), fill=0)  # x-axis
            
    # Add touch instruction at bottom
    draw.text((10, 110), "Tap to change view", font=font14, fill=0)
    
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
                # Check for touch input
                if check_touch(epd):
                    # If touch detected, update immediately
                    update_display(epd)
                else:
                    # Normal timed update
                    update_display(epd)
            time.sleep(10)  # Check for touch every 10 seconds

    except KeyboardInterrupt:
        print("Exiting...")
        epd2in13_V3.epdconfig.module_exit()

if __name__ == "__main__":
    main()
