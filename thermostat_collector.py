#!/usr/bin/env python3
"""
Thermostat Data Collector
Reads data from Honeywell WiFi 9000 and stores in Neon database
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from pyhtcc import PyHTCC

# Load environment variables from .env file
load_dotenv()

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')

# Honeywell credentials
HONEYWELL_EMAIL = os.environ.get('PYHTCC_EMAIL')
HONEYWELL_PASS = os.environ.get('PYHTCC_PASS')

# Downstairs setpoint (for adjusted outdoor temp calculation)
DOWNSTAIRS_SETPOINT = 65
HEAT_RISE_FACTOR = 0.3  # Calibrate based on actual data


def get_thermostat_data():
    """Fetch current thermostat data from Honeywell"""
    htcc = PyHTCC(HONEYWELL_EMAIL, HONEYWELL_PASS)
    zones = htcc.get_all_zones()

    if not zones:
        raise Exception("No zones found")

    zone = zones[0]  # Use first zone
    info = zone.zone_info
    ui_data = info.get('latestData', {}).get('uiData', {})
    fan_data = info.get('latestData', {}).get('fanData', {})

    # Map SystemSwitchPosition to mode string
    mode_map = {0: 'emheat', 1: 'heat', 2: 'off', 3: 'cool', 4: 'auto'}
    fan_map = {0: 'auto', 1: 'on', 2: 'circulate'}

    # EquipmentOutputStatus: 0=off, 1=heating, 2=cooling
    equip_status = ui_data.get('EquipmentOutputStatus', 0)

    outdoor_temp = info.get('OutdoorTemperature') if info.get('OutdoorTemperature') != 128 else None

    # Calculate adjusted outdoor temp (accounts for heat rising from downstairs)
    adjusted_outdoor = None
    if outdoor_temp is not None:
        if outdoor_temp < DOWNSTAIRS_SETPOINT:
            # Downstairs is heating, some heat rises to upstairs
            adjusted_outdoor = outdoor_temp + (HEAT_RISE_FACTOR * (DOWNSTAIRS_SETPOINT - outdoor_temp))
        else:
            # No heating needed downstairs, no adjustment
            adjusted_outdoor = outdoor_temp

    return {
        'indoor_temp': info.get('DispTemp'),
        'outdoor_temp': outdoor_temp,
        'adjusted_outdoor_temp': adjusted_outdoor,
        'heat_setpoint': ui_data.get('HeatSetpoint'),
        'cool_setpoint': ui_data.get('CoolSetpoint'),
        'humidity': info.get('IndoorHumi'),
        'mode': mode_map.get(ui_data.get('SystemSwitchPosition'), 'unknown'),
        'fan_mode': fan_map.get(fan_data.get('fanMode'), 'unknown'),
        'is_heating': equip_status == 1,
        'is_cooling': equip_status == 2,
    }


def save_to_db(data):
    """Save thermostat reading to Neon database"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO thermostat_readings
        (indoor_temp, outdoor_temp, adjusted_outdoor_temp, heat_setpoint, cool_setpoint,
         humidity, mode, fan_mode, is_heating, is_cooling)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, recorded_at
    """, (
        data['indoor_temp'],
        data['outdoor_temp'],
        data['adjusted_outdoor_temp'],
        data['heat_setpoint'],
        data['cool_setpoint'],
        data['humidity'],
        data['mode'],
        data['fan_mode'],
        data['is_heating'],
        data['is_cooling'],
    ))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result


def main():
    print(f"[{datetime.now()}] Fetching thermostat data...")

    try:
        data = get_thermostat_data()
        print(f"  Indoor: {data['indoor_temp']}F, Outdoor: {data['outdoor_temp']}F (adj: {data['adjusted_outdoor_temp']:.1f}F), Setpoint: {data['heat_setpoint']}F, Heating: {data['is_heating']}")

        record_id, recorded_at = save_to_db(data)
        print(f"  Saved as record #{record_id} at {recorded_at}")

    except Exception as e:
        print(f"  Error: {e}")
        raise


if __name__ == '__main__':
    main()
