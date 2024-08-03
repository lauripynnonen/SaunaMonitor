import time
import asyncio
from database import setup_database, check_data_freshness, cleanup_old_data
from ruuvitag_interface import RuuviTagInterface
from display import Display
from data_analysis import get_estimated_time, get_status_message
from config import SLEEP_DURATION, UPDATE_INTERVAL

def main():
    print("Initializing SaunaMonitor...")
    setup_database()
    print("Database setup complete.")
    
    ruuvi = RuuviTagInterface()
    
    if not check_data_freshness():
        print("Attempting to download historical data from RuuviTag...")
        try:
            asyncio.run(ruuvi.download_historical_data())
            print("Historical data download complete.")
        except Exception as e:
            print(f"Error downloading historical data: {e}")
            print("Continuing with real-time data only.")

    cleanup_old_data()
    print("Old data cleanup complete.")

    try:
        display = Display()
        display.initialize()
        print("Display initialized successfully.")
    except Exception as e:
        print(f"Error initializing display: {e}")
        print("Continuing without display updates.")
        display = None

    ruuvi.start_realtime_listener()

    display_sleep_until = 0
    last_update_time = 0
    last_cleanup = time.time()

    print("Entering main loop...")
    try:
        while True:
            current_time = time.time()

            try:
                current_temp = ruuvi.get_current_temp()
                current_humidity = ruuvi.get_current_humidity()
                print(f"Current readings - Temperature: {current_temp:.2f}°C, Humidity: {current_humidity:.2f}%")
            except Exception as e:
                print(f"Error getting RuuviTag data: {e}")
                current_temp = 0
                current_humidity = 0

            if current_temp != 0 and current_humidity != 0:  # Assuming 0 means no data
                status, minutes, is_active = get_estimated_time()
                print(f"Sauna status: {status}, Estimated time: {minutes} minutes, Active: {is_active}")
                
                if display and (is_active or current_time >= display_sleep_until):
                    if display.is_sleeping:
                        display.wake()
                        print("Display woken up.")
                    
                    if current_time - last_update_time >= UPDATE_INTERVAL:
                        status_title, status_message = get_status_message(current_temp, (status, minutes, is_active))
                        
                        print(f"Updating display - Status: {status_title}, Message: {status_message}")
                        display.update(current_temp, current_humidity, status_title, status_message)
                        last_update_time = current_time
                    
                    if not is_active:
                        display_sleep_until = current_time + SLEEP_DURATION
                        print(f"Sauna inactive. Display will sleep until: {time.ctime(display_sleep_until)}")
                elif display and not display.is_sleeping:
                    display.sleep()
                    print("Display put to sleep.")

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                print("Performing daily data cleanup...")
                cleanup_old_data()
                last_cleanup = current_time
                print("Daily data cleanup complete.")

            time.sleep(10)  # Check every 10 seconds
            print("Waiting for next update cycle...")

    except KeyboardInterrupt:    
        print("Ctrl + C pressed. Stopping listener and exiting...")
        ruuvi.stop_listener()

if __name__ == '__main__':
    main()