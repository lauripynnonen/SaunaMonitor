import time
import threading
import asyncio
from database import setup_database, check_data_freshness, cleanup_old_data
from ruuvitag_interface import RuuviTagInterface
from display import Display
from data_analysis import get_estimated_time, get_status_message
from config import SLEEP_DURATION, UPDATE_INTERVAL

def main():
    setup_database()
    
    if not check_data_freshness():
        print("Downloading historical data from RuuviTag...")
        asyncio.run(download_historical_data())
        print("Historical data download complete.")

    cleanup_old_data()

    ruuvi = RuuviTagInterface()
    display = Display()

    threading.Thread(target=ruuvi.start_realtime_listener, daemon=True).start()

    display_sleep_until = 0
    last_update_time = 0
    last_cleanup = time.time()

    try:
        while True:
            current_time = time.time()

            if ruuvi.last_update_time:
                status, minutes, is_active = get_estimated_time()
                
                if is_active or current_time >= display_sleep_until:
                    if display.is_sleeping:
                        display.wake()
                    
                    if current_time - last_update_time >= UPDATE_INTERVAL:
                        current_temp = ruuvi.current_temp
                        current_humidity = ruuvi.current_humidity
                        status_title, status_message = get_status_message(current_temp, (status, minutes, is_active))
                        
                        display.update(current_temp, current_humidity, status_title, status_message)
                        last_update_time = current_time
                    
                    if not is_active:
                        display_sleep_until = current_time + SLEEP_DURATION
                else:
                    if not display.is_sleeping:
                        display.sleep()

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                cleanup_old_data()
                last_cleanup = current_time

            time.sleep(10)  # Check every 10 seconds

    except KeyboardInterrupt:    
        print("Ctrl + C pressed. Exiting...")
        display.cleanup()
        ruuvi.stop_listener()

if __name__ == '__main__':
    main()
