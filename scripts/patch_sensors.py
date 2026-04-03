#!/usr/bin/env python3
"""
Patch sensor prims in progress3 (copy).usd
Fixes: Livox HAP LiDAR, OAK-D cameras, ZED 2 cameras
Does NOT touch /World/drive or any OmniGraph wiring (already correct)
"""

import json
import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3 (copy).usd")
LIVOX_JSON = "/home/tritonai/isaac-sim/exts/omni.sensors.nv.lidar/data/sensors/lidar/Livox_HAP.json"


def load_livox_config():
    with open(LIVOX_JSON, "r") as f:
        return json.load(f)


def fix_livox_hap(stage):
    """
    Fix LiDAR: change from ROTARY/128 emitters to solidState per real Livox HAP spec.
    Real specs: solid-state, 45200 emitters, 0.5-150m range, 120°x25° FOV, 905nm, 10Hz
    """
    print("\n=== Fixing Livox HAP LiDAR ===")
    prim = stage.GetPrimAtPath("/World/kart/World_LivoxHAP")
    if not prim:
        print("  ERROR: LiDAR prim not found!")
        return False

    config = load_livox_config()
    profile = config["profile"]

    # Core scan parameters — switch from ROTARY to solidState
    fixes = {
        "omni:sensor:Core:scanType": "SOLIDSTATE",
        "omni:sensor:Core:nearRangeM": profile["nearRangeM"],        # 0.5
        "omni:sensor:Core:farRangeM": profile["farRangeM"],          # 150.0
        "omni:sensor:Core:numberOfEmitters": profile["numberOfEmitters"],  # 45200
        "omni:sensor:Core:reportRateBaseHz": profile["reportRateBaseHz"],  # 10
        "omni:sensor:Core:scanRateBaseHz": profile["scanRateBaseHz"],      # 10
        "omni:sensor:Core:rangeResolutionM": profile["rangeResolutionM"],  # 0.02
        "omni:sensor:Core:rangeAccuracyM": profile["rangeAccuracyM"],      # 0.02
        "omni:sensor:Core:avgPowerW": profile["avgPowerW"],                # 8.0
        "omni:sensor:Core:waveLengthNm": profile["wavelengthNm"],          # 905.0
        "omni:sensor:Core:pulseTimeNs": profile["pulseTimeNs"],            # 5
        "omni:sensor:Core:maxReturns": profile["reportNumReturns"],        # 2
        "omni:sensor:Core:minReflectance": profile["minReflectance"],      # 0.1
        "omni:sensor:Core:minReflectionRangeM": profile["minReflectanceRange"],  # 150.0
        "omni:sensor:Core:intensityProcessing": "NORMALIZATION",
        "omni:sensor:Core:rayType": "IDEALIZED",
        "omni:sensor:modelName": "Livox_HAP",
        "omni:sensor:modelVendor": "Livox",
        "omni:sensor:marketName": "HAP",
    }

    for attr_name, value in fixes.items():
        attr = prim.GetAttribute(attr_name)
        if attr:
            old_val = attr.Get()
            attr.Set(value)
            print(f"  {attr_name}: {old_val} -> {value}")
        else:
            print(f"  WARN: attribute {attr_name} not found on prim")

    # Clear the ROTARY emitter arrays — solidState uses the config file pattern instead
    # We clear s001 emitter state arrays since they had 128-emitter rotary data
    emitter_arrays = [
        "omni:sensor:Core:emitterState:s001:azimuthDeg",
        "omni:sensor:Core:emitterState:s001:elevationDeg",
        "omni:sensor:Core:emitterState:s001:fireTimeNs",
        "omni:sensor:Core:emitterState:s001:channelId",
    ]
    for arr_name in emitter_arrays:
        attr = prim.GetAttribute(arr_name)
        if attr:
            attr.Clear()
            print(f"  Cleared {arr_name} (solidState uses config file pattern)")

    # Point to the Livox HAP emitter states file
    attr = prim.GetAttribute("omni:sensor:Core:emitterStatesFile")
    if attr:
        attr.Set(LIVOX_JSON)
        print(f"  emitterStatesFile -> {LIVOX_JSON}")

    print("  Livox HAP LiDAR: DONE")
    return True


def fix_oak_d_cameras(stage):
    """
    Fix OAK-D cameras:
    - Real OAK-D specs:
      RGB (IMX378): 4056x3040, 4.81mm focal, 69° HFOV, pixel size 1.55um
      Stereo (OV9282): 1280x800, 2.35mm focal, 89.5° HFOV (global shutter mono)
      Stereo baseline: 75mm (0.075m)
    - Fix stereoRole on Left/Right
    - Fix OAK_D_Depth orientation to match forward-facing
    """
    print("\n=== Fixing OAK-D Cameras ===")

    # Forward-facing quaternion (same as OAK_D_RGB currently uses)
    forward_quat = Gf.Quatd(0.5, 0.5, 0.5, 0.5)

    # --- OAK_D_RGB: verify specs (IMX378 sensor) ---
    # Current: focalLength=3.37, hAperture=5.76, vAperture=3.24
    # Real IMX378: 4.81mm focal, 6.287mm x 4.712mm sensor
    # At Isaac scale these look reasonable for the configured resolution, leave as-is
    rgb = stage.GetPrimAtPath("/World/kart/OAK_D_RGB")
    if rgb:
        print(f"  OAK_D_RGB: focal={rgb.GetAttribute('focalLength').Get()}, keeping (close to spec)")

    # --- OAK_D_Left: set stereoRole ---
    left = stage.GetPrimAtPath("/World/kart/OAK_D_Left")
    if left:
        attr = left.GetAttribute("stereoRole")
        if attr:
            attr.Set("left")
            print("  OAK_D_Left stereoRole: mono -> left")

    # --- OAK_D_Right: set stereoRole ---
    right = stage.GetPrimAtPath("/World/kart/OAK_D_Right")
    if right:
        attr = right.GetAttribute("stereoRole")
        if attr:
            attr.Set("right")
            print("  OAK_D_Right stereoRole: mono -> right")

    # --- OAK_D_Depth: fix orientation to forward-facing ---
    depth = stage.GetPrimAtPath("/World/kart/OAK_D_Depth")
    if depth:
        orient_attr = depth.GetAttribute("xformOp:orient")
        if orient_attr:
            old = orient_attr.Get()
            orient_attr.Set(forward_quat)
            print(f"  OAK_D_Depth orientation: {old} -> {forward_quat}")

    print("  OAK-D Cameras: DONE")
    return True


def fix_zed2_cameras(stage):
    """
    Fix ZED 2 cameras:
    - Real ZED 2 specs:
      Resolution: 2208x1242 (2.2K), also 1920x1080, 1280x720
      HFOV: 110°, VFOV: 70°
      Focal length: 2.12mm
      Sensor size: ~5.33mm x 3.0mm (from current aperture values — correct)
      Stereo baseline: 120mm (0.12m)
    - Fix ZED2_Right position (Z=7.16 is wrong, should match Left)
    - Fix ZED2_Depth position (at origin, should co-locate with Left)
    - Fix all orientations to forward-facing
    - Set stereoRole
    """
    print("\n=== Fixing ZED 2 Cameras ===")

    forward_quat = Gf.Quatd(0.5, 0.5, 0.5, 0.5)

    # ZED2 mounting position on kart (co-located, offset by baseline in Y)
    # Left at Y=+0.06, Right at Y=-0.06 (120mm baseline centered)
    # Height Z=0.3 (same mounting height as OAK-D)

    # --- ZED2_Left: fix orientation, set stereoRole ---
    left = stage.GetPrimAtPath("/World/kart/ZED2_Left")
    if left:
        orient_attr = left.GetAttribute("xformOp:orient")
        if orient_attr:
            old = orient_attr.Get()
            orient_attr.Set(forward_quat)
            print(f"  ZED2_Left orientation: {old} -> {forward_quat}")

        stereo_attr = left.GetAttribute("stereoRole")
        if stereo_attr:
            stereo_attr.Set("left")
            print("  ZED2_Left stereoRole: mono -> left")

    # --- ZED2_Right: fix position AND orientation, set stereoRole ---
    right = stage.GetPrimAtPath("/World/kart/ZED2_Right")
    if right:
        # Fix position: should be at (0, -0.06, 0.3) — 120mm baseline from left
        translate_attr = right.GetAttribute("xformOp:translate")
        if translate_attr:
            old = translate_attr.Get()
            new_pos = Gf.Vec3d(0.0, -0.06, 0.3)
            translate_attr.Set(new_pos)
            print(f"  ZED2_Right position: {old} -> {new_pos}")

        orient_attr = right.GetAttribute("xformOp:orient")
        if orient_attr:
            old = orient_attr.Get()
            orient_attr.Set(forward_quat)
            print(f"  ZED2_Right orientation: {old} -> {forward_quat}")

        stereo_attr = right.GetAttribute("stereoRole")
        if stereo_attr:
            stereo_attr.Set("right")
            print("  ZED2_Right stereoRole: mono -> right")

    # --- ZED2_Depth: co-locate with Left camera ---
    depth = stage.GetPrimAtPath("/World/kart/ZED2_Depth")
    if depth:
        translate_attr = depth.GetAttribute("xformOp:translate")
        if translate_attr:
            old = translate_attr.Get()
            new_pos = Gf.Vec3d(0.0, 0.06, 0.3)
            translate_attr.Set(new_pos)
            print(f"  ZED2_Depth position: {old} -> {new_pos}")

        orient_attr = depth.GetAttribute("xformOp:orient")
        if orient_attr:
            old = orient_attr.Get()
            orient_attr.Set(forward_quat)
            print(f"  ZED2_Depth orientation: {old} -> {forward_quat}")

    print("  ZED 2 Cameras: DONE")
    return True


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    ok = True
    ok &= fix_livox_hap(stage)
    ok &= fix_oak_d_cameras(stage)
    ok &= fix_zed2_cameras(stage)

    if ok:
        stage.Save()
        print(f"\nStage saved successfully: {stage_path}")
    else:
        print("\nErrors occurred — stage NOT saved")
        sys.exit(1)


if __name__ == "__main__":
    main()
