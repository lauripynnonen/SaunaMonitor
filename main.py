```python
import time
import threading
import asyncio
from database import setup_database, check_data_freshness, cleanup_old_data
from ruuvitag_interface import start_realtime_listener, download_historical_data
from display import update_display
from waveshare_epd import epd7in5_V2

def main():
    setup_database()
    
    if not check_data_freshness():
        print("Downloading historical data from RuuviTag...")
        asyncio.run(download_historical_data())
        print("Historical data download complete.")

    cleanup_old_data()

    threading.Thread(target=start_realtime_listener, daemon=True).start()

    try:
        epd = epd7in5_V2.EPD()
        epd.init()

        last_display_update = time.time()
        last_cleanup = time.time()

        while True:
            current_time = time.time()

            # Update display every 1 minute
            if current_time - last_display_update >= 60:
                update_display(epd)
                last_display_update = current_time

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                cleanup_old_data()
                last_cleanup = current_time

            time.sleep(1)  # Check every second for more responsive updates

    except KeyboardInterrupt:    
        print("Ctrl + C pressed. Exiting...")
        epd7in5_V2.epdconfig.module_exit()

if __name__ == '__main__':
    main()
```
