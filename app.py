#!/usr/bin/env python3
"""
Thermostat Data Collector - Flask Server
Runs on Render to collect data every 15 minutes
"""

import os
import atexit
from datetime import datetime
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import psycopg2
import requests
from pyhtcc import PyHTCC

app = Flask(__name__)

# Render URL for self-ping (set this after deployment)
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')

# Honeywell credentials
HONEYWELL_EMAIL = os.environ.get('PYHTCC_EMAIL')
HONEYWELL_PASS = os.environ.get('PYHTCC_PASS')

# Downstairs setpoint (for adjusted outdoor temp calculation)
DOWNSTAIRS_SETPOINT = 65
HEAT_RISE_FACTOR = 0.3

# Track last collection status
last_collection = {
    'time': None,
    'status': 'not run',
    'error': None,
    'data': None
}


def get_thermostat_data():
    """Fetch current thermostat data from Honeywell"""
    htcc = PyHTCC(HONEYWELL_EMAIL, HONEYWELL_PASS)
    zones = htcc.get_all_zones()

    if not zones:
        raise Exception("No zones found")

    zone = zones[0]
    info = zone.zone_info
    ui_data = info.get('latestData', {}).get('uiData', {})
    fan_data = info.get('latestData', {}).get('fanData', {})

    mode_map = {0: 'emheat', 1: 'heat', 2: 'off', 3: 'cool', 4: 'auto'}
    fan_map = {0: 'auto', 1: 'on', 2: 'circulate'}

    equip_status = ui_data.get('EquipmentOutputStatus', 0)
    outdoor_temp = info.get('OutdoorTemperature') if info.get('OutdoorTemperature') != 128 else None

    adjusted_outdoor = None
    if outdoor_temp is not None:
        if outdoor_temp < DOWNSTAIRS_SETPOINT:
            adjusted_outdoor = outdoor_temp + (HEAT_RISE_FACTOR * (DOWNSTAIRS_SETPOINT - outdoor_temp))
        else:
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


def keep_alive():
    """Self-ping to prevent Render free tier from sleeping"""
    if RENDER_URL:
        try:
            response = requests.get(f"{RENDER_URL}/", timeout=10)
            print(f"[{datetime.now()}] Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now()}] Keep-alive error: {e}")


def collect_data():
    """Background job to collect thermostat data"""
    global last_collection
    print(f"[{datetime.now()}] Collecting thermostat data...")

    try:
        data = get_thermostat_data()
        record_id, recorded_at = save_to_db(data)

        last_collection = {
            'time': datetime.now().isoformat(),
            'status': 'success',
            'error': None,
            'data': {
                'record_id': record_id,
                'indoor_temp': data['indoor_temp'],
                'outdoor_temp': data['outdoor_temp'],
                'is_heating': data['is_heating']
            }
        }
        print(f"  Saved record #{record_id}: Indoor={data['indoor_temp']}F, Outdoor={data['outdoor_temp']}F, Heating={data['is_heating']}")

    except Exception as e:
        last_collection = {
            'time': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e),
            'data': None
        }
        print(f"  Error: {e}")


# Set up scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=collect_data, trigger="interval", minutes=15, id="collect")
scheduler.add_job(func=keep_alive, trigger="interval", minutes=10, id="keepalive")
scheduler.start()

# Shut down scheduler when app exits
atexit.register(lambda: scheduler.shutdown())


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'Thermostat Data Collector',
        'last_collection': last_collection
    })


@app.route('/collect')
def manual_collect():
    """Manually trigger data collection"""
    collect_data()
    return jsonify({
        'status': 'collected',
        'result': last_collection
    })


@app.route('/status')
def status():
    """Get last collection status"""
    return jsonify(last_collection)


if __name__ == '__main__':
    # Run initial collection on startup
    collect_data()

    # Start Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
