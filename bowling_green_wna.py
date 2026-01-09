"""
Atmos Energy Kentucky - Bowling Green WNA Calculator
Based on KY PSC Case 2021-00214 and November 2025 Tariff

WNA = R x (HSF x (NDD - ADD)) / (BL + (HSF x ADD))

Sign behavior:
  - Colder than normal (ADD > NDD) -> negative WNA (CREDIT to customer)
  - Warmer than normal (ADD < NDD) -> positive WNA (SURCHARGE to customer)

WNA only applies November-April billing cycles.

Sources:
  - KY PSC Case 2021-00214: Staff_3-09_Att1_-_Residential_WNA_Customer.xlsx
  - Kentucky Tariff November 2025, Sheet No. 4
"""

# =============================================================================
# KENTUCKY G-1 RESIDENTIAL PARAMETERS (from KY PSC Case 2021-00214)
# =============================================================================

# Values from Staff_3-09_Att1_-_Residential_WNA_Customer.xlsx "WNA Calc" sheet
# HSF and BL are stated in Ccf terms in the filing

KY_RESIDENTIAL = {
    "R": 1.6261,         # $/Mcf - Distribution rate from Nov 2025 tariff (Sheet 4)
    "R_ccf": 0.16261,    # $/Ccf - Same rate per Ccf (1 Mcf = 10 Ccf)
    "HSF": 0.12576,      # Heat Sensitivity Factor (Ccf basis)
    "HSF_mcf": 0.012576, # HSF per Mcf (divided by 10)
    "BL": 10.556,        # Base Load (Ccf basis)
    "BL_mcf": 1.0556,    # BL per Mcf (divided by 10)
}

# Bowling Green likely uses Nashville weather station (south-central KY)
WEATHER_STATION = "Nashville"

# Normal HDD (NDD) by billing cycle - based on 20-year NOAA average
# Back-calculated from actual bills
# Key: (start_month, end_month) approximate billing cycle
NDD_BY_CYCLE = {
    # Billing cycle: (approx start, approx end) -> NDD
    ("Oct", "Nov"): 210.5,   # 10/14-11/12 cycle, 30 days
    ("Nov", "Dec"): 587.0,   # 11/13-12/11 cycle, 29 days
    ("Dec", "Jan"): None,    # TBD
    ("Jan", "Feb"): None,    # TBD
    ("Feb", "Mar"): None,    # TBD
    ("Mar", "Apr"): None,    # TBD
}

# Daily NDD rate (for estimating other cycles)
# Oct-Nov: 210.5 / 30 days = 7.0 HDD/day
# Nov-Dec: 587.0 / 29 days = 20.2 HDD/day

# Monthly base charge
BASE_CHARGE_MONTHLY = 25.00  # $/month for G-1 Residential

# Additional riders (tuned from actual Nov 2025 bill)
RIDERS = {
    "PRP": 0.8214,    # Pipeline Replacement Program $/Mcf (from actual bill: $4.60 / 5.6 Mcf)
    # R&D: not shown as separate line item on bill - may be bundled or not applicable
    # PM: $0.00 - not shown on bill
}


def calculate_wna_factor_mcf(R, HSF, BL, NDD, ADD):
    """
    Calculate Weather Normalization Adjustment Factor (WNAF) in $/Mcf

    All inputs should be in Mcf basis.
    Returns: WNAF in $/Mcf
    """
    if NDD == ADD:
        return 0.0

    numerator = HSF * (NDD - ADD)
    denominator = BL + (HSF * ADD)

    if denominator == 0:
        return 0.0

    wnaf = R * (numerator / denominator)
    return wnaf


def calculate_wna_factor_ccf(R_ccf, HSF, BL, NDD, ADD):
    """
    Calculate Weather Normalization Adjustment Factor (WNAF) in $/Ccf

    HSF and BL should be in Ccf basis.
    Returns: WNAF in $/Ccf
    """
    if NDD == ADD:
        return 0.0

    numerator = HSF * (NDD - ADD)
    denominator = BL + (HSF * ADD)

    if denominator == 0:
        return 0.0

    wnaf = R_ccf * (numerator / denominator)
    return wnaf


def calculate_bill(usage_mcf, NDD, ADD, winter_month=True):
    """
    Calculate distribution portion of bill for Bowling Green, KY G-1 Residential

    usage_mcf: Gas usage in Mcf (as shown on bill)
    NDD: Normal Heating Degree Days for billing cycle
    ADD: Actual Heating Degree Days for billing cycle
    winter_month: True if November-April (WNA applies)

    Returns: dict with bill components
    """
    params = KY_RESIDENTIAL

    # Base charge
    base_charge = BASE_CHARGE_MONTHLY

    # Distribution charge (volumetric) - tiered rates from tariff:
    #   First 300 Mcf (3,000 Ccf)   @ $1.6261/Mcf
    #   Next 14,700 Mcf             @ $1.1390/Mcf
    #   Over 15,000 Mcf             @ $0.9817/Mcf
    # Residential never exceeds first tier - only large commercial/industrial would
    distribution_rate = params["R"]  # $1.6261/Mcf
    distribution_volumetric = usage_mcf * distribution_rate

    # WNA calculation (only in winter months)
    if winter_month:
        wnaf = calculate_wna_factor_mcf(
            params["R"],
            params["HSF_mcf"],
            params["BL_mcf"],
            NDD,
            ADD
        )
        wna_amount = wnaf * usage_mcf
    else:
        wnaf = 0.0
        wna_amount = 0.0

    # Additional riders
    prp_amount = usage_mcf * RIDERS["PRP"]
    total_riders = prp_amount

    # Total distribution = base + volumetric + WNA + riders
    total_distribution = base_charge + distribution_volumetric + wna_amount + total_riders

    # Determine weather impact
    if ADD > NDD:
        weather_status = "COLDER than normal"
        wna_effect = "CREDIT (bill reduced)"
    elif ADD < NDD:
        weather_status = "WARMER than normal"
        wna_effect = "SURCHARGE (bill increased)"
    else:
        weather_status = "NORMAL weather"
        wna_effect = "No adjustment"

    return {
        "usage_mcf": usage_mcf,
        "usage_ccf": usage_mcf * 10,
        "base_charge": round(base_charge, 2),
        "distribution_volumetric": round(distribution_volumetric, 2),
        "wnaf_per_mcf": round(wnaf, 6),
        "wna_amount": round(wna_amount, 2),
        "prp_amount": round(prp_amount, 2),
        "total_distribution": round(total_distribution, 2),
        "NDD": NDD,
        "ADD": ADD,
        "HDD_difference": ADD - NDD,
        "weather_status": weather_status,
        "wna_effect": wna_effect,
    }


def print_bill_summary(result):
    """Pretty print bill calculation results"""
    print("\n" + "=" * 60)
    print("BOWLING GREEN, KY - G-1 RESIDENTIAL BILL ESTIMATE")
    print("=" * 60)
    print(f"Weather Station: {WEATHER_STATION}")
    print("-" * 60)
    print(f"Usage:                    {result['usage_mcf']:.3f} Mcf ({result['usage_ccf']:.1f} Ccf)")
    print(f"Normal HDD (NDD):         {result['NDD']}")
    print(f"Actual HDD (ADD):         {result['ADD']}")
    print(f"HDD Difference:           {result['HDD_difference']:+d} ({result['weather_status']})")
    print("-" * 60)
    print("DISTRIBUTION CHARGES:")
    print(f"  Base Charge:            ${result['base_charge']:.2f}")
    print(f"  Volumetric:             ${result['distribution_volumetric']:.2f}")
    print(f"  WNA Factor:             ${result['wnaf_per_mcf']:.6f}/Mcf")
    print(f"  WNA Adjustment:         ${result['wna_amount']:+.2f} ({result['wna_effect']})")
    print("-" * 60)
    print("RIDERS:")
    print(f"  PRP (Pipeline Repl):    ${result['prp_amount']:.2f}")
    print("-" * 60)
    print(f"  TOTAL DISTRIBUTION:     ${result['total_distribution']:.2f}")
    print("=" * 60)
    print("\nNote: This is distribution only. Gas cost (GCA) is additional.")


# =============================================================================
# EXAMPLE / INTERACTIVE MODE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Atmos Energy Kentucky - Bowling Green WNA Calculator")
    print("=" * 60)
    print(f"\nParameters (tuned from actual Nov 2025 bill):")
    print(f"  R (Distribution Rate):  ${KY_RESIDENTIAL['R']:.4f}/Mcf")
    print(f"  HSF (Heat Sensitivity): {KY_RESIDENTIAL['HSF_mcf']:.6f}")
    print(f"  BL (Base Load):         {KY_RESIDENTIAL['BL_mcf']:.4f}")
    print(f"  Base Charge:            ${BASE_CHARGE_MONTHLY:.2f}/month")
    print(f"  PRP:                    ${RIDERS['PRP']:.4f}/Mcf")
    print(f"  Weather Station:        {WEATHER_STATION}")

    # Example calculations for different weather scenarios
    print("\n" + "=" * 60)
    print("EXAMPLE CALCULATIONS (5 Mcf / 50 Ccf usage)")
    print("=" * 60)

    usage = 5.0  # Mcf - typical winter month

    # Scenario 1: Normal weather
    print("\n--- Scenario 1: Normal Weather (NDD = ADD = 600) ---")
    result = calculate_bill(usage, NDD=600, ADD=600)
    print(f"  Base + Volumetric:      ${result['base_charge'] + result['distribution_volumetric']:.2f}")
    print(f"  WNA:                    ${result['wna_amount']:+.2f}")
    print(f"  PRP:                    ${result['prp_amount']:.2f}")
    print(f"  Total Distribution:     ${result['total_distribution']:.2f}")

    # Scenario 2: Colder than normal
    print("\n--- Scenario 2: Colder Than Normal (NDD=600, ADD=750) ---")
    result = calculate_bill(usage, NDD=600, ADD=750)
    print(f"  Base + Volumetric:      ${result['base_charge'] + result['distribution_volumetric']:.2f}")
    print(f"  WNA:                    ${result['wna_amount']:+.2f} (CREDIT)")
    print(f"  PRP:                    ${result['prp_amount']:.2f}")
    print(f"  Total Distribution:     ${result['total_distribution']:.2f}")

    # Scenario 3: Warmer than normal
    print("\n--- Scenario 3: Warmer Than Normal (NDD=600, ADD=450) ---")
    result = calculate_bill(usage, NDD=600, ADD=450)
    print(f"  Base + Volumetric:      ${result['base_charge'] + result['distribution_volumetric']:.2f}")
    print(f"  WNA:                    ${result['wna_amount']:+.2f} (SURCHARGE)")
    print(f"  PRP:                    ${result['prp_amount']:.2f}")
    print(f"  Total Distribution:     ${result['total_distribution']:.2f}")

    # Interactive mode
    print("\n" + "=" * 60)
    print("CALCULATE YOUR BILL")
    print("=" * 60)

    try:
        usage_input = input("\nEnter your usage in Mcf (or press Enter for 5.0): ").strip()
        usage = float(usage_input) if usage_input else 5.0

        ndd_input = input("Enter Normal HDD for your billing cycle (or Enter for 600): ").strip()
        ndd = float(ndd_input) if ndd_input else 600

        add_input = input("Enter Actual HDD for your billing cycle (or Enter for 600): ").strip()
        add = float(add_input) if add_input else 600

        result = calculate_bill(usage, ndd, add)
        print_bill_summary(result)

    except ValueError as e:
        print(f"Invalid input: {e}")
    except KeyboardInterrupt:
        print("\n\nExiting...")
