"""
Calculate actual HDD and WNA for October 2025 bill
Billing period: 10/14/25 - 11/12/25
Usage: 16 Ccf = 1.6 Mcf
"""

# Weather data from timeanddate.com for Bowling Green, KY
weather_data = {
    # October 2025 (14-31)
    "10/14": (80, 73),
    "10/15": (80, 75),
    "10/16": (78, 71),
    "10/17": (80, 73),
    "10/18": (87, 80),
    "10/19": (78, 66),
    "10/20": (71, 66),
    "10/21": (71, 66),
    "10/22": (66, 60),
    "10/23": (66, 60),
    "10/24": (62, 57),
    "10/25": (68, 62),
    "10/26": (60, 55),
    "10/27": (57, 53),
    "10/28": (62, 59),
    "10/29": (53, 53),
    "10/30": (57, 51),
    "10/31": (60, 55),
    # November 2025 (1-12)
    "11/01": (60, 42),
    "11/02": (51, 44),
    "11/03": (62, 34),
    "11/04": (69, 39),
    "11/05": (73, 51),
    "11/06": (66, 51),
    "11/07": (69, 59),
    "11/08": (69, 57),
    "11/09": (57, 37),
    "11/10": (35, 28),
    "11/11": (50, 26),
    "11/12": (66, 44),
}

print("=" * 70)
print("HDD CALCULATION: Billing Period 10/14/25 - 11/12/25")
print("=" * 70)

total_hdd = 0
daily_details = []

for date, (high, low) in weather_data.items():
    avg_temp = (high + low) / 2
    hdd = max(0, 65 - avg_temp)
    total_hdd += hdd
    daily_details.append((date, high, low, avg_temp, hdd))

print(f"\n{'Date':<8} {'High':>6} {'Low':>6} {'Avg':>6} {'HDD':>6}")
print("-" * 40)
for date, high, low, avg, hdd in daily_details:
    print(f"{date:<8} {high:>6} {low:>6} {avg:>6.1f} {hdd:>6.1f}")

print("-" * 40)
print(f"{'TOTAL ADD (Actual HDD):':<26} {total_hdd:>6.1f}")
print(f"{'Days in billing cycle:':<26} {len(weather_data):>6}")

# WNA Calculation
print("\n" + "=" * 70)
print("WNA CALCULATION")
print("=" * 70)

R = 1.6261
HSF = 0.012576
BL = 1.0556
usage_mcf = 1.6
ADD = total_hdd

# From bill
bill_dist_rate = 0.15625
bill_dist_total = 2.50
base_rate_ccf = 0.16261
implied_wna_per_ccf = bill_dist_rate - base_rate_ccf
implied_wna_total = implied_wna_per_ccf * 16

print(f"\nActual HDD (ADD): {ADD:.1f}")
print(f"Usage: {usage_mcf} Mcf (16 Ccf)")

print(f"\nFrom actual bill:")
print(f"  Distribution rate:     ${bill_dist_rate:.8f}/Ccf")
print(f"  Base rate (tariff):    ${base_rate_ccf:.5f}/Ccf")
print(f"  Implied WNA per Ccf:   ${implied_wna_per_ccf:.8f}")
print(f"  Implied WNA total:     ${implied_wna_total:.2f}")

# Back-calculate NDD
implied_wnaf_mcf = implied_wna_per_ccf * 10
if R * HSF != 0:
    calculated_ndd = ADD + (implied_wnaf_mcf * (BL + HSF * ADD)) / (R * HSF)
else:
    calculated_ndd = ADD

print(f"\nBack-calculated NDD: {calculated_ndd:.1f}")
print(f"Actual ADD:          {ADD:.1f}")
print(f"Difference:          {calculated_ndd - ADD:.1f}")

if calculated_ndd > ADD:
    print(f"\n--> Weather was WARMER than normal (WNA surcharge)")
else:
    print(f"\n--> Weather was COLDER than normal (WNA credit)")

# Verify with model
print("\n" + "=" * 70)
print("MODEL VERIFICATION")
print("=" * 70)

wnaf = R * (HSF * (calculated_ndd - ADD)) / (BL + (HSF * ADD))
wna_total = wnaf * usage_mcf
effective_rate = (R + wnaf) / 10

print(f"\nUsing NDD={calculated_ndd:.1f}, ADD={ADD:.1f}:")
print(f"  WNAF:              ${wnaf:.6f}/Mcf")
print(f"  WNA total:         ${wna_total:.2f}")
print(f"  Model dist rate:   ${effective_rate:.8f}/Ccf")
print(f"  Bill dist rate:    ${bill_dist_rate:.8f}/Ccf")

# PRP check
prp_bill = 1.31
prp_rate = prp_bill / usage_mcf
print(f"\nPRP rate from bill: ${prp_rate:.4f}/Mcf (model: $0.8214/Mcf)")
