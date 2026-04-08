#!/usr/bin/env python3
"""
Reparent cameras from /World/kart/ to /World/kart/Body/ so they move
with the rigid body during physics simulation.

Also updates CameraGraph render product references to the new paths.

Does NOT touch: /World/drive, /World/lidar, /World/kart/World_LivoxHAP
"""

import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom

STAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "stage", "progress3_latest.usd")

# Cameras to reparent
CAMERAS = [
    "OAK_D_RGB",
    "OAK_D_Left",
    "OAK_D_Right",
    "OAK_D_Depth",
    "ZED2_Left",
    "ZED2_Right",
    "ZED2_Depth",
]

# CameraGraph render product node → camera name mapping
RENDER_NODES = {
    "RenderOAKRGB": "OAK_D_RGB",
    "RenderOAKLeft": "OAK_D_Left",
    "RenderOAKRight": "OAK_D_Right",
    "RenderOAKDepth": "OAK_D_Depth",
    "RenderZEDLeft": "ZED2_Left",
    "RenderZEDRight": "ZED2_Right",
    "RenderZEDDepth": "ZED2_Depth",
}


def reparent_cameras(stage):
    """Move camera prims from /World/kart/ to /World/kart/Body/"""
    print("\n=== Reparenting cameras to /World/kart/Body ===")

    edit = Sdf.BatchNamespaceEdit()

    for cam_name in CAMERAS:
        old_path = Sdf.Path(f"/World/kart/{cam_name}")
        new_path = Sdf.Path(f"/World/kart/Body/{cam_name}")

        prim = stage.GetPrimAtPath(str(old_path))
        if not prim:
            print(f"  WARN: {old_path} not found, skipping")
            continue

        edit.Add(old_path, new_path)
        print(f"  {old_path} -> {new_path}")

    # Apply all reparent operations atomically
    layer = stage.GetEditTarget().GetLayer()
    result = layer.Apply(edit)
    if not result:
        print("  ERROR: Batch reparent failed!")
        return False

    print("  Reparent: DONE")
    return True


def update_camera_graph_refs(stage):
    """Update CameraGraph render product nodes to point to new camera paths"""
    print("\n=== Updating CameraGraph references ===")

    for node_name, cam_name in RENDER_NODES.items():
        node_path = f"/World/CameraGraph/{node_name}"
        node_prim = stage.GetPrimAtPath(node_path)
        if not node_prim:
            print(f"  WARN: {node_path} not found")
            continue

        # Update the cameraPrim relationship
        rel = node_prim.GetRelationship("inputs:cameraPrim")
        if rel:
            old_targets = [str(t) for t in rel.GetTargets()]
            new_target = Sdf.Path(f"/World/kart/Body/{cam_name}")
            rel.SetTargets([new_target])
            print(f"  {node_name}.cameraPrim: {old_targets} -> [{new_target}]")
        else:
            print(f"  WARN: {node_name} has no inputs:cameraPrim relationship")

    print("  CameraGraph refs: DONE")
    return True


def verify(stage):
    """Verify cameras are under Body and graph refs point correctly"""
    print("\n=== Verification ===")
    ok = True

    for cam_name in CAMERAS:
        new_path = f"/World/kart/Body/{cam_name}"
        old_path = f"/World/kart/{cam_name}"

        new_prim = stage.GetPrimAtPath(new_path)
        old_prim = stage.GetPrimAtPath(old_path)

        if new_prim and new_prim.IsValid():
            print(f"  OK: {new_path} exists [{new_prim.GetTypeName()}]")
        else:
            print(f"  FAIL: {new_path} missing!")
            ok = False

        if old_prim and old_prim.IsValid():
            print(f"  FAIL: {old_path} still exists (should have been moved)")
            ok = False

    for node_name, cam_name in RENDER_NODES.items():
        node_path = f"/World/CameraGraph/{node_name}"
        node_prim = stage.GetPrimAtPath(node_path)
        if node_prim:
            rel = node_prim.GetRelationship("inputs:cameraPrim")
            if rel:
                targets = [str(t) for t in rel.GetTargets()]
                expected = f"/World/kart/Body/{cam_name}"
                if expected in targets:
                    print(f"  OK: {node_name}.cameraPrim -> {expected}")
                else:
                    print(f"  FAIL: {node_name}.cameraPrim -> {targets} (expected {expected})")
                    ok = False

    return ok


def main():
    stage_path = os.path.abspath(STAGE_PATH)
    print(f"Opening stage: {stage_path}")

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("ERROR: Failed to open stage!")
        sys.exit(1)

    ok = reparent_cameras(stage)
    if ok:
        ok = update_camera_graph_refs(stage)

    if ok:
        ok = verify(stage)

    if ok:
        stage.Save()
        print(f"\nStage saved successfully: {stage_path}")
    else:
        print("\nErrors found — stage NOT saved")
        sys.exit(1)


if __name__ == "__main__":
    main()
