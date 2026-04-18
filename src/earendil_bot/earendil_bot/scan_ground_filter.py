#!/usr/bin/env python3
"""
scan_ground_filter  –  Removes ground-plane hits from a 2-D LaserScan.

Problem
-------
On rough terrain (hills, craters) the rover tilts.  Because the RPLIDAR
is rigidly mounted, its scan plane tilts too.  Forward-facing rays hit
the ground a few metres ahead and Nav2 sees them as impassable walls.
Inside craters the same effect makes crater walls invisible or creates
phantom obstacles.

Solution
--------
Read the robot's current **pitch** and **roll** from the IMU.  For every
ray in the scan, compute where it *would* hit an infinite ground plane at
the known sensor height.  If the actual measured range is close to (or
beyond) that ground-hit distance, replace the reading with ``inf`` so the
costmap ignores it.

Published topic
~~~~~~~~~~~~~~~
``/scan_filtered``  – cleaned LaserScan, plug straight into Nav2.

Subscribed topics
~~~~~~~~~~~~~~~~~
``/scan``      – raw 360° scan from Gazebo / real RPLIDAR
``/imu/data``  – orientation quaternion (ICM-20948 or Gazebo plugin)
"""

import math
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from sensor_msgs.msg import LaserScan, Imu
from tf_transformations import euler_from_quaternion


class ScanGroundFilter(Node):
    """Filter ground returns out of a 2-D LaserScan using IMU orientation."""

    def __init__(self):
        super().__init__('scan_ground_filter')

        # ── tuneable parameters ─────────────────────────────────────────
        self.declare_parameter('lidar_height', 0.42)      # metres above ground on flat terrain
        self.declare_parameter('ground_tolerance', 0.30)   # accept range within ±tol of expected ground hit
        self.declare_parameter('min_pitch_deg', 3.0)       # ignore filtering below this tilt (flat ground)
        self.declare_parameter('scan_topic_in', '/scan')
        self.declare_parameter('scan_topic_out', '/scan_filtered')
        self.declare_parameter('imu_topic', '/imu/data')

        self.lidar_height    = self.get_parameter('lidar_height').value
        self.ground_tol      = self.get_parameter('ground_tolerance').value
        self.min_pitch_rad   = math.radians(self.get_parameter('min_pitch_deg').value)
        scan_in              = self.get_parameter('scan_topic_in').value
        scan_out             = self.get_parameter('scan_topic_out').value
        imu_topic            = self.get_parameter('imu_topic').value

        # ── state ───────────────────────────────────────────────────────
        self.current_roll  = 0.0
        self.current_pitch = 0.0

        # ── QoS ─────────────────────────────────────────────────────────
        sensor_qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        # ── subscribers ─────────────────────────────────────────────────
        self.imu_sub = self.create_subscription(
            Imu, imu_topic, self._imu_cb, sensor_qos)
        self.scan_sub = self.create_subscription(
            LaserScan, scan_in, self._scan_cb, sensor_qos)

        # ── publisher ───────────────────────────────────────────────────
        self.scan_pub = self.create_publisher(LaserScan, scan_out, sensor_qos)

        self.get_logger().info(
            f'ScanGroundFilter active  h={self.lidar_height:.2f}m  '
            f'tol={self.ground_tol:.2f}m  min_pitch={math.degrees(self.min_pitch_rad):.1f}°'
        )

    # ─────────────────────────────────────────────────────────────────────
    def _imu_cb(self, msg: Imu):
        q = msg.orientation
        roll, pitch, _ = euler_from_quaternion([q.x, q.y, q.z, q.w])
        self.current_roll  = roll
        self.current_pitch = pitch

    # ─────────────────────────────────────────────────────────────────────
    def _scan_cb(self, msg: LaserScan):
        pitch = self.current_pitch
        roll  = self.current_roll

        # If the robot is practically flat, just forward the scan unchanged.
        if abs(pitch) < self.min_pitch_rad and abs(roll) < self.min_pitch_rad:
            self.scan_pub.publish(msg)
            return

        h = self.lidar_height
        ranges = np.array(msg.ranges, dtype=np.float32)
        n = len(ranges)

        # Build array of scan angles (each ray's horizontal angle in sensor frame)
        angles = np.arange(n, dtype=np.float32) * msg.angle_increment + msg.angle_min

        # ── Geometry ────────────────────────────────────────────────────
        # The LiDAR emits rays in its own XY plane (z=0 in sensor frame).
        # When the body (and therefore the sensor) pitches by θ_p and rolls
        # by θ_r, a ray at scan angle α has a world-frame direction:
        #
        #   d_x =  cos(α) cos(θ_p)
        #   d_y =  sin(α) cos(θ_r) - cos(α) sin(θ_p) sin(θ_r)
        #   d_z = -cos(α) sin(θ_p) cos(θ_r) - sin(α) sin(θ_r)
        #
        # The ray hits the ground (z = -h) at range
        #   r_ground = h / [cos(α) sin(θ_p) cos(θ_r) + sin(α) sin(θ_r)]
        #
        # (only valid when the denominator > 0, i.e. ray points downward)
        # ────────────────────────────────────────────────────────────────

        cos_a = np.cos(angles)
        sin_a = np.sin(angles)
        sp = math.sin(pitch)
        cp = math.cos(pitch)
        sr = math.sin(roll)
        cr = math.cos(roll)

        # Vertical component of each ray direction (positive = upward in world)
        dz = -(cos_a * sp * cr) - (sin_a * sr)

        # dz < 0 means the ray points into the ground
        ground_mask = dz < -1e-4   # ray has significant downward component

        # Expected ground-hit range for rays that point downward
        r_ground = np.full(n, np.inf, dtype=np.float32)
        r_ground[ground_mask] = h / (-dz[ground_mask])

        # Determine which rays are hitting the ground
        # A ray is a "ground hit" if its measured range is within tolerance
        # of the expected ground distance, or if it's BEYOND the expected
        # ground distance (meaning it went past the ground — numerical edge).
        valid = np.isfinite(ranges) & (ranges > msg.range_min)
        is_ground = (
            ground_mask
            & valid
            & (ranges < (r_ground + self.ground_tol))
        )

        # Replace ground hits with inf (costmap will ignore them)
        ranges[is_ground] = float('inf')

        # Publish the filtered scan
        out = LaserScan()
        out.header = msg.header
        out.angle_min = msg.angle_min
        out.angle_max = msg.angle_max
        out.angle_increment = msg.angle_increment
        out.time_increment = msg.time_increment
        out.scan_time = msg.scan_time
        out.range_min = msg.range_min
        out.range_max = msg.range_max
        out.ranges = ranges.tolist()
        out.intensities = list(msg.intensities) if msg.intensities else []
        self.scan_pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = ScanGroundFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
