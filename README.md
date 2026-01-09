# Atmos - Thermostat & Gas Usage Monitoring

A project to monitor thermostat data and correlate it with gas consumption to predict utility bills and understand heating patterns.

## Overview

This system logs data from a Honeywell WiFi 9000 thermostat (upstairs) and gas meter readings to a Neon PostgreSQL database. The goal is to:

1. Track indoor/outdoor temperature and heating activity
2. Correlate temperature with gas usage
3. Predict monthly gas bills based on weather forecasts
4. Understand heating patterns between upstairs and downstairs zones

## Setup

### Prerequisites
- Python 3.x
- Honeywell Total Connect Comfort account
- Neon database (ThermostatDB project)

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Create a `.env` file with:
```
PYHTCC_EMAIL=your_honeywell_email
PYHTCC_PASS=your_honeywell_password
DATABASE_URL=postgresql://...your_neon_connection_string...
```

### Running
```bash
# Manual run
python thermostat_collector.py

# Log gas meter reading
python log_meter.py <reading>
```

### Automated Collection
Windows Task Scheduler runs `thermostat_collector.py` every 15 minutes via `run_collector.bat`.

---

## House Configuration

| Zone | Thermostat | Setpoint | WiFi Connected |
|------|------------|----------|----------------|
| Upstairs | Honeywell WiFi 9000 | 63°F | Yes (logged) |
| Downstairs | Standard thermostat | 65°F | No |

**Other gas appliances:** Stove only (water heater is electric)

---

## Database Schema

### thermostat_readings
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| recorded_at | TIMESTAMPTZ | Timestamp of reading |
| indoor_temp | DECIMAL | Indoor temperature (°F) |
| outdoor_temp | DECIMAL | Outdoor temperature from Honeywell (°F) |
| adjusted_outdoor_temp | DECIMAL | Adjusted temp accounting for heat rise (°F) |
| heat_setpoint | INTEGER | Heat setpoint (63°F) |
| cool_setpoint | INTEGER | Cool setpoint |
| humidity | INTEGER | Indoor humidity (%) |
| mode | VARCHAR | System mode (heat, cool, off, auto) |
| fan_mode | VARCHAR | Fan mode (auto, on, circulate) |
| is_heating | BOOLEAN | Whether furnace is currently heating |
| is_cooling | BOOLEAN | Whether AC is currently cooling |

### gas_meter_readings
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| recorded_at | TIMESTAMPTZ | Timestamp of reading |
| meter_reading | INTEGER | Cumulative meter reading (CCF) |
| ccf_since_last | DECIMAL | CCF consumed since last reading |

---

## Key Metrics & Formulas

### Heating Degree Days (HDD)
```
HDD = max(0, base_temp - outdoor_temp)
```
- **Base temperature:** 65°F (downstairs setpoint)
- Higher HDD = more heating demand

### Gas Usage Factor
Based on historical data (Dec 11 - Jan 7, 2026):
- **Total usage:** 69 CCF
- **Total HDD (base 65):** ~588
- **Factor:** 0.12 CCF per HDD

```
Estimated CCF = HDD × 0.12
```

### Adjusted Outdoor Temperature
Accounts for heat rising from downstairs to upstairs:
```python
if outdoor_temp < 65:  # Downstairs is heating
    adjusted = outdoor_temp + (HEAT_RISE_FACTOR × (65 - outdoor_temp))
else:
    adjusted = outdoor_temp
```
- **HEAT_RISE_FACTOR:** 0.3 (initial estimate, needs calibration)

**Example:**
| Actual Outdoor | Adjusted |
|----------------|----------|
| 65°F | 65°F |
| 50°F | 54.5°F |
| 40°F | 47.5°F |
| 27°F | 38.4°F |

---

## Bill Estimation

### Rate Structure (as of Dec 2025)
| Charge | Rate |
|--------|------|
| Customer Charge | $25.00/month |
| Distribution | $0.1682/CCF |
| Gas Cost | $0.5403/CCF |
| School Fee | $0.0375/CCF |
| Franchise Fee | $0.0123/CCF |
| PRP Charge | $0.0821/CCF |
| **Total Variable** | **$0.8404/CCF** |

### Bill Formula
```
Monthly Bill = $25 + (CCF × $0.8404)
```

### Example Estimates
| CCF | Estimated Bill |
|-----|----------------|
| 50 | $67 |
| 75 | $88 |
| 90 | $101 |
| 110 | $117 |

---

## Historical Data (2024-2025)

### Monthly Consumption
| Month | CCF | Avg Temp | Bill |
|-------|-----|----------|------|
| Jan 25 | 108 | 40°F | $88.31 |
| Feb 25 | 99 | 39°F | $85.98 |
| Mar 25 | 78 | 43°F | $70.89 |
| Apr 25 | 19 | 56°F | $33.43 |
| May 25 | 6 | 64°F | $25.78 |
| Jun 25 | 1 | 71°F | $26.96 |
| Jul 25 | 2 | 81°F | $27.50 |
| Aug 25 | 2 | 81°F | $27.74 |
| Sep 25 | 1 | 74°F | $26.47 |
| Oct 25 | 2 | 72°F | $27.75 |
| Nov 25 | 16 | 54°F | $38.96 |
| Dec 25 | 56 | 44°F | $72.07 |

### Seasonal Patterns
- **Summer (Jun-Sep):** 1-2 CCF/month (stove only)
- **Shoulder (Apr-May, Oct-Nov):** 6-19 CCF/month
- **Winter (Dec-Mar):** 56-108 CCF/month

---

## Heat Rise Theory

### Hypothesis
When outdoor temp drops below 65°F, the downstairs furnace kicks on. Heat rises to the upstairs, reducing or eliminating the need for the upstairs furnace to run.

### Observable Patterns

**Heat rising from downstairs (inferred):**
- Outdoor temp falling
- Indoor temp stable at 63°F
- `is_heating = false`
- Duration: sustained (1+ hours)

**Upstairs needs to heat:**
- Outdoor temp very cold
- Indoor temp dips below 63°F OR `is_heating = true`
- Indicates rising heat is insufficient

### Calibration Method
When we observe upstairs `is_heating = true`:
1. Note the actual outdoor temp at that moment
2. Calculate what heat_rise_factor would make adjusted = 63°F

```python
# If upstairs kicks on at 40°F outdoor:
factor = (63 - 40) / (65 - 40)  # = 0.92
```

### Confounding Factors
- **Thermal mass:** House retains heat from warmer periods
- **Other heat sources:** Cooking, appliances, body heat
- **Solar gain:** Daytime sun through windows (not applicable at night)

---

## Current Billing Period Tracking

### Meter Readings (Dec 11, 2025 - present)
| Date/Time | Reading | CCF Used |
|-----------|---------|----------|
| Dec 11 (start) | 1339 | - |
| Jan 7 10pm | 1408 | 69 (cumulative) |
| Jan 8 7am | 1409 | 1 (overnight) |
| Jan 8 5pm | 1410 | 1 (daytime) |

### January 2026 Bill Projection
- **Estimated total CCF:** 85-90
- **Estimated bill:** $96-101

---

## Files

| File | Purpose |
|------|---------|
| `thermostat_collector.py` | Main data collection script |
| `log_meter.py` | CLI for logging gas meter readings |
| `run_collector.bat` | Batch file for Task Scheduler |
| `.env` | Environment variables (credentials) |
| `.gitignore` | Excludes .env and other files from git |
| `requirements.txt` | Python dependencies |

---

## Next Steps

1. **Collect overnight data** (Jan 8-9) to observe heating patterns
2. **Calibrate heat_rise_factor** based on when upstairs kicks on
3. **Validate 0.12 CCF/HDD factor** with more meter readings
4. **Build prediction model** for monthly bills based on weather forecast
5. **Create dashboard/visualization** of temperature vs. gas usage

---

## Data Sources

- **Thermostat data:** Honeywell Total Connect Comfort API via [pyhtcc](https://github.com/csm10495/pyhtcc)
- **Outdoor temperature:** Honeywell (pulls from weather service based on zip code)
- **Weather forecasts:** [National Weather Service](https://forecast.weather.gov)
- **Historical weather:** [TimeAndDate.com](https://www.timeanddate.com/weather/usa/bowling-green/historic)
