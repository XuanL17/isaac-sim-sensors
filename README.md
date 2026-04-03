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
| Point One Nav Atlas | GPS (via odom) | Bridge script | `atlas/odometry` → `atlas/fix` |

## Directory Structure

```
├── kart/                   # Go-kart 3D models (FBX + USD)
├── track/                  # Purdue track models + textures
├── stage/                  # USD scene files
│   ├── progress3 (copy).usd   # ← Active working scene
│   ├── progress3.usd          # Previous checkpoint
│   ├── progress2.usd
│   ├── progress1.usd
│   ├── Lidarprogress1.usd
│   └── rew.usd
└── scripts/
    ├── steering.py         # Vehicle control (WIP)
    ├── gps_bridge.py       # ROS2: odom → NavSatFix converter
    ├── patch_sensors.py    # USD patcher: LiDAR/camera config fixes
    ├── patch_cameras.py    # USD patcher: reparent cameras to Body
    └── revert_lidar.py     # USD patcher: revert LiDAR to ROTARY
```

## Scene Hierarchy (`progress3 (copy).usd`)

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
# Open: ~/Downloads/isaac_sim/stage/progress3 (copy).usd
# Press ▶ Play to start simulation
```

### GPS Bridge (separate terminal)
```bash
# Requires ROS2 Humble/Jazzy
python3 ~/Downloads/isaac_sim/scripts/gps_bridge.py
```

Configurable via ROS2 params:
- `origin_lat` (default: 40.4432 — Purdue track)
- `origin_lon` (default: -86.9427)
- `origin_alt` (default: 190.0m)

### Verify ROS2 Topics
```bash
ros2 topic list
ros2 topic echo /livox/lidar        # LiDAR point cloud
ros2 topic echo /oak/rgb/image_raw  # OAK-D RGB
ros2 topic echo /atlas/odometry     # Odometry
ros2 topic echo /atlas/fix          # GPS NavSatFix (requires gps_bridge.py)
```

## Known Issues

- **LiDAR config**: Livox HAP solid-state config (45,200 emitters) crashes the RTX sensor plugin due to empty emitter arrays in the config JSON. Currently using a generic ROTARY/128-emitter config as workaround.
- **GPS**: No native Isaac Sim NavSatFix publisher — uses external ROS2 bridge script.

## Hardware Reference

| Sensor | Model | Key Specs |
|--------|-------|-----------|
| LiDAR | Livox HAP | Solid-state, 120°×25° FOV, 150m range, 10Hz |
| Camera 1 | OAK-D | RGB (IMX378) + Stereo (OV9282), 75mm baseline |
| Camera 2 | ZED 2 | Stereo 2208×1242, 110° HFOV, 120mm baseline |
| GPS | Point One Nav Atlas | RTK GPS, ~2cm accuracy |
