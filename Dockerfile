# ====================================================================
# STAGE 1: Builder
# ====================================================================
FROM osrf/ros:humble-desktop AS builder

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /robot_ws

# 1. Copy package.xml first to utilize Docker layer caching.
# If you only change Python/Xacro files, this step and rosdep install
# will be instantly loaded from cache, saving minutes on every build!
COPY src/earendil_bot/package.xml src/earendil_bot/package.xml

# 2. Install all ROS dependencies defined in package.xml automatically
RUN apt-get update \
    && rosdep update \
    && rosdep install --from-paths src --ignore-src -y \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy the rest of the source code
COPY src/ src/

# 4. Build the workspace
# Note: No --symlink-install here! We want actual compiled files so we
# can leave the 'src' folder behind in the next stage.
RUN . /opt/ros/humble/setup.sh && \
    colcon build


# ====================================================================
# STAGE 2: Runtime
# ====================================================================
FROM osrf/ros:humble-desktop AS runtime

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /robot_ws

# 1. Copy package.xml again to install dependencies in the runtime image
COPY src/earendil_bot/package.xml src/earendil_bot/package.xml

# 2. Install runtime dependencies
RUN apt-get update \
    && rosdep update \
    && rosdep install --from-paths src --ignore-src -y \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy ONLY the compiled 'install' folder from the builder stage.
# We leave behind 'src', 'build', 'log' and all compiler caches.
COPY --from=builder /robot_ws/install /robot_ws/install

# 4. Setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
