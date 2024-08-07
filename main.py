import asyncio
import time
import pandas as pd
from database import setup_database, check_data_freshness, cleanup_old_data, get_historical_data
from ruuvitag_interface import RuuviTagInterface
from display import Display
from data_analysis import get_estimated_time, get_status_message
from config import SLEEP_DURATION, UPDATE_INTERVAL, DISPLAY_WIDTH, DISPLAY_HEIGHT

async def main():
    print("Initializing SaunaMonitor...")
    try:
        setup_database()
        print("Database setup complete.")
    except Exception as e:
        print(f"Error setting up database: {e}")
        return

    ruuvi = RuuviTagInterface()
    
    print("Attempting to download historical data from RuuviTag...")
    try:
        await ruuvi.download_historical_data()
        print("Historical data download attempt completed.")
    except Exception as e:
        print(f"Error during historical data download attempt: {e}")
        print("Continuing with real-time data only.")

    if check_data_freshness():
        print("Data is fresh.")
    else:
        print("Data is not fresh. Consider investigating if historical data was successfully downloaded.")

    try:
        cleanup_old_data()
        print("Old data cleanup complete.")
    except Exception as e:
        print(f"Error during old data cleanup: {e}")

    try:
        display = Display(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        display.initialize()
        print("Display initialized successfully.")

        # Update display with historical data from database
        historical_data = get_historical_data(hours=2)  # Get last 2 hours of data
        print(f"Retrieved {len(historical_data)} historical data points from database:")
        for data_point in historical_data:
            print(f"Time: {data_point['time']}, Temp: {data_point['temperature']}, Humidity: {data_point['humidity']}")
            display.add_data_point(data_point)

        if historical_data:
            latest_data = historical_data[-1]  # Use the most recent data point
            current_temp = latest_data['temperature']
            current_humidity = latest_data['humidity']
            status, minutes, expected_ready_time, is_active = get_estimated_time()  # Unpack 4 values
            status_title, status_message = get_status_message(current_temp, (status, minutes, expected_ready_time, is_active))
            display.update(current_temp, current_humidity, status_title, status_message)
            print("Display updated with historical data.")
        else:
            print("No historical data available for initial display update.")
    except Exception as e:
        print(f"Error initializing or updating display: {e}")
        print("Continuing without display updates.")
        display = None

    print("Starting real-time listener...")
    listener_task = asyncio.create_task(ruuvi.start_realtime_listener())

    display_sleep_until = 0
    last_update_time = 0
    last_cleanup = time.time()

    print("Entering main loop...")
    try:
        while True:
            current_time = time.time()

            current_temp = ruuvi.get_current_temp()
            current_humidity = ruuvi.get_current_humidity()

            if current_temp is not None and current_humidity is not None:
                print(f"Current readings - Temperature: {current_temp:.2f}°C, Humidity: {current_humidity:.2f}%")
                
                if display:
                    status, minutes, expected_ready_time, is_active = get_estimated_time()  # Now unpacking 4 values
                    
                    if is_active or current_time >= display_sleep_until:
                        if display.is_sleeping:
                            display.wake()
                        
                        if current_time - last_update_time >= UPDATE_INTERVAL:
                            status_title, status_message = get_status_message(current_temp, (status, minutes, expected_ready_time, is_active))  # Passing 4 values
                            
                            print(f"Updating display - Status: {status_title}, Message: {status_message}")
                            display.update(current_temp, current_humidity, status_title, status_message)
                            last_update_time = current_time
                        
                        if not is_active:
                            display_sleep_until = current_time + SLEEP_DURATION
                            print(f"Sauna inactive. Display will sleep until: {time.ctime(display_sleep_until)}")
                    elif not display.is_sleeping:
                        display.sleep()
                        print("Display put to sleep.")

            # Cleanup old data once a day
            if current_time - last_cleanup >= 86400:  # 86400 seconds = 1 day
                print("Performing daily data cleanup...")
                cleanup_old_data()
                last_cleanup = current_time
                print("Daily data cleanup complete.")

            await asyncio.sleep(10)  # Check every 10 seconds
            print("Waiting for next update cycle...")

    except asyncio.CancelledError:
        print("Main loop cancelled. Cleaning up...")
    finally:
        print("Stopping listener and exiting...")
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Exiting gracefully.")
