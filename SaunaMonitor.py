import time
import math
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from waveshare_epd import epd7in5_V2
from ruuvitag_sensor.ruuvi import RuuviTagSensor

# Replace with your RuuviTag's MAC address
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"

# Set the target temperature here
TARGET_TEMP = 65

# Database setup
DB_NAME = "sauna_data.db"

# ... [Keep the existing setup_database, store_measurement, and get_historical_data functions] ...

def get_current_data():
    data = RuuviTagSensor.get_data_for_sensors([RUUVITAG_MAC], 5)
    if RUUVITAG_MAC in data:
        return data[RUUVITAG_MAC]
    return None

def get_current_temp():
    data = get_current_data()
    return data['temperature'] if data else 0

def get_current_humidity():
    data = get_current_data()
    return data['humidity'] if data else 0

def get_estimated_time():
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
    status, minutes = estimate
    if status == "Not heating":
        return "Sauna is cold", "Turn on to heat"
    elif status == "Heating just started":
        return "Heating up", "Estimating time..."
    elif status == "Insufficient data" or status == "Temperature stable":
        return "Status unclear", "Check back soon"
    elif status == "Ready":
        return "Sauna is ready!", "Enjoy your sauna"
    elif minutes is not None:
        if minutes > 60:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes // 60}h {minutes % 60}min"
        else:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes} min"
    else:
        return "Status unknown", "Check sauna"


def draw_temperature_gauge(draw, value, x, y, radius):
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

def main():
    setup_database()
    
    try:
        epd = epd7in5_V2.EPD()
        epd.init()

        while True:
            current_data = get_current_data()
            if current_data:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                store_measurement(timestamp, current_data['temperature'], current_data['humidity'])

            image = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
            draw = ImageDraw.Draw(image)

            current_temp = get_current_temp()
            current_humidity = get_current_humidity()
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
            
            # Wait for 5 minutes before the next update
            time.sleep(300)

    except IOError as e:
        print(e)

    except KeyboardInterrupt:    
        print("ctrl + c:")
        epd7in5_V2.epdconfig.module_exit()
        exit()

if __name__ == '__main__':
    main()
