```python
from ruuvitag_sensor.ruuvi import RuuviTagSensor
from datetime import datetime
from config import RUUVITAG_MAC
from database import store_measurement

current_temp = 0
current_humidity = 0
last_update_time = None
last_data_store_time = None

def handle_data(found_data):
    """
    Process data received from the RuuviTag.
    This function is called every time new data is received from the tag.
    It updates the current temperature and humidity, and stores the data
    in the database every minute.
    
    Args:
    found_data (dict): Dictionary containing data from the RuuviTag.
    """
    global current_temp, current_humidity, last_update_time, last_data_store_time
    if RUUVITAG_MAC in found_data:
        data = found_data[RUUVITAG_MAC]
        current_temp = data['temperature']
        current_humidity = data['humidity']
        current_time = datetime.now()

        # Store data every minute
        if last_data_store_time is None or (current_time - last_data_store_time).total_seconds() >= 60:
            store_measurement(current_time.strftime('%Y-%m-%d %H:%M:%S'), current_temp, current_humidity)
            last_data_store_time = current_time

        last_update_time = current_time

def start_realtime_listener():
    """
    Start the real-time listener for RuuviTag data.
    This function initiates the continuous listening process for data
    broadcasts from the RuuviTag.
    """
    RuuviTagSensor.get_datas(handle_data, [RUUVITAG_MAC])

async def download_historical_data():
    """
    Download historical data from the RuuviTag using Bluetooth Low Energy.
    This function connects to the RuuviTag, requests historical data,
    and stores it in the database.
    """
    log_data_end_of_data = False
    historical_data = []

    def handle_rx(_: int, data: bytearray):
        nonlocal log_data_end_of_data, historical_data
        if len(data) > 0 and data[0] == DATATYPE_LOG:
            if len(data) == 11:
                dat = struct.unpack('>BBBII', data)
                if dat[3] == 0xFFFFFFFF and dat[4] == 0xFFFFFFFF:
                    log_data_end_of_data = True
                else:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dat[3]))
                    if dat[1] == 0x30:  # Temperature
                        historical_data.append((timestamp, dat[4]/100.0, None))
                    elif dat[1] == 0x31:  # Humidity
                        # Find the matching temperature entry and update it
                        for i, (t, temp, _) in enumerate(historical_data):
                            if t == timestamp:
                                historical_data[i] = (t, temp, dat[4]/100.0)
                                break

    async with BleakClient(RUUVITAG_MAC) as client:
        await client.start_notify(UART_TX_CHAR_UUID, handle_rx)

        # Request log data
        timenow = int(time.time())
        timeprv = timenow - LOG_SECONDS
        data_tx = struct.pack('>BBBIIII', DATATYPE_LOG, DATATYPE_LOG, 0x11, timenow, timeprv)
        await client.write_gatt_char(UART_RX_CHAR_UUID, data_tx)

        while not log_data_end_of_data:
            await asyncio.sleep(1)

    # Store the downloaded historical data
    for timestamp, temperature, humidity in historical_data:
        if temperature is not None and humidity is not None:
            store_measurement(timestamp, temperature, humidity)

def get_current_data():
    """
    Retrieve the most recent data from the RuuviTag.
    
    Returns:
    dict: A dictionary containing the current sensor data, or None if no data is available.
    """
    data = RuuviTagSensor.get_data_for_sensors([RUUVITAG_MAC], 5)
    if RUUVITAG_MAC in data:
        return data[RUUVITAG_MAC]
    return None

def get_current_temp():
    """
    Get the current temperature from the most recent RuuviTag data.
    
    Returns:
    float: The current temperature, or 0 if no data is available.
    """
    data = get_current_data()
    return data['temperature'] if data else 0

def get_current_humidity():
    """
    Get the current humidity from the most recent RuuviTag data.
    
    Returns:
    float: The current humidity, or 0 if no data is available.
    """
    data = get_current_data()
    return data['humidity'] if data else 0
