# Initial master file, now split into multiple smaller files for easier updates

import time
import math
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from waveshare_epd import epd7in5_V2
from ruuvitag_sensor.ruuvi import RuuviTagSensor
import threading
import asyncio
import struct
from bleak import BleakClient

# Replace with your RuuviTag's MAC address
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"

# Set the target temperature here
TARGET_TEMP = 60

# Temperature drop threshold (in °C per hour)
TEMP_DROP_THRESHOLD = -5

# Database setup
DB_NAME = "sauna_data.db"

# Global variables for current data
current_temp = 0
current_humidity = 0
last_update_time = None
last_data_store_time = None

# Constants for RuuviTag communication
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
DATATYPE_LOG = 0x3A  # ALL_SENSORS
LOG_SECONDS = 7200  # 2 hours of historical data

def setup_database():
    """
    Initialize the SQLite database and create the measurements table if it doesn't exist.
    This function is called at the start of the program to ensure the database is ready for use.
    """
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS measurements
                     (timestamp TEXT PRIMARY KEY, temperature REAL, humidity REAL)''')
        conn.commit()
        conn.close()

def store_measurement(timestamp, temperature, humidity):
    """
    Store a single measurement in the database.
    
    Args:
    timestamp (str): The time of the measurement in 'YYYY-MM-DD HH:MM:SS' format.
    temperature (float): The temperature reading.
    humidity (float): The humidity reading.
    """
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO measurements VALUES (?, ?, ?)",
                  (timestamp, temperature, humidity))
        conn.commit()
        conn.close()

def get_historical_data(hours=2):
    """
    Retrieve historical data from the database for the specified number of hours.
    
    Args:
    hours (int): The number of hours of historical data to retrieve (default is 2).
    
    Returns:
    list: A list of dictionaries containing timestamp, temperature, and humidity data.
    """
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT * FROM measurements WHERE timestamp > ? ORDER BY timestamp DESC", (time_threshold,))
        data = c.fetchall()
        conn.close()
    return [{"time": row[0], "temperature": row[1], "humidity": row[2]} for row in data]

def check_data_freshness():
    """
    Check if the most recent data in the database is fresh (not older than 2 hours).
    
    Returns:
    bool: True if the data is fresh, False otherwise.
    """
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT MAX(timestamp) FROM measurements")
        latest_timestamp = c.fetchone()[0]
        conn.close()

    if latest_timestamp:
        latest_time = datetime.strptime(latest_timestamp, '%Y-%m-%d %H:%M:%S')
        time_difference = datetime.now() - latest_time
        return time_difference <= timedelta(hours=2)
    return False

def cleanup_old_data(days=10):
    """
    Remove data older than the specified number of days from the database.
    
    Args:
    days (int): The number of days to keep data for (default is 10).
    """
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("DELETE FROM measurements WHERE timestamp < ?", (threshold,))
        conn.commit()
        conn.close()

def handle_data(found_data):
    """
    Process data received from the RuuviTag.
    This function is called every time new data is received from the tag.
    It updates the current temperature and humidity, and stores the data
    in the database every minute.
    
    Args:
    found_data (dict): Dictionary containing data from the RuuviTag.
    """
    global current_temp, current_humidity, last_update_time, last_data_store_time
    if RUUVITAG_MAC in found_data:
        data = found_data[RUUVITAG_MAC]
        current_temp = data['temperature']
        current_humidity = data['humidity']
        current_time = datetime.now()

        # Store data every minute
        if last_data_store_time is None or (current_time - last_data_store_time).total_seconds() >= 60:
            store_measurement(current_time.strftime('%Y-%m-%d %H:%M:%S'), current_temp, current_humidity)
            last_data_store_time = current_time

        last_update_time = current_time

def start_realtime_listener():
    """
    Start the real-time listener for RuuviTag data.
    This function initiates the continuous listening process for data
    broadcasts from the RuuviTag.
    """
    RuuviTagSensor.get_datas(handle_data, [RUUVITAG_MAC])

async def download_historical_data():
    """
    Download historical data from the RuuviTag using Bluetooth Low Energy.
    This function connects to the RuuviTag, requests historical data,
    and stores it in the database.
    """
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

    async with BleakClient(RUUVITAG_MAC) as client:
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

def get_current_data():
    """
    Retrieve the most recent data from the RuuviTag.
    
    Returns:
    dict: A dictionary containing the current sensor data, or None if no data is available.
    """
    data = RuuviTagSensor.get_data_for_sensors([RUUVITAG_MAC], 5)
    if RUUVITAG_MAC in data:
        return data[RUUVITAG_MAC]
    return None

def get_current_temp():
    """
    Get the current temperature from the most recent RuuviTag data.
    
    Returns:
    float: The current temperature, or 0 if no data is available.
    """
    data = get_current_data()
    return data['temperature'] if data else 0

def get_current_humidity():
    """
    Get the current humidity from the most recent RuuviTag data.
    
    Returns:
    float: The current humidity, or 0 if no data is available.
    """
    data = get_current_data()
    return data['humidity'] if data else 0

def get_temperature_trend(hours=0.5):
    """
    Calculate the temperature trend over the specified time period.
    
    Args:
    hours (float): The number of hours to consider for the trend calculation (default is 0.5 hours).
    
    Returns:
    float: The temperature change rate in °C per hour.
    """
    historical_data = get_historical_data(hours=hours)
    if len(historical_data) < 2:
        return 0
    
    temp_data = [(datetime.strptime(d['time'], '%Y-%m-%d %H:%M:%S'), d['temperature']) for d in historical_data]
    temp_data.sort()
    
    time_diff = (temp_data[-1][0] - temp_data[0][0]).total_seconds() / 3600  # in hours
    temp_diff = temp_data[-1][1] - temp_data[0][1]
    
    if time_diff == 0:
        return 0
    
    return temp_diff / time_diff  # °C per hour

def get_estimated_time():
    """
    Estimate the time remaining to reach the target temperature.
    
    Returns:
    tuple: A tuple containing the status (str) and estimated time in minutes (int or None).
    """
    historical_data = get_historical_data(hours=2)  # Use last 2 hours of data
    if len(historical_data) < 2:
        return "Insufficient data", None
    
    # Convert data to list of tuples (timestamp, temperature)
    temp_data = [(datetime.strptime(d['time'], '%Y-%m-%d %H:%M:%S'), d['temperature']) for d in historical_data]
    temp_data.sort()  # Ensure data is in chronological order
    
    # Find when temperature started rising significantly
    start_index = 0
    for i in range(1, len(temp_data)):
        if temp_data[i][1] - temp_data[i-1][1] > 1:  # 1°C threshold for significant rise
            start_index = i
            break
    
    if start_index == 0:
        return "Not heating", None
    
    # Use data from the point where temperature started rising
    rising_temp_data = temp_data[start_index:]
    
    if len(rising_temp_data) < 2:
        return "Heating just started", None
    
    # Calculate rate of temperature increase using the most recent 15 minutes of data
    recent_data = [d for d in rising_temp_data if d[0] >= rising_temp_data[-1][0] - timedelta(minutes=15)]
    
    if len(recent_data) < 2:
        recent_data = rising_temp_data[-2:]  # Use at least two points
    
    time_diff = (recent_data[-1][0] - recent_data[0][0]).total_seconds() / 3600  # in hours
    temp_diff = recent_data[-1][1] - recent_data[0][1]
    
    if time_diff == 0 or temp_diff <= 0:
        return "Temperature stable", None
    
    rate = temp_diff / time_diff  # °C per hour
    
    time_to_target = (TARGET_TEMP - recent_data[-1][1]) / rate
    
    if time_to_target <= 0:
        return "Ready", None
    
    minutes_to_target = int(time_to_target * 60)
    return f"{minutes_to_target} min", minutes_to_target

def get_status_message(current_temp, estimate):
    """
    Generate a status message based on the current temperature and time estimate.
    
    Args:
    current_temp (float): The current temperature.
    estimate (tuple): The output from get_estimated_time().
    
    Returns:
    tuple: A tuple containing the status title (str) and status message (str).
    """
    status, minutes = estimate
    temp_trend = get_temperature_trend()
    
    if temp_trend < TEMP_DROP_THRESHOLD:
        return "Temperature dropping", "Add wood to stove"
    
    if status == "Not heating":
        return "Sauna is cold", "Turn on to heat"
    elif status == "Heating just started":
        return "Heating up", "Estimating time..."
    elif status == "Insufficient data" or status == "Temperature stable":
        return "Status unclear", "Check back soon"
    elif status == "Ready":
        if current_temp >= TARGET_TEMP:
            return "Sauna is ready!", "Enjoy your sauna"
        else:
            return "Temp maintaining", "Add wood if needed"
    elif minutes is not None:
        if minutes > 60:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes // 60}h {minutes % 60}min"
        else:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes} min"
    else:
        return "Status unknown", "Check sauna"


def draw_temperature_gauge(draw, value, x, y, radius):
    """
    Draw a circular temperature gauge on the given drawing context.
    
    Args:
    draw (PIL.ImageDraw.Draw): The drawing context.
    value (float): The temperature value to display.
    x (int): The x-coordinate of the gauge center.
    y (int): The y-coordinate of the gauge center.
    radius (int): The radius of the gauge.
    """
    # Draw outer circle
    draw.ellipse([x-radius, y-radius, x+radius, y+radius], outline=0)
    
    # Draw tick marks and numbers
    for i in range(11):
        angle = math.radians(-135 + i * 27)
        x1 = x + int((radius - 10) * math.cos(angle))
        y1 = y + int((radius - 10) * math.sin(angle))
        x2 = x + int(radius * math.cos(angle))
        y2 = y + int(radius * math.sin(angle))
        draw.line((x1, y1, x2, y2), fill=0)
        
        if i % 2 == 0:
            num = i * 10
            num_x = x + int((radius - 30) * math.cos(angle))
            num_y = y + int((radius - 30) * math.sin(angle))
            draw.text((num_x, num_y), str(num), fill=0)

    # Draw needle
    angle = math.radians(-135 + (value / 100) * 270)
    needle_x = x + int((radius - 20) * math.cos(angle))
    needle_y = y + int((radius - 20) * math.sin(angle))
    draw.line((x, y, needle_x, needle_y), fill=0, width=3)
    
    # Draw center circle
    draw.ellipse([x-5, y-5, x+5, y+5], fill=0)
    
    # Draw value
    draw.text((x, y+radius-40), f"{value:.2f}°C", fill=0, anchor="mm", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36))

def create_graph(data):
     """
    Create a graph of temperature and humidity data.
    
    Args:
    data (list): A list of dictionaries containing historical temperature and humidity data.
    
    Returns:
    PIL.Image: An image of the created graph.
    """
    times = [item["time"] for item in data]
    temps = [item["temperature"] for item in data]
    humidities = [item["humidity"] for item in data]

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()

    ax1.plot(times, temps, 'k-', linewidth=2)
    ax2.plot(times, humidities, 'k--', linewidth=2)

    ax1.set_xlabel('Time')
    ax1.set_ylabel('Temperature (°C)')
    ax2.set_ylabel('Humidity (%)')

    ax1.tick_params(axis='y')
    ax2.tick_params(axis='y')

    plt.title('Temperature and Humidity Over Time')
    plt.legend(['Temperature (solid)', 'Humidity (dashed)'])

    plt.tight_layout()
    plt.savefig('graph.png', dpi=100, bbox_inches='tight')
    plt.close()

    return Image.open('graph.png').convert('L')

def draw_table(draw, data):
    """
    Draw a table of recent measurements on the given drawing context.
    
    Args:
    draw (PIL.ImageDraw.Draw): The drawing context.
    data (list): A list of dictionaries containing recent measurement data.
    """
    start_x, start_y = 50, 400
    cell_width, cell_height = 150, 30
    header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)

    headers = ["Time", "Temp (°C)", "Humidity (%)"]
    for i, header in enumerate(headers):
        draw.rectangle([start_x + i*cell_width, start_y, start_x + (i+1)*cell_width, start_y + cell_height], outline=0)
        draw.text((start_x + i*cell_width + 5, start_y + 5), header, font=header_font, fill=0)

    for row, measurement in enumerate(data[:8]):  # Display last 8 measurements
        time = datetime.strptime(measurement['time'], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        temp = f"{measurement['temperature']:.1f}"
        humidity = f"{measurement['humidity']:.1f}"
        row_data = [time, temp, humidity]
        for col, value in enumerate(row_data):
            draw.rectangle([start_x + col*cell_width, start_y + (row+1)*cell_height,
                            start_x + (col+1)*cell_width, start_y + (row+2)*cell_height], outline=0)
            draw.text((start_x + col*cell_width + 5, start_y + (row+1)*cell_height + 5),
                      value, font=font, fill=0)

def update_display(epd):
    """
    Update the e-ink display with the latest sauna information.
    
    Args:
    epd (waveshare_epd.epd7in5_V2.EPD): The e-ink display object.
    """
    global current_temp, current_humidity, last_update_time
    
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    estimate = get_estimated_time()
    status_title, status_message = get_status_message(current_temp, estimate)

    # Draw temperature gauge
    draw_temperature_gauge(draw, current_temp, 200, 200, 180)

    # Draw humidity and status message
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    value_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    
    draw.text((450, 100), "Humidity", font=title_font, fill=0)
    draw.text((450, 130), f"{current_humidity:.1f}%", font=value_font, fill=0)

    draw.text((450, 220), status_title, font=title_font, fill=0)
    draw.text((450, 250), status_message, font=value_font, fill=0)

    # Create and paste graph
    historical_data = get_historical_data(hours=2)
    graph = create_graph(historical_data)
    image.paste(graph, (50, 400))

    # Draw table
    draw_table(draw, historical_data)

    epd.display(epd.getbuffer(image))

def main():
    """
    Main function to run the Sauna Monitor program.
    This function initializes the database, checks data freshness,
    starts the real-time listener, and enters the main loop for
    updating the display and managing data.
    """
    setup_database()
    
    if not check_data_freshness():
        print("Downloading historical data from RuuviTag...")
        asyncio.run(download_historical_data())
        print("Historical data download complete.")

    cleanup_old_data()

    threading.Thread(target=start_realtime_listener, daemon=True).start()

    try:
        epd = epd7in5_V2.EPD()
        epd.init()

        last_display_update = datetime.now()
        last_cleanup = datetime.now()

        while True:
            current_time = datetime.now()

            # Update display every 1 minute
            if (current_time - last_display_update).total_seconds() >= 60:
                update_display(epd)
                last_display_update = current_time

            # Cleanup old data once a day
            if (current_time - last_cleanup).days >= 1:
                cleanup_old_data()
                last_cleanup = current_time

            time.sleep(1)  # Check every second for more responsive updates

    except IOError as e:
        print(e)

    except KeyboardInterrupt:    
        print("ctrl + c:")
        epd7in5_V2.epdconfig.module_exit()
        exit()

if __name__ == '__main__':
    main()
