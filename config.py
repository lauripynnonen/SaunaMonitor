# config.py

# RuuviTag settings
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"

# Temperature settings
TARGET_TEMP = 65  # Target temperature for the sauna in °C
MIN_ACTIVE_TEMP = 40  # Minimum temperature to consider the sauna active in °C
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
