# config.py

# RuuviTag settings
TEMPERATURE  = 0x30  # \x30 Temperature  [0,01°C]
HUMIDITY     = 0x31  # \x31 Humidity     [0,01%rH]
AIR_PRESSURE = 0x32  # \x32 Air pressure [1Pa]
ALL_SENSORS  = 0x3A  # \x3A All of the above
RUUVITAG_MAC = "C5:D5:BF:EA:9E:0D"

## Number of seconds to get log data
LOG_SECONDS = 7200  # 7200 = last 2 hours

DATATYPE_LOG = ALL_SENSORS

# Temperature settings
TARGET_TEMP = 65  # Target temperature for the sauna in °C
MIN_ACTIVE_TEMP = 30  # Minimum temperature to consider the sauna active in °C
TEMP_DROP_THRESHOLD = -5  # Temperature drop threshold in °C per hour

# Database settings
DB_NAME = "sauna_data.db"

# E-ink display settings
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# Update and sleep settings
SLEEP_DURATION = 50  # Sleep time in seconds when sauna is inactive
UPDATE_INTERVAL = 60  # Update interval in seconds when sauna is active

# Data management
DATA_RETENTION_DAYS = 10  # Number of days to keep historical data

# Bluetooth settings
BLE_SCAN_DURATION = 5  # Duration in seconds to scan for BLE devices

# Logging settings
LOG_LEVEL = "INFO"  # Logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FILE = "sauna_monitor.log"  # Name of the log file

# Mock data settings
USE_MOCK_DATA = False  # Set to False to use real RuuviTag data
