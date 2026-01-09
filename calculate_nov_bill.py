"""
Calculate actual HDD and WNA for November 2025 bill
Billing period: 11/13/25 - 12/11/25
Usage: 56 Ccf = 5.6 Mcf
"""

# Weather data from timeanddate.com for Bowling Green, KY
# Format: (high, low) in Fahrenheit

weather_data = {
    # November 2025 (13-30)
    "11/13": (66, 41),
    "11/14": (75, 39),
    "11/15": (77, 60),
    "11/16": (69, 51),
    "11/17": (62, 32),
    "11/18": (71, 51),
    "11/19": (64, 60),
    "11/20": (59, 53),
    "11/21": (69, 57),
    "11/22": (60, 48),
    "11/23": (60, 42),
    "11/24": (62, 46),
    "11/25": (66, 60),
    "11/26": (59, 37),
    "11/27": (44, 30),
    "11/28": (39, 26),
    "11/29": (48, 26),
    "11/30": (46, 28),
    # December 2025 (1-11)
    "12/01": (42, 23),
    "12/02": (33, 26),
    "12/03": (35, 26),
    "12/04": (35, 32),
    "12/05": (35, 33),
    "12/06": (39, 33),
    "12/07": (46, 33),
    "12/08": (41, 30),
    "12/09": (48, 26),
    "12/10": (48, 35),
    "12/11": (39, 26),
}

print("=" * 70)
print("HDD CALCULATION: Billing Period 11/13/25 - 12/11/25")
print("=" * 70)

total_hdd = 0
daily_details = []

for date, (high, low) in weather_data.items():
    avg_temp = (high + low) / 2
    hdd = max(0, 65 - avg_temp)  # HDD = 0 if avg >= 65
    total_hdd += hdd
    daily_details.append((date, high, low, avg_temp, hdd))

print(f"\n{'Date':<8} {'High':>6} {'Low':>6} {'Avg':>6} {'HDD':>6}")
print("-" * 40)
for date, high, low, avg, hdd in daily_details:
    print(f"{date:<8} {high:>6} {low:>6} {avg:>6.1f} {hdd:>6.1f}")

print("-" * 40)
print(f"{'TOTAL ADD (Actual HDD):':<26} {total_hdd:>6.1f}")
print(f"{'Days in billing cycle:':<26} {len(weather_data):>6}")

# Now calculate WNA
print("\n" + "=" * 70)
print("WNA CALCULATION")
print("=" * 70)

# Parameters from tuned model
R = 1.6261       # $/Mcf distribution rate
HSF = 0.012576   # Heat sensitivity factor (Mcf basis)
BL = 1.0556      # Base load (Mcf basis)
usage_mcf = 5.6  # 56 Ccf = 5.6 Mcf

ADD = total_hdd  # Actual HDD we just calculated

# We need NDD (Normal HDD) - estimate based on 20-year NOAA average
# For late Nov - early Dec in Bowling Green, typical normal is around 18-22 HDD/day
# 29 days × ~20 HDD/day = ~580 NDD (rough estimate)
# Let's try a few NDD values to see what matches the bill

print(f"\nActual HDD (ADD): {ADD:.1f}")
print(f"Usage: {usage_mcf} Mcf ({usage_mcf * 10} Ccf)")
print(f"\nR = ${R}/Mcf, HSF = {HSF}, BL = {BL}")

print("\n--- Testing different NDD values ---")
print(f"{'NDD':<8} {'WNAF ($/Mcf)':<14} {'WNA Total':<12} {'Dist Rate':<12}")
print("-" * 50)

for ndd in [500, 520, 540, 555, 560, 580, 600, 620]:
    if BL + (HSF * ADD) != 0:
        wnaf = R * (HSF * (ndd - ADD)) / (BL + (HSF * ADD))
    else:
        wnaf = 0
    wna_total = wnaf * usage_mcf

    # Distribution rate = (base distribution + WNA) / usage
    # Base distribution per Mcf = $1.6261
    # Effective rate per Ccf = (R + WNAF) / 10
    effective_rate_ccf = (R + wnaf) / 10

    print(f"{ndd:<8} ${wnaf:<13.6f} ${wna_total:<11.2f} ${effective_rate_ccf:.8f}/Ccf")

# From bill: Distribution Charge = 56 CCF @ $0.16821429/CCF = $9.42
# Base rate = $0.16261/Ccf
# Difference = $0.16821429 - $0.16261 = $0.00560429/Ccf
# This difference × 56 Ccf = $0.31 WNA

print("\n" + "=" * 70)
print("BILL COMPARISON")
print("=" * 70)
bill_dist_rate = 0.16821429
bill_dist_total = 9.42
base_rate_ccf = 0.16261
implied_wna_per_ccf = bill_dist_rate - base_rate_ccf
implied_wna_total = implied_wna_per_ccf * 56

print(f"\nFrom actual bill:")
print(f"  Distribution rate:     ${bill_dist_rate:.8f}/Ccf")
print(f"  Distribution total:    ${bill_dist_total:.2f}")
print(f"  Base rate (tariff):    ${base_rate_ccf:.5f}/Ccf")
print(f"  Implied WNA per Ccf:   ${implied_wna_per_ccf:.8f}")
print(f"  Implied WNA total:     ${implied_wna_total:.2f}")

# Back-calculate NDD from implied WNA
# WNAF = R × (HSF × (NDD - ADD)) / (BL + (HSF × ADD))
# Solve for NDD:
# WNAF × (BL + HSF × ADD) = R × HSF × (NDD - ADD)
# WNAF × (BL + HSF × ADD) / (R × HSF) = NDD - ADD
# NDD = ADD + WNAF × (BL + HSF × ADD) / (R × HSF)

implied_wnaf_mcf = implied_wna_per_ccf * 10  # Convert to $/Mcf
calculated_ndd = ADD + (implied_wnaf_mcf * (BL + HSF * ADD)) / (R * HSF)

print(f"\nBack-calculated NDD from bill: {calculated_ndd:.1f}")
print(f"Actual ADD:                    {ADD:.1f}")
print(f"Difference (NDD - ADD):        {calculated_ndd - ADD:.1f}")

if calculated_ndd > ADD:
    print(f"\n--> Weather was WARMER than normal (ADD < NDD)")
    print(f"    Result: WNA SURCHARGE of ${implied_wna_total:.2f}")
else:
    print(f"\n--> Weather was COLDER than normal (ADD > NDD)")
    print(f"    Result: WNA CREDIT of ${abs(implied_wna_total):.2f}")
