#!/usr/bin/env python3
"""
Position sensors correctly on the kart based on actual chassis dimensions.

Kart measurements (from mesh extent + Body scale):
  - Chassis: 1.71m long × 1.37m wide × 1.00m tall
  - Wheelbase: 1.11m
  - Track width: ~0.98m
  - Body scale Z = 7.688 (all child Z values multiplied by this)
  - Chassis top (body-local Z) = 0.1141
  - Chassis center Y (body-local) = -0.498

Sensor mounting plan:
  - OAK-D: Front of chassis, centered, just above chassis top (forward-facing)
  - ZED 2: Mid-chassis, centered, just above chassis top (forward-facing)
  - LiDAR: Behind center (roll bar area), centered, highest point

Does NOT touch: /World/drive, OmniGraph wiring, sensor configs
"""

import os
import sys

from pxr import Gf, Usd

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3_latest.usd")

# Body scale Z factor
BODY_SCALE_Z = 7.688377

# Chassis dimensions (body-local coordinates, from mesh extent)
CHASSIS_TOP_Z = 0.1141      # top of chassis mesh
CHASSIS_FRONT_X = 1.1576    # front edge
CHASSIS_REAR_X = -0.5531    # rear edge
CHASSIS_CENTER_Y = -0.498   # centerline of chassis

# Sensor Z offsets above chassis top (body-local, gets multiplied by 7.688)
CAM_Z = CHASSIS_TOP_Z + 0.005    # 0.1191 → ~0.04m real above chassis top
LIDAR_Z = CHASSIS_TOP_Z + 0.013  # 0.1271 → ~0.10m real above chassis top

# --- OAK-D: front-mounted, forward-facing ---
# Slightly inset from front edge, centered on chassis
OAK_X = CHASSIS_FRONT_X - 0.05   # 1.108 body-local
OAK_Y_CENTER = CHASSIS_CENTER_Y  # chassis centerline
OAK_BASELINE = 0.075             # 75mm stereo baseline

# --- ZED 2: mid-chassis, forward-facing ---
ZED_X = (CHASSIS_FRONT_X + CHASSIS_REAR_X) / 2 + 0.15  # slightly forward of center
ZED_Y_CENTER = CHASSIS_CENTER_Y
ZED_BASELINE = 0.12              # 120mm stereo baseline

# --- LiDAR: roll bar area, highest point ---
LIDAR_X = (CHASSIS_FRONT_X + CHASSIS_REAR_X) / 2 - 0.1  # behind center
LIDAR_Y = CHASSIS_CENTER_Y


def fix_positions(stage):
    """Set sensor positions based on real kart geometry."""
    print("\n=== Fixing sensor positions based on chassis dimensions ===")
    print(f"  Chassis: front X={CHASSIS_FRONT_X:.3f}, rear X={CHASSIS_REAR_X:.3f}")
    print(f"  Chassis: top Z={CHASSIS_TOP_Z:.4f} (real {CHASSIS_TOP_Z*BODY_SCALE_Z:.2f}m)")
    print(f"  Chassis: center Y={CHASSIS_CENTER_Y:.3f}")
    print()

    positions = {
        # OAK-D cameras: front of kart
        "/World/kart/Body/OAK_D_RGB": Gf.Vec3d(
            OAK_X, OAK_Y_CENTER, CAM_Z
        ),
        "/World/kart/Body/OAK_D_Left": Gf.Vec3d(
            OAK_X, OAK_Y_CENTER - OAK_BASELINE / 2, CAM_Z
        ),
        "/World/kart/Body/OAK_D_Right": Gf.Vec3d(
            OAK_X, OAK_Y_CENTER + OAK_BASELINE / 2, CAM_Z
        ),
        "/World/kart/Body/OAK_D_Depth": Gf.Vec3d(
            OAK_X, OAK_Y_CENTER, CAM_Z
        ),

        # ZED 2 cameras: mid-chassis
        "/World/kart/Body/ZED2_Left": Gf.Vec3d(
            ZED_X, ZED_Y_CENTER + ZED_BASELINE / 2, CAM_Z
        ),
        "/World/kart/Body/ZED2_Right": Gf.Vec3d(
            ZED_X, ZED_Y_CENTER - ZED_BASELINE / 2, CAM_Z
        ),
        "/World/kart/Body/ZED2_Depth": Gf.Vec3d(
            ZED_X, ZED_Y_CENTER + ZED_BASELINE / 2, CAM_Z  # co-located with left
        ),

        # LiDAR: roll bar area
        "/World/kart/Body/World_LivoxHAP": Gf.Vec3d(
            LIDAR_X, LIDAR_Y, LIDAR_Z
        ),
    }

    for prim_path, new_pos in positions.items():
        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            print(f"  WARN: {prim_path} not found")
            continue

        attr = prim.GetAttribute("xformOp:translate")
        if attr:
            old = attr.Get()
            attr.Set(new_pos)
            name = prim_path.split("/")[-1]
            real_z = new_pos[2] * BODY_SCALE_Z
            print(f"  {name:20s} ({old[0]:.3f}, {old[1]:.3f}, {old[2]:.4f}) -> "
                  f"({new_pos[0]:.3f}, {new_pos[1]:.3f}, {new_pos[2]:.4f})  "
                  f"[real Z: {real_z:.2f}m]")

    return True


def verify(stage):
    """Print final sensor layout for review."""
    print("\n=== Final Sensor Layout ===")
    print(f"{'Sensor':<20s} {'X (local)':<12s} {'Y (local)':<12s} {'Z (real m)':<12s} {'Mount'}")
    print("-" * 72)

    sensors = [
        ("/World/kart/Body/OAK_D_RGB", "Front"),
        ("/World/kart/Body/OAK_D_Left", "Front-L"),
        ("/World/kart/Body/OAK_D_Right", "Front-R"),
        ("/World/kart/Body/OAK_D_Depth", "Front"),
        ("/World/kart/Body/ZED2_Left", "Mid-L"),
        ("/World/kart/Body/ZED2_Right", "Mid-R"),
        ("/World/kart/Body/ZED2_Depth", "Mid-L"),
        ("/World/kart/Body/World_LivoxHAP", "Roll bar"),
    ]

    for path, mount in sensors:
        prim = stage.GetPrimAtPath(path)
        if prim:
            t = prim.GetAttribute("xformOp:translate").Get()
            name = path.split("/")[-1]
            real_z = t[2] * BODY_SCALE_Z
            print(f"  {name:<20s} {t[0]:<12.3f} {t[1]:<12.3f} {real_z:<12.2f} {mount}")

    return True


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    ok = fix_positions(stage)
    if ok:
        ok = verify(stage)

    if ok:
        stage.Save()
        print(f"\nStage saved: {stage_path}")
    else:
        print("\nErrors — stage NOT saved")
        sys.exit(1)


if __name__ == "__main__":
    main()
