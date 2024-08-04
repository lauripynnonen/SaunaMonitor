import sqlite3
from datetime import datetime, timedelta
import threading
import pandas as pd
import numpy as np
from contextlib import contextmanager

from config import DB_NAME

db_lock = threading.Lock()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    try:
        yield conn
    finally:
        conn.close()

def setup_database():
    """
    Initialize the SQLite database and create the measurements table if it doesn't exist.
    This function is called at the start of the program to ensure the database is ready for use.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS measurements
                     (timestamp TEXT PRIMARY KEY, temperature REAL, humidity REAL)''')
        conn.commit()
    print("Database setup complete.")
    check_and_update_schema()

def check_and_update_schema():
    """
    Check if the database schema is up to date and update it if necessary.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        
        # Check if 'time' column exists
        c.execute("PRAGMA table_info(measurements)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'time' in columns and 'timestamp' not in columns:
            print("Updating database schema: renaming 'time' column to 'timestamp'")
            c.execute("ALTER TABLE measurements RENAME COLUMN time TO timestamp")
            conn.commit()

def store_measurement(timestamp, temperature, humidity):
    """
    Store a single measurement in the database, updating existing record if it exists.
    
    Args:
    timestamp (str): The time of the measurement in 'YYYY-MM-DD HH:MM:SS' format.
    temperature (float): The temperature reading.
    humidity (float): The humidity reading.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO measurements (timestamp, temperature, humidity)
            VALUES (?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
            temperature = COALESCE(EXCLUDED.temperature, temperature),
            humidity = COALESCE(EXCLUDED.humidity, humidity)
        """, (timestamp, temperature, humidity))
        conn.commit()
    print(f"Stored/Updated measurement: Timestamp: {timestamp}, Temp: {temperature}, Humidity: {humidity}")

def get_historical_data(hours=2, resample_interval='5min'):
    """
    Retrieve historical data from the database for the specified number of hours.
    
    Args:
    hours (int): The number of hours of historical data to retrieve (default is 2).
    resample_interval (str): Interval to resample data to (default is '5min' for 5 minutes).
    
    Returns:
    list: A list of dictionaries containing timestamp, temperature, and humidity data.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("""
            SELECT timestamp, temperature, humidity 
            FROM measurements 
            WHERE timestamp > ? 
            ORDER BY timestamp ASC
        """, (time_threshold,))
        data = c.fetchall()
    
    if data:
        # Convert to pandas DataFrame for easy resampling
        df = pd.DataFrame(data, columns=['timestamp', 'temperature', 'humidity'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resample data to specified interval
        resampled = df.resample(resample_interval).mean()
        
        # Fill NaN values with the last known value
        resampled = resampled.ffill()
        
        # Convert back to list of dictionaries
        return [{'time': index.strftime('%Y-%m-%d %H:%M:%S'), 
                 'temperature': row['temperature'] if not pd.isna(row['temperature']) else None, 
                 'humidity': row['humidity'] if not pd.isna(row['humidity']) else None} 
                for index, row in resampled.iterrows()]
    else:
        return []

def check_data_freshness():
    """
    Check if the most recent data in the database is fresh (not older than 2 hours).
    
    Returns:
    bool: True if the data is fresh, False otherwise.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(timestamp) FROM measurements")
        latest_timestamp = c.fetchone()[0]

    if latest_timestamp:
        latest_time = datetime.strptime(latest_timestamp, '%Y-%m-%d %H:%M:%S')
        time_difference = datetime.now() - latest_time
        return time_difference <= timedelta(hours=2)
    return False

def cleanup_old_data(days=10):
    """
    Remove data older than the specified number of days from the database.
    
    Args:
    days (int): The number of days to keep data for (default is 10).
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("DELETE FROM measurements WHERE timestamp < ?", (threshold,))
        conn.commit()
