# AV4EV Isaac Sim + ROS 2 + RViz2 + helpers for gps_bridge in-container.
# Base: https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_container.html
#
# Build (requires: docker login nvcr.io with NGC API key):
#   docker compose build
#
# Args:
#   ISAAC_SIM_VERSION — NGC tag (default 4.5.0). Must match an image whose Ubuntu
#                       codename is jammy (Humble) or noble (Jazzy).

ARG ISAAC_SIM_VERSION=4.5.0
FROM nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION}

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        locales \
        curl \
        gnupg2 \
        lsb-release \
        software-properties-common \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# ROS 2: Humble on Ubuntu 22.04 (jammy), Jazzy on Ubuntu 24.04 (noble)
RUN set -eux; \
    . /etc/os-release; \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu ${VERSION_CODENAME} main" \
        > /etc/apt/sources.list.d/ros2.list; \
    apt-get update; \
    case "${VERSION_CODENAME}" in \
      jammy) \
        apt-get install -y --no-install-recommends ros-humble-ros-base ros-humble-rviz2 ros-dev-tools; \
        echo humble > /etc/av4ev-ros-distro \
        ;; \
      noble) \
        apt-get install -y --no-install-recommends ros-jazzy-ros-base ros-jazzy-rviz2 ros-dev-tools; \
        echo jazzy > /etc/av4ev-ros-distro \
        ;; \
      *) \
        echo "Unsupported Ubuntu codename '${VERSION_CODENAME}' for automatic ROS install. Use jammy (Isaac 4.5.x) or noble (newer) images, or extend this Dockerfile." >&2; \
        exit 1 \
        ;; \
    esac; \
    rm -rf /var/lib/apt/lists/*

RUN RD=$(cat /etc/av4ev-ros-distro) && \
    grep -q "source /opt/ros/${RD}/setup.bash" /root/.bashrc \
    || echo "source /opt/ros/${RD}/setup.bash" >> /root/.bashrc

COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/gps-bridge.sh /usr/local/bin/gps-bridge
RUN chmod +x /entrypoint.sh /usr/local/bin/gps-bridge

ENV ISAAC_SIM_PROJECT=/workspace/repo
WORKDIR /isaac-sim

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash", "-l"]
