import math
import traceback
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import io
from datetime import datetime, timedelta
from data_analysis import get_current_time
import os

class Display:
    def __init__(self, width=800, height=480):  # Default values added
        try:
            print(f"Initializing Display with width={width}, height={height}")
            self.width = width
            self.height = height
            self.is_sleeping = False
            self.historical_data = []
            self.is_mock = not self._is_raspberry_pi()
            self.mock_display_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_display.png')
            self.font = self.load_font()
            self.graph_width = int(width * 0.95)  # 95% of display width
            self.graph_height = int(height * 0.40)  # 40% of display height

            if not self.is_mock:
                try:
                    import epaper # type: ignore
                    self.epd = epaper.epaper('epd7in5_V2').EPD()
                    print("Successfully initialized epaper display")
                except Exception as e:
                    print(f"Error initializing epaper display: {str(e)}")
                    self.is_mock = True
            
            if self.is_mock:
                print(f"Using mock display. Images will be saved to: {self.mock_display_path}")
        except Exception as e:
            print(f"Error in Display.init: {str(e)}")
            print("Traceback:")

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
        try:
            if self.is_sleeping:
                self.wake()

            image = Image.new('1', (self.width, self.height), 255)
            draw = ImageDraw.Draw(image)

            # Draw current time at the top
            current_time = get_current_time()
            draw.text((self.width // 2, 10), f"Current Time: {current_time.strftime('%H:%M')}", 
                    fill=0, anchor="mt", font=self.load_font(24))

            # Calculate new x-positions for gauges
            side_padding = 130  # Increased from 120
            temp_gauge_x = side_padding
            humidity_gauge_x = self.width - side_padding

            # Draw temperature gauge
            self.draw_gauge(draw, current_temp, temp_gauge_x, 140, 110, "Temperature", "°C", 0, 100)

            # Draw humidity gauge
            self.draw_gauge(draw, current_humidity, humidity_gauge_x, 140, 110, "Humidity", "%", 0, 100)

            # Draw status
            self.draw_status(draw, status_title, status_message)

            if self.historical_data:
                # Create and paste graph
                graph = self.create_graph()
                # Center the graph horizontally
                graph_x = (self.width - self.graph_width) // 2 + 95
                graph_y = 280  # Adjust this value if needed
                image.paste(graph, (graph_x, graph_y))

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
        except Exception as e:
            print(f"Error in Display.update: {str(e)}")
            print("Traceback:")
            traceback.print_exc()

    def add_data_point(self, data_point):
        self.historical_data.append(data_point)
        # Keep only the last 2 hours of data
        two_hours_ago = datetime.now() - timedelta(hours=2)
        self.historical_data = [point for point in self.historical_data if datetime.strptime(point['time'], '%Y-%m-%d %H:%M:%S') > two_hours_ago]

    def create_graph(self):
        # Increase the graph size by 25%
        self.graph_width = int(self.graph_width * 1.25)
        self.graph_height = int(self.graph_height * 1.25)

        # Calculate the size in inches
        dpi = 100  # Set this to match your e-paper display's DPI if known
        width_inches = self.graph_width / dpi
        height_inches = self.graph_height / dpi

        # Parse the full datetime
        datetimes = [datetime.strptime(item['time'], '%Y-%m-%d %H:%M:%S') for item in self.historical_data]
        temps = [item['temperature'] for item in self.historical_data]
        humidities = [item['humidity'] for item in self.historical_data]

        # Create figure with exact size
        fig, ax1 = plt.subplots(figsize=(width_inches, height_inches), dpi=dpi)
        ax2 = ax1.twinx()

        # Use a simple, clear font
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['font.size'] = 10  # Increased base font size

        # Plot data
        ax1.plot(datetimes, temps, 'k-', linewidth=1.5, label='Temperature')
        ax2.plot(datetimes, humidities, 'k--', linewidth=1.5, label='Humidity')

        # Set labels
        ax1.set_ylabel('Temp (°C)', fontsize=10)
        ax2.set_ylabel('Humidity (%)', fontsize=10)

        # Format x-axis
        ax1.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        fig.autofmt_xdate(rotation=45, ha='right')

        # Set y-axis limits
        temp_min, temp_max = min(temps), max(temps)
        hum_min, hum_max = min(humidities), max(humidities)
        temp_range = max(0.5, temp_max - temp_min)
        hum_range = max(2, hum_max - hum_min)
        ax1.set_ylim(temp_min - 0.1 * temp_range, temp_max + 0.1 * temp_range)
        ax2.set_ylim(hum_min - 0.1 * hum_range, hum_max + 0.1 * temp_range)

        # Set ticks
        ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))
        ax2.yaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=5))
        ax1.tick_params(axis='both', which='major', labelsize=10)
        ax2.tick_params(axis='both', which='major', labelsize=10)

        # Add legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

        # Adjust layout
        plt.tight_layout(pad=0.4, rect=[0.1, 0.1, 0.9, 0.9])

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)

        # Open as image and convert to 1-bit color without resizing
        graph_image = Image.open(buf).convert('1')
        return graph_image

    def draw_gauge(self, draw, value, x, y, radius, label, unit, min_value, max_value):
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
                num = min_value + i * (max_value - min_value) // 10
                num_x = x + int((radius - 25) * math.cos(angle))
                num_y = y + int((radius - 25) * math.sin(angle))
                draw.text((num_x, num_y), str(num), fill=0, font=self.load_font(12))

        # Draw label
        draw.text((x, y+radius+15), label, fill=0, anchor="mm", font=self.load_font(18))
        
        # Draw value with white stroke
        value_font = self.load_font(36)
        value_text = f"{int(value)}{unit}"
        
        # Position for the value text
        value_x = x
        value_y = y + radius - 80

        # Function to draw text with stroke
        def draw_text_with_stroke(draw, text, x, y, font, text_color, stroke_color, stroke_width):
            # Draw stroke
            for offset_x in range(-stroke_width, stroke_width+1):
                for offset_y in range(-stroke_width, stroke_width+1):
                    draw.text((x+offset_x, y+offset_y), text, font=font, fill=stroke_color, anchor="mm")
            # Draw text
            draw.text((x, y), text, font=font, fill=text_color, anchor="mm")

        # Draw value text with white stroke
        draw_text_with_stroke(draw, value_text, value_x, value_y, value_font, 0, 255, 2)

        # Draw needle
        angle = math.radians(-135 + ((value - min_value) / (max_value - min_value)) * 270)
        needle_x = x + int((radius - 15) * math.cos(angle))
        needle_y = y + int((radius - 15) * math.sin(angle))
        draw.line((x, y, needle_x, needle_y), fill=0, width=2)
        
        # Draw center circle
        draw.ellipse([x-3, y-3, x+3, y+3], fill=0)

    def draw_status(self, draw, status_title, status_message):
        title_font = self.load_font(28)
        message_font = self.load_font(24)
        
        # Calculate text sizes using textbbox
        title_bbox = title_font.getbbox(status_title)
        title_height = title_bbox[3] - title_bbox[1]
        
        # Calculate positions
        center_x = self.width // 2
        title_y = 110  # Moved up
        message_y = title_y + title_height + 15  # Reduced padding
        
        # Draw title
        draw.text((center_x, title_y), status_title, font=title_font, fill=0, anchor="mt")
        
        # Draw message (can be multi-line)
        lines = status_message.split('\n')
        for i, line in enumerate(lines):
            message_bbox = message_font.getbbox(line)
            message_height = message_bbox[3] - message_bbox[1]
            line_y = message_y + i * (message_height + 3)  # Reduced space between lines
            draw.text((center_x, line_y), line, font=message_font, fill=0, anchor="mt")

