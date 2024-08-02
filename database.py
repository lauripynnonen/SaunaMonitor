import sqlite3
from datetime import datetime, timedelta
import threading
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

def store_measurement(timestamp, temperature, humidity):
    """
    Store a single measurement in the database.
    
    Args:
    timestamp (str): The time of the measurement in 'YYYY-MM-DD HH:MM:SS' format.
    temperature (float): The temperature reading.
    humidity (float): The humidity reading.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO measurements VALUES (?, ?, ?)",
                  (timestamp, temperature, humidity))
        conn.commit()

def get_historical_data(hours=2):
    """
    Retrieve historical data from the database for the specified number of hours.
    
    Args:
    hours (int): The number of hours of historical data to retrieve (default is 2).
    
    Returns:
    list: A list of dictionaries containing timestamp, temperature, and humidity data.
    """
    with db_lock, get_db_connection() as conn:
        c = conn.cursor()
        time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT * FROM measurements WHERE timestamp > ? ORDER BY timestamp DESC", (time_threshold,))
        data = c.fetchall()
    return [{"time": row[0], "temperature": row[1], "humidity": row[2]} for row in data]

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
