"""
Configuration – edit these values for your criteria.
"""

# Target high-growth ZIP codes in Fulton County / metro Atlanta
HIGH_GROWTH_ZIPS = {
    "30305", "30306", "30307", "30308", "30309",
    "30312", "30316", "30317", "30318", "30319",
    "30324", "30326", "30327", "30328", "30338",
    "30339", "30342", "30346", "30350",
    # Add or remove as needed
}

# Minimum assessed value (USD) to even consider flagging
MIN_ASSESSED_FOR_FLAG = 250_000

# If original principal is known, flag when assessed_value / principal >= this ratio
EQUITY_RATIO_THRESHOLD = 1.5

# How many days back to look for new notices
LOOKBACK_DAYS = 14
