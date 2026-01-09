"""
Estimate HDD and WNA for December 2025 bill
Billing period: 12/12/25 - 1/13/26
"""

# Actual weather data (12/12 - 1/6)
weather_actual = {
    # December 2025
    "12/12": (48, 34),
    "12/13": (41, 30),
    "12/14": (26, 14),
    "12/15": (37, 10),
    "12/16": (48, 34),
    "12/17": (55, 48),
    "12/18": (61, 43),
    "12/19": (46, 34),
    "12/20": (61, 26),
    "12/21": (52, 28),
    "12/22": (61, 26),
    "12/23": (66, 57),
    "12/24": (70, 61),
    "12/25": (68, 61),
    "12/26": (68, 60),
    "12/27": (70, 59),
    "12/28": (75, 48),
    "12/29": (46, 30),
    "12/30": (36, 25),
    "12/31": (48, 32),
    # January 2026 (actual through 1/6)
    "01/01": (55, 28),
    "01/02": (43, 33),
    "01/03": (48, 35),
    "01/04": (48, 25),
    "01/05": (63, 27),
    "01/06": (66, 48),
}

# Estimate for 1/7-1/8 (recent days - assume similar to recent pattern)
weather_estimated = {
    "01/07": (55, 35),  # Estimate
    "01/08": (50, 30),  # Estimate
}

# Future days 1/9-1/13: assume NDD = ADD (normal weather)
# These contribute 0 to the WNA calculation
# But we still need to count them for total cycle HDD
# Use ~25 HDD/day for mid-January normal
future_days = {
    "01/09": "normal",
    "01/10": "normal",
    "01/11": "normal",
    "01/12": "normal",
    "01/13": "normal",
}

print("=" * 70)
print("HDD ESTIMATE: Billing Period 12/12/25 - 1/13/26")
print("=" * 70)

# Calculate actual HDD
actual_hdd = 0
print(f"\n{'Date':<8} {'High':>6} {'Low':>6} {'Avg':>6} {'HDD':>6} {'Type':<10}")
print("-" * 50)

for date, (high, low) in weather_actual.items():
    avg = (high + low) / 2
    hdd = max(0, 65 - avg)
    actual_hdd += hdd
    print(f"{date:<8} {high:>6} {low:>6} {avg:>6.1f} {hdd:>6.1f} {'Actual':<10}")

for date, (high, low) in weather_estimated.items():
    avg = (high + low) / 2
    hdd = max(0, 65 - avg)
    actual_hdd += hdd
    print(f"{date:<8} {high:>6} {low:>6} {avg:>6.1f} {hdd:>6.1f} {'Estimated':<10}")

# For future days, we assume normal (NDD = ADD for those days)
# So they don't affect the WNA calculation
# But for total ADD count, use approximate normal daily HDD
jan_normal_daily_hdd = 25  # Approximate for mid-January
future_hdd = len(future_days) * jan_normal_daily_hdd

for date in future_days:
    print(f"{date:<8} {'--':>6} {'--':>6} {'--':>6} {jan_normal_daily_hdd:>6.1f} {'Normal':<10}")

print("-" * 50)
print(f"Actual/Estimated HDD (12/12-1/8):  {actual_hdd:.1f}")
print(f"Future days HDD (1/9-1/13):        {future_hdd:.1f} (assumed normal)")
print(f"Total ADD for cycle:               {actual_hdd + future_hdd:.1f}")
print(f"Days in billing cycle:             {len(weather_actual) + len(weather_estimated) + len(future_days)}")

# Estimate NDD for Dec-Jan cycle
# Based on Nov-Dec cycle: 587 NDD / 29 days = 20.2 HDD/day
# Dec-Jan should be colder, estimate ~22-25 HDD/day
# 33 days × 24 HDD/day = 792 NDD (rough estimate)
estimated_ndd_daily = 24
total_days = len(weather_actual) + len(weather_estimated) + len(future_days)
estimated_ndd = total_days * estimated_ndd_daily

print(f"\n" + "=" * 70)
print("WNA ESTIMATE")
print("=" * 70)

R = 1.6261
HSF = 0.012576
BL = 1.0556

# The key insight: future days (1/9-1/13) are assumed NDD=ADD
# So only the actual/estimated days (12/12-1/8) contribute to WNA
# WNA is based on: (NDD - ADD) for the actual period

# For actual period (12/12 - 1/8): 28 days
actual_days = len(weather_actual) + len(weather_estimated)
actual_period_ndd = actual_days * estimated_ndd_daily

print(f"\nActual period (12/12 - 1/8): {actual_days} days")
print(f"  Actual ADD:     {actual_hdd:.1f}")
print(f"  Estimated NDD:  {actual_period_ndd:.1f} ({estimated_ndd_daily} HDD/day)")
print(f"  Difference:     {actual_period_ndd - actual_hdd:.1f}")

# Calculate WNAF for actual period
ADD = actual_hdd
NDD = actual_period_ndd

if BL + (HSF * ADD) != 0:
    wnaf = R * (HSF * (NDD - ADD)) / (BL + (HSF * ADD))
else:
    wnaf = 0

print(f"\nWNA Factor: ${wnaf:.6f}/Mcf")

if NDD > ADD:
    print(f"--> Weather was WARMER than normal (ADD {ADD:.0f} < NDD {NDD:.0f})")
    print(f"    Expect WNA SURCHARGE")
else:
    print(f"--> Weather was COLDER than normal (ADD {ADD:.0f} > NDD {NDD:.0f})")
    print(f"    Expect WNA CREDIT")

# Estimate bill impact for different usage levels
print(f"\n" + "=" * 70)
print("ESTIMATED BILL IMPACT")
print("=" * 70)

effective_rate_ccf = (R + wnaf) / 10

print(f"\nBase dist rate:      $0.16261/Ccf")
print(f"Effective dist rate: ${effective_rate_ccf:.5f}/Ccf")
print(f"WNA adjustment:      ${wnaf/10:.5f}/Ccf")

print(f"\n{'Usage (Ccf)':<12} {'Dist Charge':<14} {'WNA':<10} {'PRP':<10} {'Total Dist':<12}")
print("-" * 60)
for ccf in [40, 50, 60, 70, 80, 100]:
    mcf = ccf / 10
    base_dist = 25 + (mcf * R)
    wna = mcf * wnaf
    prp = mcf * 0.8214
    total = base_dist + wna + prp
    print(f"{ccf:<12} ${base_dist:<13.2f} ${wna:<9.2f} ${prp:<9.2f} ${total:<11.2f}")
