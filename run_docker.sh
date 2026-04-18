#!/bin/bash

# Allow the Docker container to connect to your X11 Display
xhost +local:root

# Run the container with GPU + X11 passthrough
docker run -it --rm \
  --name earendil_sim \
  --net=host \
  --env="DISPLAY=$DISPLAY" \
  --env="QT_X11_NO_MITSHM=1" \
  --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  --gpus all \
  --env="NVIDIA_VISIBLE_DEVICES=all" \
  --env="NVIDIA_DRIVER_CAPABILITIES=all" \
  --env="__NV_PRIME_RENDER_OFFLOAD=1" \
  --env="__GLX_VENDOR_LIBRARY_NAME=nvidia" \
  earendil_image:latest \
  bash

# NOTE: To use the Arduino joystick, add these flags before the image name:
#   --device=/dev/ttyUSB0 \
#   --group-add dialout \

# After the container exits, revoke X11 access
xhost -local:root