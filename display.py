```python
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from waveshare_epd import epd7in5_V2
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT
from ruuvitag_interface import get_current_temp, get_current_humidity
from data_analysis import get_estimated_time, get_status_message

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
