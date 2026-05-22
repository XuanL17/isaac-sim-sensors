# ROS 2 — `auto_drive` package

Autonomy nodes for AV4EV Isaac Sim: lane follow (camera), GPS waypoint follow, and command fusion.

## Build

```bash
cd ~/Downloads/isaac_sim/ros2
source /opt/ros/humble/setup.bash   # or jazzy
colcon build --packages-select auto_drive
source install/setup.bash
```

Inside the Docker stack (`docker compose run …`), the same paths apply under `/workspace/repo/ros2`.

## Prerequisites

- Isaac Sim playing with ROS bridge enabled (cameras, `atlas/odometry`).
- **GPS bridge** publishing `atlas/fix` (see main [README](../README.md#gps)):

  ```bash
  python3 ~/Downloads/isaac_sim/scripts/gps_bridge.py
  # or: docker compose run --rm -it av4ev-sim gps-bridge
  ```

## Run (three terminals)

```bash
source install/setup.bash

# 1) Camera lane follow → camera_cmd
ros2 run auto_drive lane_follow_node

# 2) GPS waypoint follow → gps_cmd (uses atlas/fix + atlas/odometry)
ros2 run auto_drive gps_waypoint_follower

# 3) Fuse camera + GPS → ackermann_cmd (70% / 30% steer, speed from GPS)
ros2 run auto_drive cmd_arbiter
```

Wire the fused `/ackermann_cmd` into your vehicle controller (OmniGraph Ackermann subscriber or bridge) as needed for your stage.

## Topics

| Node | Subscribes | Publishes |
|------|------------|-----------|
| `lane_follow_node` | `oak/rgb/image_raw` | `camera_cmd` |
| `gps_waypoint_follower` | `atlas/fix`, `atlas/odometry` | `gps_cmd` |
| `cmd_arbiter` | `camera_cmd`, `gps_cmd` | `ackermann_cmd` |

Parameters are overridable, e.g. `ros2 run auto_drive lane_follow_node --ros-args -p image_topic:=/oak/rgb/image_raw`.

## Waypoints

Default file: `auto_drive/waypoints/track_waypoints.json` (installed to share). Coordinates are **placeholders** around the Purdue origin used by `gps_bridge.py` — replace with surveyed track GPS before on-track use.
