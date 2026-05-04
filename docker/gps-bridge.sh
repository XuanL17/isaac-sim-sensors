#!/usr/bin/env bash
set -euo pipefail
RD=$(cat /etc/av4ev-ros-distro)
# shellcheck source=/dev/null
source "/opt/ros/${RD}/setup.bash"
ROOT="${ISAAC_SIM_PROJECT:-/workspace/repo}"
exec python3 "${ROOT}/scripts/gps_bridge.py" "$@"
