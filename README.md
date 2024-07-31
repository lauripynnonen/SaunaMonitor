# SaunaMonitor

This Python script implements the sauna monitor dashboard for your 7.5-inch E-Ink display.

We import necessary libraries, including PIL for image processing, matplotlib for graph creation, and the Waveshare EPD library for interfacing with the e-ink display.
Placeholder functions (get_current_temp(), get_current_humidity(), get_estimated_time(), and get_historical_data()) are included. You'll need to replace these with your actual data collection methods from your Ruuvi sensor.
The draw_temperature_gauge() function creates the circular temperature gauge.
create_graph() generates the temperature and humidity graph using matplotlib.
The main() function:

Initializes the e-ink display
Creates a new image
Draws the temperature gauge
Adds humidity and estimated time information
Creates and pastes the graph
Displays the final image on the e-ink display

To use this script:

Install required libraries:
Copypip install pillow matplotlib RPi.GPIO spidev

Install the Waveshare e-Paper library:
Copygit clone https://github.com/waveshare/e-Paper
cd e-Paper/RaspberryPi_JetsonNano/python
sudo python setup.py install

Replace the placeholder data collection functions with your actual methods to get data from the Ruuvi sensor.
Run the script:
Copypython sauna_monitor.py


This script will create the dashboard and display it on your e-ink screen. You may need to adjust font paths or sizes depending on your Raspberry Pi's configuration.
To make this update periodically:

You could run this script at regular intervals using a cron job.
Alternatively, you could modify the script to run in a loop, updating the display every few minutes.
