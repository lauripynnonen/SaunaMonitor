```python
from datetime import datetime, timedelta
from database import get_historical_data
from config import TARGET_TEMP

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
           and a boolean indicating if the sauna is active.
    """
    historical_data = get_historical_data(hours=1)  # Use last 1 hour of data
    if len(historical_data) < 2:
        return "Insufficient data", None, False
    
    # Convert data to list of tuples (timestamp, temperature)
    temp_data = [(datetime.strptime(d['time'], '%Y-%m-%d %H:%M:%S'), d['temperature']) for d in historical_data]
    temp_data.sort()  # Ensure data is in chronological order
    
    current_temp = temp_data[-1][1]
    
    # Check if the sauna is cold
    if current_temp < MIN_ACTIVE_TEMP:
        return "Cold", None, False
    
    # Check if the sauna is at or above target temperature
    if current_temp >= TARGET_TEMP:
        return "Ready", None, True
    
    # Calculate temperature change over the last 15 minutes
    recent_data = [d for d in temp_data if d[0] >= temp_data[-1][0] - timedelta(minutes=15)]
    if len(recent_data) < 2:
        recent_data = temp_data[-2:]  # Use at least two points
    
    time_diff = (recent_data[-1][0] - recent_data[0][0]).total_seconds() / 3600  # in hours
    temp_diff = recent_data[-1][1] - recent_data[0][1]
    
    # Check for stable temperature
    if abs(temp_diff) < 1:  # Less than 1°C change in 15 minutes
        return "Temperature stable", None, True
    
    # Check if heating
    if temp_diff > 0:
        rate = temp_diff / time_diff  # °C per hour
        time_to_target = (TARGET_TEMP - current_temp) / rate
        minutes_to_target = int(time_to_target * 60)
        return "Heating", minutes_to_target, True
    
    # Temperature is dropping
    return "Cooling", None, True

def get_status_message(current_temp, estimate):
    """
    Generate a status message based on the current temperature and time estimate.
    
    Args:
    current_temp (float): The current temperature.
    estimate (tuple): The output from get_estimated_time().
    
    Returns:
    tuple: A tuple containing the status title (str) and status message (str).
    """
    status, minutes, is_active = estimate
    
    if status == "Cold":
        return "Sauna is cold", "Turn on to heat"
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
        if minutes > 60:
            return f"Heating", f"{minutes // 60}h {minutes % 60}min to {TARGET_TEMP}°C"
        else:
            return f"Heating", f"{minutes} min to {TARGET_TEMP}°C"
    elif status == "Cooling":
        return "Temp dropping", "Add wood if needed"
    else:
        return "Status unknown", "Check sauna"
