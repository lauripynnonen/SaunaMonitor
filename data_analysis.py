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
    Estimate the time remaining to reach the target temperature.
    
    Returns:
    tuple: A tuple containing the status (str) and estimated time in minutes (int or None).
    """
    historical_data = get_historical_data(hours=2)  # Use last 2 hours of data
    if len(historical_data) < 2:
        return "Insufficient data", None
    
    # Convert data to list of tuples (timestamp, temperature)
    temp_data = [(datetime.strptime(d['time'], '%Y-%m-%d %H:%M:%S'), d['temperature']) for d in historical_data]
    temp_data.sort()  # Ensure data is in chronological order
    
    # Find when temperature started rising significantly
    start_index = 0
    for i in range(1, len(temp_data)):
        if temp_data[i][1] - temp_data[i-1][1] > 1:  # 1°C threshold for significant rise
            start_index = i
            break
    
    if start_index == 0:
        return "Not heating", None
    
    # Use data from the point where temperature started rising
    rising_temp_data = temp_data[start_index:]
    
    if len(rising_temp_data) < 2:
        return "Heating just started", None
    
    # Calculate rate of temperature increase using the most recent 15 minutes of data
    recent_data = [d for d in rising_temp_data if d[0] >= rising_temp_data[-1][0] - timedelta(minutes=15)]
    
    if len(recent_data) < 2:
        recent_data = rising_temp_data[-2:]  # Use at least two points
    
    time_diff = (recent_data[-1][0] - recent_data[0][0]).total_seconds() / 3600  # in hours
    temp_diff = recent_data[-1][1] - recent_data[0][1]
    
    if time_diff == 0 or temp_diff <= 0:
        return "Temperature stable", None
    
    rate = temp_diff / time_diff  # °C per hour
    
    time_to_target = (TARGET_TEMP - recent_data[-1][1]) / rate
    
    if time_to_target <= 0:
        return "Ready", None
    
    minutes_to_target = int(time_to_target * 60)
    return f"{minutes_to_target} min", minutes_to_target

def get_status_message(current_temp, estimate):
    """
    Generate a status message based on the current temperature and time estimate.
    
    Args:
    current_temp (float): The current temperature.
    estimate (tuple): The output from get_estimated_time().
    
    Returns:
    tuple: A tuple containing the status title (str) and status message (str).
    """
    status, minutes = estimate
    temp_trend = get_temperature_trend()
    
    if temp_trend < TEMP_DROP_THRESHOLD:
        return "Temperature dropping", "Add wood to stove"
    
    if status == "Not heating":
        return "Sauna is cold", "Turn on to heat"
    elif status == "Heating just started":
        return "Heating up", "Estimating time..."
    elif status == "Insufficient data" or status == "Temperature stable":
        return "Status unclear", "Check back soon"
    elif status == "Ready":
        if current_temp >= TARGET_TEMP:
            return "Sauna is ready!", "Enjoy your sauna"
        else:
            return "Temp maintaining", "Add wood if needed"
    elif minutes is not None:
        if minutes > 60:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes // 60}h {minutes % 60}min"
        else:
            return f"Est. time to {TARGET_TEMP}°C", f"{minutes} min"
    else:
        return "Status unknown", "Check sauna"
