#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /robot_ws/install/setup.bash

exec "$@"
