import time
import matplotlib.pyplot as plt
from ruuvitag_sensor.ruuvi import RuuviTagSensor
from waveshare_epd import epd7in5_V2
import numpy as np

# Constants
SENSOR_MAC = "XX:XX:XX:XX:XX:XX"  # Replace with your Ruuvi tag's MAC address
DESIRED_TEMP = 65
SAMPLE_INTERVAL = 300  # 5 minutes in seconds
DATA_POINTS = 24  # 2 hours worth of data (24 * 5 minutes)

class SaunaMonitor:
    def __init__(self):
        self.temperatures = []
        self.humidities = []
        self.timestamps = []
        self.epd = epd7in5_V2.EPD()
        self.epd.init()

    def collect_data(self):
        data = RuuviTagSensor.get_data_for_sensors([SENSOR_MAC], 1)
        temp = data[SENSOR_MAC]['temperature']
        humidity = data[SENSOR_MAC]['humidity']
        self.temperatures.append(temp)
        self.humidities.append(humidity)
        self.timestamps.append(time.time())
        
        # Keep only the last 2 hours of data
        if len(self.temperatures) > DATA_POINTS:
            self.temperatures = self.temperatures[-DATA_POINTS:]
            self.humidities = self.humidities[-DATA_POINTS:]
            self.timestamps = self.timestamps[-DATA_POINTS:]

    def estimate_time_to_target(self):
        if len(self.temperatures) < 2:
            return "Insufficient data"
        
        # Find when temperature started rising
        start_index = 0
        for i in range(1, len(self.temperatures)):
            if self.temperatures[i] - self.temperatures[i-1] > 1:  # 1 degree threshold
                start_index = i
                break
        
        if start_index == 0:
            return "Heating not detected"
        
        # Calculate rate of temperature increase
        time_diff = self.timestamps[-1] - self.timestamps[start_index]
        temp_diff = self.temperatures[-1] - self.temperatures[start_index]
        rate = temp_diff / time_diff
        
        if rate <= 0:
            return "Unable to estimate"
        
        time_to_target = (DESIRED_TEMP - self.temperatures[-1]) / rate
        return f"{int(time_to_target / 60)} minutes"

    def create_graph(self):
        plt.figure(figsize=(10, 5))
        plt.plot(self.timestamps, self.temperatures, label='Temperature')
        plt.plot(self.timestamps, self.humidities, label='Humidity')
        plt.xlabel('Time')
        plt.ylabel('Value')
        plt.title('Temperature and Humidity over Time')
        plt.legend()
        plt.savefig('graph.png')
        plt.close()

    def update_display(self):
        self.create_graph()
        image = Image.new('1', (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(image)
        
        # Add current temperature and humidity
        draw.text((10, 10), f"Temp: {self.temperatures[-1]:.1f}°C", fill=0)
        draw.text((10, 40), f"Humidity: {self.humidities[-1]:.1f}%", fill=0)
        
        # Add time estimate
        estimate = self.estimate_time_to_target()
        draw.text((10, 70), f"Est. time to {DESIRED_TEMP}°C: {estimate}", fill=0)
        
        # Add graph
        graph = Image.open('graph.png').convert('1')
        image.paste(graph, (10, 100))
        
        self.epd.display(self.epd.getbuffer(image))

    def run(self):
        try:
            while True:
                self.collect_data()
                self.update_display()
                time.sleep(SAMPLE_INTERVAL)
        except KeyboardInterrupt:
            print("Cleaning up...")
            self.epd.sleep()

if __name__ == "__main__":
    monitor = SaunaMonitor()
    monitor.run()
