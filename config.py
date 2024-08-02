# config.py
```python
# RuuviTag MAC address
RUUVITAG_MAC = "AA:BB:CC:DD:EE:FF"

# Target temperature
TARGET_TEMP = 65

# This should be a temperature higher than what the environment can create without the stove on
MIN_ACTIVE_TEMP = 40

# Temperature drop threshold (in °C per hour)
TEMP_DROP_THRESHOLD = -5

# Database name
DB_NAME = "sauna_data.db"

# E-ink display settings
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# E-paper display settings
SLEEP_DURATION = 50 # Sleep time in seconds
UPDATE_INTERVAL = 60  # Update interval in seconds
```
