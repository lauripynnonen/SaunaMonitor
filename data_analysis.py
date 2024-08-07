from datetime import datetime, timedelta
import numpy as np
from scipy.stats import linregress
from config import TARGET_TEMP, MIN_ACTIVE_TEMP
from database import get_historical_data
import pytz

# Assuming you're in Finland, but adjust the timezone as needed
TIMEZONE = pytz.timezone('Europe/Stockholm')

def get_current_time():
    """Get the current time in the specified timezone."""
    return datetime.now(TIMEZONE)

def get_temperature_trend(hours=0.5):
    """
    Calculate the temperature trend over the specified time period.
    
    Args:
    hours (float): The number of hours to consider for the trend calculation (default is 0.5 hours).
    
    Returns:
    float: The temperature change rate in °C per hour.
    """
    historical_data = get_historical_data(hours=hours)
    if len(historical_data) < 2:
        return 0
    
    temp_data = [(datetime.strptime(d['time'], '%Y-%m-%d %H:%M:%S'), d['temperature']) for d in historical_data]
    temp_data.sort()
    
    time_diff = (temp_data[-1][0] - temp_data[0][0]).total_seconds() / 3600  # in hours
    temp_diff = temp_data[-1][1] - temp_data[0][1]
    
    if time_diff == 0:
        return 0
    
    return temp_diff / time_diff  # °C per hour

def get_estimated_time():
    """
    Estimate the time remaining to reach the target temperature and determine sauna state.
    
    Returns:
    tuple: A tuple containing the status (str), estimated time in minutes (int or None),
           expected ready time (datetime or None), and a boolean indicating if the sauna is active.
    """
    historical_data = get_historical_data(hours=2)  # Use last 2 hours of data
    if len(historical_data) < 2:
        return "Insufficient data", None, None, False
    
    # Sort data by time
    historical_data.sort(key=lambda x: x['time'])
    
    # Convert string times to datetime objects
    for data in historical_data:
        data['time'] = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S')
    
    current_temp = historical_data[-1]['temperature']
    current_time = get_current_time()
    
    # Check if the sauna is cold
    if current_temp < MIN_ACTIVE_TEMP:
        return "Cold", None, None, False
    
    # Check if the sauna is at or above target temperature
    if current_temp >= TARGET_TEMP:
        return "Ready", None, current_time, True
    
    # Calculate temperature change over different time periods
    time_periods = [5, 15, 30]  # minutes
    rates = []
    
    for period in time_periods:
        cutoff_time = current_time - timedelta(minutes=period)
        recent_data = [d for d in historical_data if d['time'] >= cutoff_time]
        
        if len(recent_data) < 2:
            continue
        
        times = [(d['time'] - recent_data[0]['time']).total_seconds() / 60 for d in recent_data]
        temps = [d['temperature'] for d in recent_data]
        
        slope, _, _, _, _ = linregress(times, temps)
        rates.append(slope)
    
    if not rates:
        return "Temperature stable", None, None, True
    
    # Use weighted average of rates, giving more weight to recent data
    weights = [3, 2, 1][:len(rates)]
    avg_rate = np.average(rates, weights=weights)
    
    # Check for stable temperature
    if abs(avg_rate) < 0.1:  # Less than 0.1°C change per minute
        return "Temperature stable", None, None, True
    
    # Check if heating
    if avg_rate > 0:
        time_to_target = (TARGET_TEMP - current_temp) / avg_rate
        minutes_to_target = int(time_to_target)
        expected_ready_time = current_time + timedelta(minutes=minutes_to_target)
        return "Heating", minutes_to_target, expected_ready_time, True
    
    # Temperature is dropping
    return "Cooling", None, None, True

def get_status_message(current_temp, estimate):
    """
    Generate a status message based on the current temperature and time estimate.
    
    Args:
    current_temp (float): The current temperature.
    estimate (tuple): The output from get_estimated_time().
    
    Returns:
    tuple: A tuple containing the status title (str) and status message (str).
    """
    status, minutes, expected_ready_time, is_active = estimate
    current_time = get_current_time()
    
    if status == "Cold":
        return "Sauna is not heating", "Time to light a fire?"
    elif status == "Insufficient data":
        return "Collecting data", "Please wait..."
    elif status == "Temperature stable":
        if current_temp < TARGET_TEMP:
            return "Temp stable", "Add wood to increase"
        else:
            return "Temp stable", "Enjoy your sauna"
    elif status == "Ready":
        return "Sauna is ready!", "Enjoy your sauna"
    elif status == "Heating":
        if minutes is not None and expected_ready_time is not None:
            return f"Heating", f"Ready in: {minutes} min\nAt: {expected_ready_time.strftime('%H:%M')}"
        else:
            return f"Heating", "Estimating time..."
    elif status == "Cooling":
        return "Temp dropping", "Add wood if needed"
    else:
        return "Status unknown", "Check sauna"
