#!/usr/bin/env python3
"""
Revert LiDAR prim to original ROTARY/128 config that was working.
The SOLIDSTATE/45200 config crashes the RTX sensor plugin because
the Livox_HAP.json has empty emitter arrays.
"""

import os
import sys

from pxr import Usd

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3 (copy).usd")

# Original values from before patch_sensors.py modified them
ORIGINAL_VALUES = {
    "omni:sensor:Core:scanType": "ROTARY",
    "omni:sensor:Core:nearRangeM": 0.3,
    "omni:sensor:Core:farRangeM": 200.0,
    "omni:sensor:Core:numberOfEmitters": 128,
    "omni:sensor:Core:numberOfChannels": 128,
    "omni:sensor:Core:reportRateBaseHz": 36000,
    "omni:sensor:Core:scanRateBaseHz": 10,
    "omni:sensor:Core:rangeResolutionM": 0.004,
    "omni:sensor:Core:rangeAccuracyM": 0.02,
    "omni:sensor:Core:avgPowerW": 0.002,
    "omni:sensor:Core:waveLengthNm": 903.0,
    "omni:sensor:Core:pulseTimeNs": 6,
    "omni:sensor:Core:minReflectionRangeM": 200.0,
    "omni:sensor:Core:intensityProcessing": "NORMALIZATION",
    "omni:sensor:Core:rayType": "IDEALIZED",
    "omni:sensor:modelName": "LidarCore",
    "omni:sensor:modelVendor": "NVIDIA",
    "omni:sensor:marketName": "Generic",
    "omni:sensor:Core:emitterStatesFile": "",
}

# Original emitter arrays (128 emitters, 4 azimuth groups x 32 elevations)
ORIGINAL_AZIMUTH = (
    [-3]*32 + [-1]*32 + [1]*32 + [3]*32
)

ORIGINAL_ELEVATION = [
    -15, -14.19, -13.39, -12.58, -11.77, -10.97, -10.16, -9.35,
    -8.55, -7.74, -6.94, -6.13, -5.32, -4.52, -3.71, -2.9,
    -2.1, -1.29, -0.48, 0.32, 1.13, 1.94, 2.74, 3.55,
    4.35, 5.16, 5.97, 6.77, 7.58, 8.39, 9.19, 10
] * 4

ORIGINAL_FIRE_TIME = (
    [0]*16 + [3500]*16 + [7000]*16 + [10500]*16 +
    [14000]*16 + [17500]*16 + [21000]*16 + [24500]*16
)

ORIGINAL_CHANNEL_ID = list(range(1, 129))


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    prim = stage.GetPrimAtPath("/World/kart/World_LivoxHAP")
    if not prim:
        print("ERROR: LiDAR prim not found!")
        sys.exit(1)

    print("\n=== Reverting LiDAR to original ROTARY config ===")

    for attr_name, value in ORIGINAL_VALUES.items():
        attr = prim.GetAttribute(attr_name)
        if attr:
            old = attr.Get()
            attr.Set(value)
            print(f"  {attr_name}: {old} -> {value}")

    # Restore emitter arrays
    arrays = {
        "omni:sensor:Core:emitterState:s001:azimuthDeg": ORIGINAL_AZIMUTH,
        "omni:sensor:Core:emitterState:s001:elevationDeg": ORIGINAL_ELEVATION,
        "omni:sensor:Core:emitterState:s001:fireTimeNs": ORIGINAL_FIRE_TIME,
        "omni:sensor:Core:emitterState:s001:channelId": ORIGINAL_CHANNEL_ID,
    }
    for attr_name, value in arrays.items():
        attr = prim.GetAttribute(attr_name)
        if attr:
            attr.Set(value)
            print(f"  Restored {attr_name} ({len(value)} values)")
        else:
            print(f"  WARN: {attr_name} not found, creating...")

    stage.Save()
    print(f"\nLiDAR reverted. Stage saved: {stage_path}")


if __name__ == "__main__":
    main()
