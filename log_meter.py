#!/usr/bin/env python3
"""
Log a gas meter reading to the database
Usage: python log_meter.py <reading>
"""

import os
import sys
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_last_reading():
    """Get the most recent meter reading"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT meter_reading FROM gas_meter_readings ORDER BY recorded_at DESC LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else None


def log_reading(reading):
    """Log a new meter reading"""
    last = get_last_reading()
    ccf_since_last = reading - last if last else None

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO gas_meter_readings (meter_reading, ccf_since_last)
        VALUES (%s, %s)
        RETURNING id, recorded_at
    """, (reading, ccf_since_last))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result, ccf_since_last


def main():
    if len(sys.argv) != 2:
        print("Usage: python log_meter.py <reading>")
        print("Example: python log_meter.py 1410")
        sys.exit(1)

    try:
        reading = int(sys.argv[1])
    except ValueError:
        print("Error: Reading must be a number")
        sys.exit(1)

    (record_id, recorded_at), ccf_since_last = log_reading(reading)

    print(f"[{datetime.now()}] Logged meter reading: {reading}")
    if ccf_since_last is not None:
        print(f"  CCF since last reading: {ccf_since_last}")
    print(f"  Saved as record #{record_id} at {recorded_at}")


if __name__ == '__main__':
    main()
