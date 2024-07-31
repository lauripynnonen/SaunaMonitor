# Sauna Monitor

## Description
Sauna Monitor is a Raspberry Pi-based system that uses a RuuviTag sensor to monitor and display sauna conditions in real-time. It provides temperature and humidity tracking, estimates time to reach target temperature, and displays historical data on an e-ink display.

## Features
- Real-time temperature and humidity monitoring
- Historical data tracking and graphing
- Temperature trend analysis
- Estimated time to reach target temperature
- E-ink display for low power consumption and clear visibility
- Automatic data cleanup to manage storage efficiently

## Requirements
- Raspberry Pi (tested on Raspberry Pi Zero 2 WH)
- RuuviTag sensor
- 7.5-inch E-Paper E-Ink Display (Waveshare)
- Python 3.7+

## Dependencies
- ruuvitag_sensor
- bleak
- Pillow (PIL)
- matplotlib
- waveshare_epd

## Setup
1. Clone the repository:
   ```
   git clone https://github.com/lauripynnonen/sauna-monitor.git
   cd sauna-monitor
   ```

2. Install required Python packages:
   ```
   pip install ruuvitag_sensor bleak Pillow matplotlib
   ```

3. Install Waveshare e-Paper library:
   ```
   git clone https://github.com/waveshare/e-Paper.git
   cd e-Paper/RaspberryPi_JetsonNano/python
   sudo python setup.py install
   ```

4. Configure your RuuviTag:
   - Open `config.py` and set `RUUVITAG_MAC` to your RuuviTag's MAC address.

5. Adjust other settings in `config.py` as needed (e.g., `TARGET_TEMP`, `TEMP_DROP_THRESHOLD`).

## Usage
1. Connect the e-ink display to your Raspberry Pi following Waveshare's instructions.

2. Run the main script:
   ```
   python main.py
   ```

3. The system will start monitoring your sauna and updating the e-ink display every minute.

## File Structure
- `main.py`: Main script that runs the program
- `config.py`: Configuration variables and constants
- `database.py`: Database operations for storing and retrieving data
- `ruuvitag_interface.py`: RuuviTag data collection and processing
- `display.py`: E-ink display rendering and updates
- `data_analysis.py`: Temperature trend and time estimation functions

## Contributing
Contributions to the Sauna Monitor project are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- [RuuviTag](https://ruuvi.com/) for their excellent environmental sensors
- [Waveshare](https://www.waveshare.com/) for the e-Paper display module
- All contributors and users of this project

## Support
If you encounter any problems or have any questions, please open an issue on the GitHub repository.
