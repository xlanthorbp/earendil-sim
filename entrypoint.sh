#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /robot_ws/install/setup.bash

# Let Gazebo find the environment meshes
export GAZEBO_MODEL_PATH="/robot_ws/src/earendil_bot/world:${GAZEBO_MODEL_PATH}"
export GAZEBO_RESOURCE_PATH="/robot_ws/src/earendil_bot/world:${GAZEBO_RESOURCE_PATH}"

exec "$@"
