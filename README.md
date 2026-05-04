# Isaac Sim — AV4EV Autonomous Go-Kart

Simulation environment for the AV4EV autonomous electric go-kart on the Purdue Grand Prix track using NVIDIA Isaac Sim.

## Sensors

| Sensor | Type | Status | ROS2 Topic |
|--------|------|--------|------------|
| Livox HAP | LiDAR (RTX) | Working | `livox/lidar` |
| OAK-D RGB | Camera | Working | `oak/rgb/image_raw` |
| OAK-D Stereo L/R | Camera (stereo) | Working | `oak/left/image_rect`, `oak/right/image_rect` |
| OAK-D Depth | Camera (depth) | Working | `oak/stereo/depth` |
| ZED 2 Stereo L/R | Camera (stereo) | Working | `zed2/zed_node/left/image_rect_color`, `zed2/zed_node/right/image_rect_color` |
| ZED 2 Depth | Camera (depth) | Working | `zed2/zed_node/depth/depth_registered` |
| Point One Nav Atlas | GPS (via odom) | ROS bridge + optional Isaac HUD | `atlas/odometry` → `atlas/fix`; see **GPS** below |

## Directory Structure

```
├── kart/                   # Go-kart 3D models (FBX + USD)
├── track/                  # Purdue track models + textures
├── stage/                  # USD scene files
│   ├── progress3_latest.usd   # ← Active working scene
│   ├── progress3.usd          # Previous checkpoint
│   ├── progress2.usd
│   ├── progress1.usd
│   ├── Lidarprogress1.usd
│   └── rew.usd
└── scripts/
    ├── steering.py         # Vehicle control (WIP)
    ├── gps_bridge.py       # ROS2: odom → NavSatFix (self-contained, no extra modules)
    ├── isaac_gps_hud.py    # Isaac Sim: viewport overlay for lat/lon/alt (Script Editor)
    ├── patch_sensors.py    # USD patcher: LiDAR/camera config fixes
    ├── patch_cameras.py    # USD patcher: reparent cameras to Body
    ├── patch_lidar_fov.py  # USD patcher: LiDAR FOV 120°, reparent, lower heights
    └── revert_lidar.py     # USD patcher: revert LiDAR to ROTARY
```

## Scene Hierarchy (`progress3_latest.usd`)

```
/World
├── PhysicsScene
├── GroundPlane
├── kart [ArticulationRoot]
│   ├── Body [RigidBody]
│   │   ├── Cube_043 (chassis mesh)
│   │   ├── FL/FR/RL/RR (wheel joints)
│   │   ├── FL_steering/FR_steering
│   │   ├── OAK_D_RGB, OAK_D_Left, OAK_D_Right, OAK_D_Depth
│   │   ├── ZED2_Left, ZED2_Right, ZED2_Depth
│   │   └── (LiDAR attached here in GUI)
│   ├── wheel_FL/FR/RL/RR [RigidBody]
│   ├── FL_knuckle, FR_knuckle [RigidBody]
│   └── World_LivoxHAP [OmniLidar]
├── purdue_track
├── drive [OmniGraph — Ackermann keyboard controller]
├── lidar [OmniGraph — RTX LiDAR → ROS2]
├── CameraGraph [OmniGraph — 7 cameras → ROS2]
└── GPSGraph [OmniGraph — odometry → ROS2]
```

## Running

### Isaac Sim (GUI)
```bash
cd ~/isaac-sim
./isaac-sim.sh
# Open: ~/Downloads/isaac_sim/stage/progress3_latest.usd
# Press ▶ Play to start simulation
```

### GPS

Isaac Sim does not publish `sensor_msgs/NavSatFix` from the OmniGraph by default. This repo uses a small ROS 2 node plus an optional in-sim overlay (same general idea as the GNSS HUD in [autoware_off-road_sim](https://github.com/autowarefoundation/autoware_off-road_sim)).

#### ROS 2 bridge (separate terminal)

```bash
# Requires ROS 2 Humble/Jazzy and a sourced workspace if applicable
python3 ~/Downloads/isaac_sim/scripts/gps_bridge.py
```

`gps_bridge.py` is self-contained (WGS-84 conversion and defaults live in the file). Parameters:

- `origin_lat` (default: 40.4432 — Purdue track)
- `origin_lon` (default: -86.9427)
- `origin_alt` (default: 190.0 m)
- `odom_topic` (default: `atlas/odometry`)
- `fix_topic` (default: `atlas/fix`)

#### In-viewport readout (Isaac Sim)

After opening the stage, run **`scripts/isaac_gps_hud.py`** from **Window → Script Editor** (Open file → Run). That creates an `omni.ui` overlay with latitude, longitude, and altitude from the world pose of **`/World/kart/Body`** using the same ENU→WGS-84 math as the bridge.

Optional: `show_gps_hud(body_prim_path="...", origin_lat=..., origin_lon=..., origin_alt=...)` if your chassis prim or map origin differs. Call `stop_gps_hud()` before starting again.

**Note:** The HUD uses the Body prim’s **world** position. If your `atlas/odometry` frame differs from world coordinates, tune the prim path or origins so the HUD matches `/atlas/fix`.

### Verify ROS2 Topics
```bash
ros2 topic list
ros2 topic echo /livox/lidar        # LiDAR point cloud
ros2 topic echo /oak/rgb/image_raw  # OAK-D RGB
ros2 topic echo /atlas/odometry     # Odometry
ros2 topic echo /atlas/fix          # GPS NavSatFix (requires gps_bridge.py)
```

## Known Issues

- **LiDAR config**: Livox HAP solid-state config (45,200 emitters) crashes the RTX sensor plugin due to empty emitter arrays in the config JSON. Using ROTARY/128-emitter with 120° FOV limit as workaround.
- **GPS**: No built-in NavSatFix publisher in the graph — use `gps_bridge.py` for ROS 2 and optionally `isaac_gps_hud.py` for an on-screen readout in Isaac Sim.

## Hardware Reference

| Sensor | Model | Key Specs |
|--------|-------|-----------|
| LiDAR | Livox HAP | Solid-state, 120°×25° FOV, 150m range, 10Hz |
| Camera 1 | OAK-D | RGB (IMX378) + Stereo (OV9282), 75mm baseline |
| Camera 2 | ZED 2 | Stereo 2208×1242, 110° HFOV, 120mm baseline |
| GPS | Point One Nav Atlas | RTK GPS, ~2cm accuracy |
