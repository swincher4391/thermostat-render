"""
Estimate January 2026 bill (billing cycle 12/12/25 - 1/13/26)
Using 0.12 CCF/HDD slope and actual meter data from Neon database
Fetches weather forecast from NWS for future day estimates
Uses IEM ASOS data for historical hourly temps (KBWG)
"""
import os
import psycopg2
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable required")

def get_meter_readings():
    """Fetch meter readings from Neon database"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get latest reading
    cur.execute("""
        SELECT meter_reading, recorded_at
        FROM gas_meter_readings
        ORDER BY recorded_at DESC
        LIMIT 1
    """)
    latest = cur.fetchone()

    cur.close()
    conn.close()

    return latest


def get_iem_hourly_temps(start_date, end_date):
    """
    Fetch hourly temperature data from Iowa Environmental Mesonet (IEM)
    for Bowling Green airport (KBWG)
    """
    url = (
        f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        f"station=KBWG&data=tmpf"
        f"&year1={start_date.year}&month1={start_date.month}&day1={start_date.day}"
        f"&year2={end_date.year}&month2={end_date.month}&day2={end_date.day}"
        f"&tz=America%2FChicago&format=onlycomma&latlon=no&elev=no"
        f"&missing=M&trace=T&direct=no&report_type=3"
    )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Parse CSV data
        lines = response.text.strip().split('\n')
        hourly_data = {}  # {date: [temps]}

        for line in lines[1:]:  # Skip header
            parts = line.split(',')
            if len(parts) >= 3 and parts[2] != 'M':
                date_str = parts[1].split()[0]  # "2026-01-09"
                temp = float(parts[2])

                if date_str not in hourly_data:
                    hourly_data[date_str] = []
                hourly_data[date_str].append(temp)

        return hourly_data

    except Exception as e:
        print(f"[IEM] Error fetching hourly data: {e}")
        return None


def calculate_hourly_hdd(temps):
    """
    Calculate HDD from hourly temperatures
    Each hour contributes: max(0, 65 - temp) / 24
    """
    if not temps or len(temps) < 20:  # Need most of the day's readings
        return None

    total_hdd = sum(max(0, 65 - temp) for temp in temps) / len(temps) * 24 / 24
    # Simplified: average the hourly HDDs
    total_hdd = sum(max(0, 65 - temp) for temp in temps) / len(temps)
    return total_hdd


def get_nws_forecast():
    """Fetch weather forecast from NWS API for Bowling Green, KY"""
    points_url = "https://api.weather.gov/points/36.9685,-86.4808"
    headers = {"User-Agent": "GasBillEstimator/1.0"}

    try:
        response = requests.get(points_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        forecast_url = data["properties"]["forecast"]

        response = requests.get(forecast_url, headers=headers, timeout=10)
        response.raise_for_status()
        forecast_data = response.json()

        periods = forecast_data["properties"]["periods"]
        daily_forecasts = {}

        for period in periods:
            temp = period["temperature"]
            is_day = period["isDaytime"]
            start_time = datetime.fromisoformat(period["startTime"].replace("Z", "+00:00"))
            date_key = start_time.strftime("%Y-%m-%d")

            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {"high": None, "low": None, "date": start_time}

            if is_day:
                daily_forecasts[date_key]["high"] = temp
            else:
                daily_forecasts[date_key]["low"] = temp

        # Fill in missing lows
        for date in daily_forecasts:
            if daily_forecasts[date]["low"] is None and daily_forecasts[date]["high"]:
                daily_forecasts[date]["low"] = daily_forecasts[date]["high"] - 20

        return daily_forecasts

    except Exception as e:
        print(f"[NWS] Error fetching forecast: {e}")
        return None


def calculate_future_hdd(forecast_data, start_date, end_date):
    """Calculate HDD for future days from forecast data"""
    future_days = []
    current = start_date

    while current <= end_date:
        date_key = current.strftime("%m/%d")
        if date_key in forecast_data:
            fc = forecast_data[date_key]
            if fc["high"] and fc["low"]:
                avg = (fc["high"] + fc["low"]) / 2
                hdd = max(0, 65 - avg)
                future_days.append({
                    "date": date_key,
                    "high": fc["high"],
                    "low": fc["low"],
                    "avg": avg,
                    "hdd": hdd
                })
        current += timedelta(days=1)

    return future_days

# =============================================================================
# ACTUAL DATA
# =============================================================================

# Meter readings
meter_dec_11 = 1339  # Bill cycle start reference (from bill)

# Get latest reading from database
try:
    db_reading = get_meter_readings()
    if db_reading:
        meter_latest = db_reading[0]
        reading_date = db_reading[1]
        print(f"[Database] Latest reading: {meter_latest} at {reading_date}")
    else:
        meter_latest = 1409  # Fallback
        reading_date = datetime(2026, 1, 9)
        print("[Database] No readings found, using fallback")
except Exception as e:
    print(f"[Database] Connection error: {e}")
    meter_latest = 1409  # Fallback
    reading_date = datetime(2026, 1, 9)

# Billing cycle info
billing_start = "12/12/25"
billing_end = "1/13/26"

# =============================================================================
# HDD CALCULATION: HYBRID APPROACH
# - Past days: Hourly temps from IEM ASOS (KBWG)
# - Future days: NWS forecast high/low
# =============================================================================

ccf_per_hdd = 0.12
billing_start_date = datetime(2025, 12, 12)
billing_end_date = datetime(2026, 1, 13)
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

print("\n" + "=" * 60)
print("HDD CALCULATION (Hybrid: IEM hourly + NWS forecast)")
print("=" * 60)

# Fetch historical hourly data from IEM
print("\nFetching IEM hourly data (KBWG)...")
hourly_data = get_iem_hourly_temps(billing_start_date, today)

# Fetch NWS forecast for future days
print("Fetching NWS forecast...")
forecast_data = get_nws_forecast()

# Calculate HDD for each day
print(f"\n{'Date':<12} {'Source':<10} {'Temps':<20} {'HDD':>8} {'CCF':>8}")
print("-" * 62)

total_hdd = 0
total_ccf = 0
current_date = billing_start_date

while current_date <= billing_end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    date_display = current_date.strftime("%m/%d")

    if current_date < today and hourly_data and date_str in hourly_data:
        # Past day with hourly data - use IEM
        temps = hourly_data[date_str]
        if len(temps) >= 20:
            hdd = calculate_hourly_hdd(temps)
            temp_info = f"{min(temps):.0f}-{max(temps):.0f}F ({len(temps)}hr)"
            source = "IEM"
        else:
            # Not enough hourly data, fall back to high/low
            hdd = max(0, 65 - (max(temps) + min(temps)) / 2) if temps else 0
            temp_info = f"{min(temps):.0f}-{max(temps):.0f}F (partial)"
            source = "IEM*"
    elif forecast_data and date_str in forecast_data:
        # Future day - use NWS forecast
        fc = forecast_data[date_str]
        if fc["high"] and fc["low"]:
            avg = (fc["high"] + fc["low"]) / 2
            hdd = max(0, 65 - avg)
            temp_info = f"{fc['low']}-{fc['high']}F (fcst)"
            source = "NWS"
        else:
            hdd = 25  # Fallback
            temp_info = "est"
            source = "Est"
    else:
        # No data - estimate
        hdd = 25
        temp_info = "no data"
        source = "Est"

    ccf = hdd * ccf_per_hdd
    total_hdd += hdd
    total_ccf += ccf

    print(f"{date_display:<12} {source:<10} {temp_info:<20} {hdd:>8.1f} {ccf:>8.2f}")
    current_date += timedelta(days=1)

print("-" * 62)
print(f"{'TOTAL':<12} {'':<10} {'':<20} {total_hdd:>8.1f} {total_ccf:>8.2f}")

# Calculate remaining CCF (future days only)
remaining_hdd = 0
remaining_ccf = 0
current_date = today
while current_date <= billing_end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    if forecast_data and date_str in forecast_data:
        fc = forecast_data[date_str]
        if fc["high"] and fc["low"]:
            hdd = max(0, 65 - (fc["high"] + fc["low"]) / 2)
            remaining_hdd += hdd
            remaining_ccf += hdd * ccf_per_hdd
    else:
        remaining_hdd += 25
        remaining_ccf += 25 * ccf_per_hdd
    current_date += timedelta(days=1)

# =============================================================================
# USAGE CALCULATION
# =============================================================================

print("\n" + "=" * 70)
print("JANUARY 2026 BILL ESTIMATE (Cycle: 12/12/25 - 1/13/26)")
print("=" * 70)

# Actual usage Dec 11 - latest reading
actual_ccf_so_far = float(meter_latest) - meter_dec_11
print(f"\nMeter Readings:")
print(f"  Dec 11:  {meter_dec_11} (billing start)")
print(f"  Latest:  {meter_latest} ({reading_date.strftime('%b %d') if hasattr(reading_date, 'strftime') else reading_date})")
print(f"  Used:    {actual_ccf_so_far} CCF")

# Total for billing cycle: actual meter + future estimate
total_ccf_exact = actual_ccf_so_far + remaining_ccf
total_ccf_int = int(total_ccf_exact)  # Meter rounds down

# Meter could be anywhere from X.0 to X.99, so estimate range
estimated_meter_low = int(meter_dec_11 + total_ccf_int)
estimated_meter_high = int(meter_dec_11 + total_ccf_int + 1)

print(f"\n{'='*40}")
print(f"SUMMARY")
print(f"{'='*40}")
print(f"  Actual (metered):   {actual_ccf_so_far} CCF")
print(f"  Remaining (HDD):    {remaining_ccf:.1f} CCF ({remaining_hdd:.0f} HDD)")
print(f"  Total (exact):      {total_ccf_exact:.1f} CCF")
print(f"  Total (rounded):    {total_ccf_int} CCF")
print(f"  Est. meter 1/13:    {estimated_meter_low}-{estimated_meter_high}")
print(f"{'='*40}")

# For WNA and bill calculations
total_ccf = total_ccf_int
total_future_hdd = total_hdd  # Full billing period HDD for WNA

# =============================================================================
# WNA CALCULATION
# =============================================================================

print("\n" + "=" * 70)
print("WNA CALCULATION")
print("=" * 70)

# Parameters
R = 1.6261       # Distribution rate $/Mcf
HSF = 0.012576   # Heat sensitivity factor
BL = 1.0556      # Base load

# ADD = actual HDD for billing cycle (from hybrid calculation)
ADD = total_hdd

# NDD = normal HDD for billing cycle
# 33 days × ~24 HDD/day normal for Dec-Jan
billing_days = (billing_end_date - billing_start_date).days + 1
ndd_daily = 24
NDD = billing_days * ndd_daily

print(f"\nBilling period: {billing_days} days")
print(f"  Actual ADD:    {ADD:.1f} (from IEM hourly + NWS forecast)")
print(f"  Normal NDD:    {NDD:.1f} ({ndd_daily}/day)")
print(f"  Difference:    {NDD - ADD:.1f}")

# Calculate WNAF
wnaf = R * (HSF * (NDD - ADD)) / (BL + (HSF * ADD))
print(f"\nWNA Factor: ${wnaf:.4f}/Mcf (${wnaf/10:.6f}/Ccf)")

if NDD > ADD:
    print(f"  -> WARMER than normal = SURCHARGE")
else:
    print(f"  -> COLDER than normal = CREDIT")

# =============================================================================
# BILL ESTIMATE
# =============================================================================

print("\n" + "=" * 70)
print("BILL ESTIMATE")
print("=" * 70)

usage_ccf = total_ccf
usage_mcf = usage_ccf / 10

# Charges (from actual bills)
customer_charge = 25.00
distribution_base = usage_mcf * R
wna_charge = usage_mcf * wnaf
prp_charge = usage_mcf * 0.8214
gas_cost = usage_ccf * 0.54034
school_fee = usage_ccf * 0.03
franchise_fee = usage_ccf * 0.01

print(f"\nUsage: {usage_ccf:.0f} CCF ({usage_mcf:.1f} Mcf)")
print(f"\n{'Charge':<25} {'Amount':>10}")
print("-" * 40)
print(f"{'Customer Charge':<25} ${customer_charge:>9.2f}")
print(f"{'Distribution':<25} ${distribution_base:>9.2f}")
print(f"{'WNA':<25} ${wna_charge:>9.2f}")
print(f"{'PRP':<25} ${prp_charge:>9.2f}")
print(f"{'Gas Cost (GCA)':<25} ${gas_cost:>9.2f}")
print(f"{'School Fee':<25} ${school_fee:>9.2f}")
print(f"{'Franchise Fee':<25} ${franchise_fee:>9.2f}")
print("-" * 40)

total_bill = (customer_charge + distribution_base + wna_charge +
              prp_charge + gas_cost + school_fee + franchise_fee)
print(f"{'TOTAL ESTIMATED BILL':<25} ${total_bill:>9.2f}")

# Show effective rates
print(f"\n{'='*40}")
print("EFFECTIVE RATES:")
dist_total = distribution_base + wna_charge
print(f"  Distribution (w/WNA): ${dist_total/usage_ccf:.5f}/Ccf")
print(f"  Total variable:       ${(total_bill - customer_charge)/usage_ccf:.5f}/Ccf")
