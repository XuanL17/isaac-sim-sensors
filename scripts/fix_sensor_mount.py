#!/usr/bin/env python3
"""
Fix camera black images caused by Body's non-uniform scale (1, 1, 7.688).

Creates a SensorMount Xform under Body with inverse Z-scale to cancel
the distortion. Reparents all sensors under SensorMount. Recalculates
sensor positions in the new coordinate space (where Z is no longer scaled).

Hierarchy after fix:
  /World/kart/Body [scale: 1, 1, 7.688]
    /World/kart/Body/SensorMount [scale: 1, 1, 0.13 = 1/7.688]
      /World/kart/Body/SensorMount/OAK_D_RGB
      /World/kart/Body/SensorMount/...
      /World/kart/Body/SensorMount/World_LivoxHAP

The net scale on sensors = Body(7.688) × SensorMount(0.13) = ~1.0

Does NOT touch: /World/drive, joints, mesh
"""

import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3_latest.usd")

BODY_SCALE_Z = 7.688377
INVERSE_Z = 1.0 / BODY_SCALE_Z  # 0.13007...

# Sensors to move
SENSORS = [
    "OAK_D_RGB",
    "OAK_D_Left",
    "OAK_D_Right",
    "OAK_D_Depth",
    "ZED2_Left",
    "ZED2_Right",
    "ZED2_Depth",
    "World_LivoxHAP",
]

# Chassis dimensions (body-local, Z already scaled by 7.688)
# We need positions in SensorMount space where Z is real meters
CHASSIS_TOP_REAL = 0.1141 * BODY_SCALE_Z  # ~0.877m real above body origin

# Real-world sensor positions (meters, relative to body origin)
# X and Y are same as before (Body X/Y scale is ~1.0)
# Z is now in real meters (SensorMount cancels the scale)
CHASSIS_FRONT_X = 1.1576
CHASSIS_CENTER_Y = -0.498

OAK_X = CHASSIS_FRONT_X - 0.05
OAK_BASELINE = 0.075
ZED_X = (CHASSIS_FRONT_X + (-0.5531)) / 2 + 0.15
ZED_BASELINE = 0.12
LIDAR_X = (CHASSIS_FRONT_X + (-0.5531)) / 2 - 0.1

# Heights in real meters above body origin
CAM_HEIGHT = CHASSIS_TOP_REAL + 0.04   # 4cm above chassis top
LIDAR_HEIGHT = CHASSIS_TOP_REAL + 0.10  # 10cm above chassis top

POSITIONS = {
    "OAK_D_RGB":       Gf.Vec3d(OAK_X, CHASSIS_CENTER_Y, CAM_HEIGHT),
    "OAK_D_Left":      Gf.Vec3d(OAK_X, CHASSIS_CENTER_Y - OAK_BASELINE/2, CAM_HEIGHT),
    "OAK_D_Right":     Gf.Vec3d(OAK_X, CHASSIS_CENTER_Y + OAK_BASELINE/2, CAM_HEIGHT),
    "OAK_D_Depth":     Gf.Vec3d(OAK_X, CHASSIS_CENTER_Y, CAM_HEIGHT),
    "ZED2_Left":       Gf.Vec3d(ZED_X, CHASSIS_CENTER_Y + ZED_BASELINE/2, CAM_HEIGHT),
    "ZED2_Right":      Gf.Vec3d(ZED_X, CHASSIS_CENTER_Y - ZED_BASELINE/2, CAM_HEIGHT),
    "ZED2_Depth":      Gf.Vec3d(ZED_X, CHASSIS_CENTER_Y + ZED_BASELINE/2, CAM_HEIGHT),
    "World_LivoxHAP":  Gf.Vec3d(LIDAR_X, CHASSIS_CENTER_Y, LIDAR_HEIGHT),
}

# CameraGraph + lidar graph references to update
GRAPH_REFS = {
    "/World/CameraGraph/RenderOAKRGB": "OAK_D_RGB",
    "/World/CameraGraph/RenderOAKLeft": "OAK_D_Left",
    "/World/CameraGraph/RenderOAKRight": "OAK_D_Right",
    "/World/CameraGraph/RenderOAKDepth": "OAK_D_Depth",
    "/World/CameraGraph/RenderZEDLeft": "ZED2_Left",
    "/World/CameraGraph/RenderZEDRight": "ZED2_Right",
    "/World/CameraGraph/RenderZEDDepth": "ZED2_Depth",
    "/World/lidar/isaac_create_render_product": "World_LivoxHAP",
}


def create_sensor_mount(stage):
    """Create SensorMount Xform under Body with inverse Z-scale."""
    print("\n=== Creating SensorMount Xform ===")

    mount_path = "/World/kart/Body/SensorMount"
    mount_prim = stage.GetPrimAtPath(mount_path)
    if mount_prim and mount_prim.IsValid():
        print(f"  SensorMount already exists, skipping creation")
        return True

    mount = UsdGeom.Xform.Define(stage, mount_path)
    mount.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0))
    mount.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, INVERSE_Z))

    print(f"  Created {mount_path} with scale (1, 1, {INVERSE_Z:.6f})")
    print(f"  Net Z-scale on sensors: {BODY_SCALE_Z} × {INVERSE_Z:.6f} = {BODY_SCALE_Z * INVERSE_Z:.6f}")
    return True


def reparent_sensors(stage):
    """Move all sensors from Body/ to Body/SensorMount/"""
    print("\n=== Reparenting sensors to SensorMount ===")

    edit = Sdf.BatchNamespaceEdit()
    moved = 0

    for name in SENSORS:
        old_path = Sdf.Path(f"/World/kart/Body/{name}")
        new_path = Sdf.Path(f"/World/kart/Body/SensorMount/{name}")

        prim = stage.GetPrimAtPath(str(old_path))
        if not prim:
            # Maybe already under SensorMount
            prim = stage.GetPrimAtPath(str(new_path))
            if prim:
                print(f"  {name}: already under SensorMount")
                continue
            print(f"  WARN: {name} not found")
            continue

        edit.Add(old_path, new_path)
        print(f"  {old_path} -> {new_path}")
        moved += 1

    if moved > 0:
        layer = stage.GetEditTarget().GetLayer()
        result = layer.Apply(edit)
        if not result:
            print("  ERROR: Reparent failed!")
            return False

    print(f"  Reparented {moved} sensors")
    return True


def fix_positions(stage):
    """Set sensor positions in SensorMount space (real meters, no Z-scale distortion)."""
    print("\n=== Setting sensor positions (real meters) ===")
    print(f"  Chassis top: {CHASSIS_TOP_REAL:.2f}m")
    print(f"  Camera height: {CAM_HEIGHT:.2f}m, LiDAR height: {LIDAR_HEIGHT:.2f}m")
    print()

    for name, pos in POSITIONS.items():
        prim_path = f"/World/kart/Body/SensorMount/{name}"
        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            print(f"  WARN: {prim_path} not found")
            continue

        attr = prim.GetAttribute("xformOp:translate")
        if attr:
            old = attr.Get()
            attr.Set(pos)
            print(f"  {name:20s} -> ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})m")

    return True


def update_graph_refs(stage):
    """Update CameraGraph and lidar graph cameraPrim refs to new SensorMount paths."""
    print("\n=== Updating OmniGraph references ===")

    for node_path, sensor_name in GRAPH_REFS.items():
        node_prim = stage.GetPrimAtPath(node_path)
        if not node_prim:
            print(f"  WARN: {node_path} not found")
            continue

        rel = node_prim.GetRelationship("inputs:cameraPrim")
        if rel:
            new_target = Sdf.Path(f"/World/kart/Body/SensorMount/{sensor_name}")
            old_targets = [str(t) for t in rel.GetTargets()]
            rel.SetTargets([new_target])
            node_name = node_path.split("/")[-1]
            print(f"  {node_name}: {old_targets[0] if old_targets else '?'} -> {new_target}")

    return True


def verify(stage):
    """Verify everything is correct."""
    print("\n=== Verification ===")
    ok = True

    # SensorMount exists with correct scale
    mount = stage.GetPrimAtPath("/World/kart/Body/SensorMount")
    if mount:
        scale = mount.GetAttribute("xformOp:scale").Get()
        print(f"  OK: SensorMount scale = {scale}")
    else:
        print("  FAIL: SensorMount missing")
        ok = False

    # All sensors under SensorMount
    for name in SENSORS:
        prim = stage.GetPrimAtPath(f"/World/kart/Body/SensorMount/{name}")
        if prim and prim.IsValid():
            t = prim.GetAttribute("xformOp:translate").Get()
            print(f"  OK: {name} at ({t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f})m")
        else:
            print(f"  FAIL: {name} not under SensorMount")
            ok = False

    # Graph refs
    for node_path, sensor_name in GRAPH_REFS.items():
        node_prim = stage.GetPrimAtPath(node_path)
        if node_prim:
            rel = node_prim.GetRelationship("inputs:cameraPrim")
            targets = [str(t) for t in rel.GetTargets()]
            expected = f"/World/kart/Body/SensorMount/{sensor_name}"
            if expected in targets:
                pass  # ok
            else:
                print(f"  FAIL: {node_path.split('/')[-1]} -> {targets}")
                ok = False

    return ok


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    ok = create_sensor_mount(stage)
    if ok:
        ok = reparent_sensors(stage)
    if ok:
        ok = fix_positions(stage)
    if ok:
        ok = update_graph_refs(stage)
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
