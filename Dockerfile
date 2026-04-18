# ── Base Image ──────────────────────────────────────────────────────
# ros:humble-desktop includes ROS 2 Humble + Gazebo Classic 11 + RViz2
FROM osrf/ros:humble-desktop

# Avoid interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# ── System Dependencies ────────────────────────────────────────────
# Install rosdep + any system packages not covered by rosdep
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-serial \
    ros-humble-gazebo-plugins \
    ros-humble-aruco-ros \
    ros-humble-twist-mux \
    ros-humble-slam-toolbox \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-robot-localization \
    ros-humble-cv-bridge \
    && rm -rf /var/lib/apt/lists/*

# ── Copy Source ─────────────────────────────────────────────────────
WORKDIR /robot_ws
COPY src/ src/

# ── Install ROS Dependencies via rosdep ─────────────────────────────
RUN apt-get update \
    && rosdep update \
    && rosdep install --from-paths src --ignore-src -y \
    && rm -rf /var/lib/apt/lists/*

# ── Build the Workspace ────────────────────────────────────────────
RUN . /opt/ros/humble/setup.sh && \
    colcon build --symlink-install

# ── Entrypoint ──────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Default command: open a bash shell
CMD ["bash"]
