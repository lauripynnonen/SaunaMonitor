import math
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime, timedelta
import os

class Display:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.is_sleeping = False
        self.historical_data = []
        self.is_mock = not self._is_raspberry_pi()
        self.font = self.load_font()

        if not self.is_mock:
            import epaper
            self.epd = epaper.epaper('epd7in5_V2').EPD()
        else:
            print("Using mock display.")

    def _is_raspberry_pi(self):
        return os.name == 'posix' and os.uname().sysname == 'Linux' and os.uname().machine.startswith('arm')
    
    def load_font(self, size=24):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except IOError:
            try:
                return ImageFont.truetype("arial.ttf", size)
            except IOError:
                return ImageFont.load_default()

    def initialize(self):
        if not self.is_mock:
            self.epd.init()
            self.epd.Clear(0xFF)
        self.is_sleeping = False

    def sleep(self):
        if not self.is_mock and not self.is_sleeping:
            self.epd.sleep()
        self.is_sleeping = True

    def wake(self):
        if not self.is_mock and self.is_sleeping:
            self.epd.init()
        self.is_sleeping = False

    def update(self, current_temp, current_humidity, status_title, status_message):
        if self.is_sleeping:
            self.wake()

        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        self.draw_temperature_gauge(draw, current_temp, 200, 200, 180)
        self.draw_humidity_and_status(draw, current_humidity, status_title, status_message)

        if self.historical_data:
            graph = self.create_graph()
            image.paste(graph, (50, 400))
            self.draw_table(draw, self.historical_data[-8:])  # Display last 8 data points

        if self.is_mock:
            image.save('mock_display.png')
            print("Display image saved as 'mock_display.png'")
        else:
            self.epd.display(self.epd.getbuffer(image))

    def add_data_point(self, data_point):
        self.historical_data.append(data_point)
        # Keep only the last 2 hours of data
        two_hours_ago = datetime.now() - timedelta(hours=2)
        self.historical_data = [point for point in self.historical_data if datetime.strptime(point['time'], '%Y-%m-%d %H:%M:%S') > two_hours_ago]

    def create_graph(self):
        times = [datetime.strptime(item['time'], '%Y-%m-%d %H:%M:%S') for item in self.historical_data]
        temps = [item['temperature'] for item in self.historical_data]
        humidities = [item['humidity'] for item in self.historical_data]

        fig, ax1 = plt.subplots(figsize=(10, 4))
        ax2 = ax1.twinx()

        ax1.plot(times, temps, 'r-', linewidth=2, label='Temperature')
        ax2.plot(times, humidities, 'b--', linewidth=2, label='Humidity')

        ax1.set_xlabel('Time')
        ax1.set_ylabel('Temperature (°C)', color='r')
        ax2.set_ylabel('Humidity (%)', color='b')

        ax1.tick_params(axis='y', labelcolor='r')
        ax2.tick_params(axis='y', labelcolor='b')

        plt.title('Temperature and Humidity Over Time')
        
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        return Image.open(buf).convert('1')

    def draw_temperature_gauge(self, draw, value, x, y, radius):
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
        draw.text((x, y+radius-40), f"{value:.2f}°C", fill=0, anchor="mm", font=self.font)

    def draw_table(self, draw, data):
        start_x, start_y = 50, 400
        cell_width, cell_height = 150, 30
        header_font = self.load_font(16)
        font = self.load_font(14)

        headers = ["Time", "Temp (°C)", "Humidity (%)"]
        for i, header in enumerate(headers):
            draw.rectangle([start_x + i*cell_width, start_y, start_x + (i+1)*cell_width, start_y + cell_height], outline=0)
            draw.text((start_x + i*cell_width + 5, start_y + 5), header, font=header_font, fill=0)

        for row, measurement in enumerate(data):
            time = datetime.strptime(measurement['time'], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
            temp = f"{measurement['temperature']:.1f}" if measurement['temperature'] is not None else "N/A"
            humidity = f"{measurement['humidity']:.1f}" if measurement['humidity'] is not None else "N/A"
            row_data = [time, temp, humidity]
            for col, value in enumerate(row_data):
                draw.rectangle([start_x + col*cell_width, start_y + (row+1)*cell_height,
                                start_x + (col+1)*cell_width, start_y + (row+2)*cell_height], outline=0)
                draw.text((start_x + col*cell_width + 5, start_y + (row+1)*cell_height + 5),
                          value, font=font, fill=0)


    def draw_humidity_and_status(self, draw, humidity, status_title, status_message):
        title_font = self.load_font(24)
        value_font = self.load_font(48)

        draw.text((450, 100), "Humidity", font=title_font, fill=0)
        draw.text((450, 130), f"{humidity:.1f}%", font=value_font, fill=0)

        draw.text((450, 220), status_title, font=title_font, fill=0)
        draw.text((450, 250), status_message, font=value_font, fill=0)