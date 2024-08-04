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
        self.mock_display_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_display.png')
        self.font = self.load_font()
        self.graph_width = int(width * 0.95)  # 95% of display width
        self.graph_height = int(height * 0.5)  # 50% of display height

        if not self.is_mock:
            import epaper # type: ignore
            self.epd = epaper.epaper('epd7in5_V2').EPD()
        else:
            print(f"Using mock display. Images will be saved to: {self.mock_display_path}")

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

        # Draw temperature gauge
        self.draw_temperature_gauge(draw, current_temp, 120, 120, 110)

        # Draw humidity and status
        self.draw_humidity_and_status(draw, current_humidity, status_title, status_message)

        if self.historical_data:
            # Create and paste graph
            graph = self.create_graph()
            image.paste(graph, (int(self.width * 0.025), 240))  # 2.5% margin on left

        if self.is_mock:
            try:
                image.save(self.mock_display_path)
                print(f"Display image saved as '{self.mock_display_path}'")
            except Exception as e:
                print(f"Error saving mock display image: {e}")
                print(f"Current working directory: {os.getcwd()}")
                print(f"File path used: {self.mock_display_path}")
        else:
            self.epd.display(self.epd.getbuffer(image))

    def add_data_point(self, data_point):
        self.historical_data.append(data_point)
        # Keep only the last 2 hours of data
        two_hours_ago = datetime.now() - timedelta(hours=2)
        self.historical_data = [point for point in self.historical_data if datetime.strptime(point['time'], '%Y-%m-%d %H:%M:%S') > two_hours_ago]

    def create_graph(self):
        # Parse the full datetime
        datetimes = [datetime.strptime(item['time'], '%Y-%m-%d %H:%M:%S') for item in self.historical_data]
        
        # Convert times to numerical values (minutes since midnight)
        times = [(dt.hour * 60 + dt.minute) for dt in datetimes]
        
        temps = [item['temperature'] for item in self.historical_data]
        humidities = [item['humidity'] for item in self.historical_data]

        # Create figure with size in inches
        fig, ax1 = plt.subplots(figsize=(self.graph_width / 100, self.graph_height / 100))
        ax2 = ax1.twinx()

        ax1.plot(times, temps, 'k-', linewidth=1, label='Temperature')
        ax2.plot(times, humidities, 'k--', linewidth=1, label='Humidity')

        ax1.set_xlabel('Time', fontsize=8)
        ax1.set_ylabel('Temperature (°C)', fontsize=8)
        ax2.set_ylabel('Humidity (%)', fontsize=8)

        # Format x-axis to show time
        def format_time(x, pos):
            hours, minutes = divmod(int(x), 60)
            return f'{hours:02d}:{minutes:02d}'
        
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(format_time))
        
        # Rotate and align the tick labels so they look better
        fig.autofmt_xdate(rotation=45, ha='right')

        # Set y-axis limits dynamically
        temp_min, temp_max = min(temps), max(temps)
        hum_min, hum_max = min(humidities), max(humidities)
        
        temp_range = max(0.5, temp_max - temp_min)  # Ensure a minimum range
        hum_range = max(2, hum_max - hum_min)  # Ensure a minimum range
        
        ax1.set_ylim(temp_min - 0.1 * temp_range, temp_max + 0.1 * temp_range)
        ax2.set_ylim(hum_min - 0.1 * hum_range, hum_max + 0.1 * hum_range)

        # Set integer ticks for both y-axes
        ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))
        ax2.yaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))

        ax1.tick_params(axis='both', which='major', labelsize=6)
        ax2.tick_params(axis='both', which='major', labelsize=6)

        plt.title('Temperature and Humidity Over Time', fontsize=10)
        
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=6)

        # Adjust layout with reduced bottom margin
        plt.tight_layout(pad=0.4, rect=[0, 0.03, 1, 0.95])
        
        # Fine-tune the subplot adjust
        fig.subplots_adjust(bottom=0.2)  # Increased bottom margin to accommodate rotated labels

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)

        graph_image = Image.open(buf).convert('1')
        return graph_image.resize((self.graph_width, self.graph_height), Image.LANCZOS)

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
                num_x = x + int((radius - 25) * math.cos(angle))
                num_y = y + int((radius - 25) * math.sin(angle))
                draw.text((num_x, num_y), str(num), fill=0, font=self.load_font(12))

        # Draw needle
        angle = math.radians(-135 + (value / 100) * 270)
        needle_x = x + int((radius - 15) * math.cos(angle))
        needle_y = y + int((radius - 15) * math.sin(angle))
        draw.line((x, y, needle_x, needle_y), fill=0, width=2)
        
        # Draw center circle
        draw.ellipse([x-3, y-3, x+3, y+3], fill=0)
        
        # Draw value
        draw.text((x, y+radius-60), f"{int(value)}°C", fill=0, anchor="mm", font=self.load_font(28))


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
        draw.text((300, 50), "Humidity", font=self.load_font(18), fill=0)
        draw.text((300, 75), f"{int(humidity)}%", font=self.load_font(36), fill=0)

        draw.text((300, 130), status_title, font=self.load_font(18), fill=0)
        draw.text((300, 155), status_message, font=self.load_font(24), fill=0)