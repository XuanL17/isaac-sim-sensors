# Docker — full simulation stack

This stack reproduces the project environment on any suitable Linux PC with an **NVIDIA GPU**, **Docker**, and the **NVIDIA Container Toolkit**:

- **Isaac Sim** from the official NGC image (`nvcr.io/nvidia/isaac-sim`)
- **ROS 2** (Humble on Ubuntu 22.04 / Isaac 4.5.x, or Jazzy on Ubuntu 24.04 / newer images)
- **RViz2** and CLI tools (`ros2 topic`, …)
- This repository bind-mounted at **`/workspace/repo`** (stage, scripts, assets)

It follows the same cache volume layout as [NVIDIA’s container guide](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_container.html).

## Prerequisites

1. **NVIDIA driver** — see [Isaac Sim requirements](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/requirements.html).
2. **Docker** + **NVIDIA Container Toolkit** — same guide, “Container Setup”.
3. **NGC / nvcr.io access** — create an API key, then:

   ```bash
   docker login nvcr.io
   # Username: $oauthtoken
   # Password: <your NGC API key>
   ```

4. **Pull the base image once** (optional but avoids surprises during `docker compose build`):

   ```bash
   docker pull nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION:-4.5.0}
   ```

## Build and enter the environment

From the **repository root** (parent of `docker/`):

```bash
cp -n .env.example .env   # optional
docker compose build
docker compose run --rm -it av4ev-sim
```

Inside the container you should have:

- Isaac Sim under **`/isaac-sim`** (NGC default layout)
- ROS 2 sourced automatically via **`/entrypoint.sh`**
- Project files at **`/workspace/repo`**

## Isaac Sim (headless + streaming)

The NGC image is oriented toward **headless** operation and **WebRTC / livestream** clients. From inside the container (after `docker compose run …`):

```bash
cd /isaac-sim
./runheadless.sh -v
```

Wait until logs indicate the streaming app is ready, then connect with the **Isaac Sim WebRTC Streaming Client** from a machine that can reach the host (see NVIDIA “manual livestream clients” for your Isaac version).

Open your stage from the streamed UI, or use Isaac batch/headless USD loading as documented by NVIDIA for your version.

## ROS 2 and RViz2

With **`network_mode: host`**, DDS uses the host stack; keep one ROS domain ID on the machine to avoid cross-talk.

In the **same** container session (ROS is already sourced by the entrypoint):

```bash
# List topics while Isaac is publishing over the ROS 2 bridge
ros2 topic list

# RViz2 (needs a display: see “GUI / RViz2 on the host” below)
rviz2
```

## GPS bridge (`NavSatFix`)

With Isaac running and its ROS bridge publishing `atlas/odometry`, in a **second** terminal on the host:

```bash
docker compose run --rm -it av4ev-sim gps-bridge
```

`gps-bridge` is a small wrapper that runs `/workspace/repo/scripts/gps_bridge.py` with the correct ROS distribution sourced.

Override the project path if you mount elsewhere:

```bash
docker compose run --rm -it -e ISAAC_SIM_PROJECT=/workspace/repo av4ev-sim gps-bridge
```

ROS parameters (origins, topics) work as usual, for example:

```bash
docker compose run --rm -it av4ev-sim ros2 run --prefix '' ...
```

(Prefer `gps-bridge` unless you install this repo as a ROS package.)

## GUI / RViz2 with an X server

Headless Isaac is the well-supported path in Docker. For **RViz2** or other X11 apps from the same container:

1. On the host: `xhost +local:root` (understand the security implications).
2. Run compose with extra bind mounts and `DISPLAY`, for example:

   ```bash
   docker compose run --rm -it \
     -e DISPLAY=$DISPLAY \
     -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
     av4ev-sim rviz2
   ```

Native **Isaac Sim full GUI** inside Docker is possible on some setups but is not covered here; use the workstation install or NVIDIA’s streaming workflow for the most reliable experience.

## Changing the Isaac Sim version

Set **`ISAAC_SIM_VERSION`** in `.env` or export it before `build`. The Dockerfile selects **ROS Humble** vs **Jazzy** from the base image’s Ubuntu codename (`/etc/os-release`).

## In-viewport GPS HUD (`isaac_gps_hud.py`)

That script runs **inside Isaac’s Kit Python** from the Script Editor; use it with a **local or workstation** Isaac install, or any environment where you can open the Script Editor in the running app. It is not invoked by this Docker entrypoint.

## Troubleshooting

| Issue | Suggestion |
|--------|------------|
| `unauthorized` pulling `nvcr.io/...` | Run `docker login nvcr.io` with an NGC API key. |
| `Unsupported Ubuntu codename` during build | Your Isaac tag uses an OS we did not map; extend the `case` block in `docker/Dockerfile`. |
| No GPU in container | Install/configure [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) and use `gpus: all` (already in `docker-compose.yml`). |
| ROS 2 cannot see Isaac topics | Use `network_mode: host`, align `ROS_DOMAIN_ID`, and ensure Isaac’s ROS bridge is enabled in the stage. |
