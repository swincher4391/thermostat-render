"""
Estimate January 2026 bill (billing cycle 12/12/25 - 1/13/26)
Using 0.12 CCF/HDD slope and actual meter data from Neon database
Fetches weather forecast from NWS for future day estimates
"""
import os
import re
import psycopg2
import requests
from datetime import datetime, timedelta

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_BSM3cGvxtF1k@ep-delicate-sea-ah563pvy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

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


def get_nws_forecast():
    """Fetch weather forecast from NWS API for Bowling Green, KY"""
    # NWS API endpoint for Bowling Green, KY
    # First get the forecast URL from the points endpoint
    points_url = "https://api.weather.gov/points/36.9685,-86.4808"
    headers = {"User-Agent": "GasBillEstimator/1.0"}

    try:
        response = requests.get(points_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        forecast_url = data["properties"]["forecast"]

        # Get the actual forecast
        response = requests.get(forecast_url, headers=headers, timeout=10)
        response.raise_for_status()
        forecast_data = response.json()

        # Parse periods into day/night pairs
        periods = forecast_data["properties"]["periods"]
        daily_forecasts = {}

        for period in periods:
            name = period["name"]
            temp = period["temperature"]
            is_day = period["isDaytime"]

            # Extract date from startTime
            start_time = datetime.fromisoformat(period["startTime"].replace("Z", "+00:00"))
            date_key = start_time.strftime("%m/%d")

            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {"high": None, "low": None, "date": start_time}

            if is_day:
                daily_forecasts[date_key]["high"] = temp
            else:
                daily_forecasts[date_key]["low"] = temp

        # Fill in missing lows from next day's night forecast or estimate
        dates = sorted(daily_forecasts.keys())
        for i, date in enumerate(dates):
            if daily_forecasts[date]["low"] is None:
                # Try to get from overnight period or estimate
                if daily_forecasts[date]["high"]:
                    # Rough estimate: low is typically 15-25 degrees below high
                    daily_forecasts[date]["low"] = daily_forecasts[date]["high"] - 20

        return daily_forecasts

    except Exception as e:
        print(f"[Weather] Error fetching forecast: {e}")
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

# HDD data from weather (12/12 - 1/8)
hdd_dec_12_to_jan_8 = 554.5  # Calculated from actual weather

# Billing cycle
billing_start = "12/12/25"
billing_end = "1/13/26"

# =============================================================================
# WEATHER FORECAST FOR REMAINING DAYS
# =============================================================================

# CCF slope
ccf_per_hdd = 0.12

# Fetch NWS forecast for future days
billing_end_date = datetime(2026, 1, 13)
forecast_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

print("\nFetching NWS forecast...")
forecast_data = get_nws_forecast()

if forecast_data:
    future_forecast = calculate_future_hdd(forecast_data, forecast_start, billing_end_date)
    print(f"\n{'Date':<8} {'High':>6} {'Low':>6} {'Avg':>6} {'HDD':>6} {'CCF':>6}")
    print("-" * 46)

    total_future_hdd = 0
    for day in future_forecast:
        ccf = day["hdd"] * ccf_per_hdd
        print(f"{day['date']:<8} {day['high']:>6} {day['low']:>6} {day['avg']:>6.1f} {day['hdd']:>6.1f} {ccf:>6.2f}")
        total_future_hdd += day["hdd"]

    future_ccf = total_future_hdd * ccf_per_hdd
    future_days_count = len(future_forecast)
    print("-" * 46)
    print(f"{'Total':<8} {'':>6} {'':>6} {'':>6} {total_future_hdd:>6.1f} {future_ccf:>6.2f}")
else:
    # Fallback to estimate if forecast fails
    print("[Weather] Using fallback estimate (25 HDD/day)")
    future_days_count = (billing_end_date - forecast_start).days + 1
    total_future_hdd = future_days_count * 25
    future_ccf = total_future_hdd * ccf_per_hdd

# =============================================================================
# USAGE CALCULATION
# =============================================================================

print("=" * 70)
print("JANUARY 2026 BILL ESTIMATE (Cycle: 12/12/25 - 1/13/26)")
print("=" * 70)

# Actual usage Dec 11 - latest reading
actual_ccf_so_far = meter_latest - meter_dec_11
print(f"\nMeter Readings:")
print(f"  Dec 11:  {meter_dec_11} (billing start)")
print(f"  Latest:  {meter_latest} ({reading_date.strftime('%b %d') if hasattr(reading_date, 'strftime') else reading_date})")
print(f"  Used:    {actual_ccf_so_far} CCF")

# Total for billing cycle
total_ccf_exact = actual_ccf_so_far + future_ccf
total_ccf = int(total_ccf_exact)  # Meter rounds down

# Meter could be anywhere from X.0 to X.99, so estimate range
estimated_meter_low = meter_dec_11 + total_ccf
estimated_meter_high = meter_dec_11 + total_ccf + 1

print(f"\n{'='*40}")
print(f"SUMMARY")
print(f"{'='*40}")
print(f"  Usage so far:     {actual_ccf_so_far} CCF")
print(f"  Future estimate:  {future_ccf:.1f} CCF")
print(f"  Total (exact):    {total_ccf_exact:.1f} CCF")
print(f"  Total (metered):  {total_ccf} CCF")
print(f"  Est. meter 1/13:  {estimated_meter_low}-{estimated_meter_high}")
print(f"{'='*40}")

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

# Total HDD for billing cycle
total_add = hdd_dec_12_to_jan_8 + total_future_hdd
# For future days, ADD = NDD, so they don't affect WNA
# WNA is based only on actual period where ADD may differ from NDD

# Estimate NDD for the actual period (12/12 - 1/8 = 28 days)
# Using ~24 HDD/day as normal for Dec-Jan
ndd_daily = 24
actual_days = 28
ndd_actual_period = actual_days * ndd_daily

print(f"\nActual period (12/12 - 1/8): {actual_days} days")
print(f"  Actual ADD:    {hdd_dec_12_to_jan_8:.1f}")
print(f"  Normal NDD:    {ndd_actual_period:.1f} ({ndd_daily}/day)")
print(f"  Difference:    {ndd_actual_period - hdd_dec_12_to_jan_8:.1f}")

# Calculate WNAF
ADD = hdd_dec_12_to_jan_8
NDD = ndd_actual_period
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
