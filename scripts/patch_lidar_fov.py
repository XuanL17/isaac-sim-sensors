#!/usr/bin/env python3
"""
Fix LiDAR FOV, reparent LiDAR to Body, and lower all sensor Z positions.

1. LiDAR FOV: 360° → 120° (validAzimuth -60 to +60)
2. Reparent LiDAR from /World/kart → /World/kart/Body
3. Lower camera/lidar Z to account for Body scale Z=7.688

Does NOT touch: /World/drive, camera wiring, camera orientations/focal lengths
"""

import os
import sys

from pxr import Gf, Sdf, Usd

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3 (copy).usd")


def fix_lidar_fov(stage):
    """Limit LiDAR azimuth from 360° to 120° (-60 to +60)"""
    print("\n=== Fixing LiDAR FOV: 360° → 120° ===")
    prim = stage.GetPrimAtPath("/World/kart/World_LivoxHAP")
    if not prim:
        print("  ERROR: LiDAR prim not found at /World/kart/World_LivoxHAP")
        # Try under Body in case already reparented
        prim = stage.GetPrimAtPath("/World/kart/Body/World_LivoxHAP")
        if not prim:
            print("  ERROR: LiDAR prim not found under Body either!")
            return False

    fov_fixes = {
        "omni:sensor:Core:validStartAzimuthDeg": -60.0,
        "omni:sensor:Core:validEndAzimuthDeg": 60.0,
    }

    for attr_name, new_val in fov_fixes.items():
        attr = prim.GetAttribute(attr_name)
        if attr:
            old = attr.Get()
            attr.Set(new_val)
            print(f"  {attr_name}: {old} -> {new_val}")
        else:
            print(f"  WARN: {attr_name} not found")

    print("  LiDAR FOV: DONE")
    return True


def reparent_lidar(stage):
    """Move LiDAR from /World/kart/ to /World/kart/Body/"""
    print("\n=== Reparenting LiDAR to /World/kart/Body ===")

    old_path = Sdf.Path("/World/kart/World_LivoxHAP")
    new_path = Sdf.Path("/World/kart/Body/World_LivoxHAP")

    prim = stage.GetPrimAtPath(str(old_path))
    if not prim:
        # Check if already under Body
        prim = stage.GetPrimAtPath(str(new_path))
        if prim:
            print("  LiDAR already under Body, skipping reparent")
            return True
        print("  ERROR: LiDAR prim not found!")
        return False

    edit = Sdf.BatchNamespaceEdit()
    edit.Add(old_path, new_path)

    layer = stage.GetEditTarget().GetLayer()
    result = layer.Apply(edit)
    if not result:
        print("  ERROR: Reparent failed!")
        return False

    print(f"  {old_path} -> {new_path}")

    # Update lidar graph reference
    render_node = stage.GetPrimAtPath("/World/lidar/isaac_create_render_product")
    if render_node:
        rel = render_node.GetRelationship("inputs:cameraPrim")
        if rel:
            old_targets = [str(t) for t in rel.GetTargets()]
            rel.SetTargets([new_path])
            print(f"  lidar graph cameraPrim: {old_targets} -> [{new_path}]")

    print("  LiDAR reparent: DONE")
    return True


def lower_sensor_positions(stage):
    """
    Lower sensor Z positions to account for Body scale Z=7.688.

    Body scale Z = 7.688, so local Z gets multiplied.
    Target real-world heights:
      Cameras: ~0.15m above chassis → local Z = 0.15 / 7.688 ≈ 0.02
      LiDAR:   ~0.30m above chassis → local Z = 0.30 / 7.688 ≈ 0.04
    """
    print("\n=== Lowering sensor Z positions ===")

    # Cameras (all under Body now)
    camera_paths = [
        "/World/kart/Body/OAK_D_RGB",
        "/World/kart/Body/OAK_D_Left",
        "/World/kart/Body/OAK_D_Right",
        "/World/kart/Body/OAK_D_Depth",
        "/World/kart/Body/ZED2_Left",
        "/World/kart/Body/ZED2_Right",
        "/World/kart/Body/ZED2_Depth",
    ]

    camera_z = 0.02  # ~0.15m real-world
    lidar_z = 0.04   # ~0.30m real-world

    for cam_path in camera_paths:
        prim = stage.GetPrimAtPath(cam_path)
        if not prim:
            print(f"  WARN: {cam_path} not found")
            continue

        attr = prim.GetAttribute("xformOp:translate")
        if attr:
            old = attr.Get()
            new_pos = Gf.Vec3d(old[0], old[1], camera_z)
            attr.Set(new_pos)
            name = cam_path.split("/")[-1]
            print(f"  {name}: Z {old[2]:.3f} -> {camera_z} (real ~{camera_z * 7.688:.2f}m)")

    # LiDAR (now under Body)
    lidar_prim = stage.GetPrimAtPath("/World/kart/Body/World_LivoxHAP")
    if lidar_prim:
        attr = lidar_prim.GetAttribute("xformOp:translate")
        if attr:
            old = attr.Get()
            new_pos = Gf.Vec3d(old[0], old[1], lidar_z)
            attr.Set(new_pos)
            print(f"  World_LivoxHAP: Z {old[2]:.3f} -> {lidar_z} (real ~{lidar_z * 7.688:.2f}m)")

    print("  Sensor positions: DONE")
    return True


def verify(stage):
    """Verify all changes"""
    print("\n=== Verification ===")
    ok = True

    # LiDAR under Body
    lidar = stage.GetPrimAtPath("/World/kart/Body/World_LivoxHAP")
    if lidar and lidar.IsValid():
        print("  OK: LiDAR under Body")

        start_az = lidar.GetAttribute("omni:sensor:Core:validStartAzimuthDeg").Get()
        end_az = lidar.GetAttribute("omni:sensor:Core:validEndAzimuthDeg").Get()
        fov = end_az - start_az
        print(f"  OK: LiDAR FOV = {fov}° ({start_az}° to {end_az}°)")
        if abs(fov - 120.0) > 0.1:
            print(f"  FAIL: Expected 120° FOV, got {fov}°")
            ok = False
    else:
        print("  FAIL: LiDAR not found under Body")
        ok = False

    # Lidar graph ref
    render_node = stage.GetPrimAtPath("/World/lidar/isaac_create_render_product")
    if render_node:
        rel = render_node.GetRelationship("inputs:cameraPrim")
        targets = [str(t) for t in rel.GetTargets()]
        if "/World/kart/Body/World_LivoxHAP" in targets:
            print("  OK: Lidar graph ref updated")
        else:
            print(f"  FAIL: Lidar graph ref = {targets}")
            ok = False

    # Sensor Z values
    for path in [
        "/World/kart/Body/OAK_D_RGB",
        "/World/kart/Body/ZED2_Left",
        "/World/kart/Body/World_LivoxHAP",
    ]:
        prim = stage.GetPrimAtPath(path)
        if prim:
            z = prim.GetAttribute("xformOp:translate").Get()[2]
            name = path.split("/")[-1]
            real_z = z * 7.688
            print(f"  OK: {name} Z={z:.3f} (real ~{real_z:.2f}m)")
            if real_z > 1.0:
                print(f"  FAIL: {name} still too high ({real_z:.2f}m)")
                ok = False

    return ok


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    ok = fix_lidar_fov(stage)
    if ok:
        ok = reparent_lidar(stage)
    if ok:
        ok = lower_sensor_positions(stage)
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
