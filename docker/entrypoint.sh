#!/usr/bin/env bash
set -euo pipefail

RD=$(cat /etc/av4ev-ros-distro)
# shellcheck source=/dev/null
source "/opt/ros/${RD}/setup.bash"
export ROS_DISTRO="${RD}"

export ISAAC_SIM_PROJECT="${ISAAC_SIM_PROJECT:-/workspace/repo}"

exec "$@"
