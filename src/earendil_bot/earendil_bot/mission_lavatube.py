#!/usr/bin/env python3
"""Navigate the rover to the lava tube coordinate using Nav2.

Run this manually after the rover has exited the starting enclosure.

Usage:
    ros2 run earendil_bot mission_lavatube --ros-args -p use_sim_time:=true
"""

import time

import rclpy
from rclpy.node import Node
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped
from robot_localization.srv import FromLL


# ─────────────────────────────────────────────
#  TARGET GPS COORDINATE
# ─────────────────────────────────────────────
TARGET_LAT = 39.925112  # Map y ≈ -6.866
TARGET_LON = 32.836628  # Map x ≈ +28.000


def gps_to_map_pose(navigator: BasicNavigator, service_node: Node,
                    lat: float, lon: float) -> PoseStamped:
    """Convert a GPS coordinate to a map-frame PoseStamped via /fromLL."""
    client = service_node.create_client(FromLL, '/fromLL')
    while not client.wait_for_service(timeout_sec=1.0):
        service_node.get_logger().info('/fromLL service not available, waiting …')

    req = FromLL.Request()
    req.ll_point.latitude = lat
    req.ll_point.longitude = lon
    req.ll_point.altitude = 0.0

    future = client.call_async(req)
    rclpy.spin_until_future_complete(service_node, future)
    res = future.result()

    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = res.map_point.x
    pose.pose.position.y = res.map_point.y
    pose.pose.position.z = 0.0
    pose.pose.orientation.w = 1.0
    return pose


def main():
    rclpy.init()

    service_node = rclpy.create_node('mission_lavatube_services')
    navigator = BasicNavigator()

    # --- Wait for Nav2 ---
    navigator.get_logger().info('Waiting for Nav2 bt_navigator to become active …')
    navigator._waitForNodeToActivate('bt_navigator')
    navigator.get_logger().info('Nav2 is active! Giving EKF a few seconds to settle …')
    time.sleep(3.0)

    # --- Convert GPS to map pose ---
    goal_pose = gps_to_map_pose(navigator, service_node, TARGET_LAT, TARGET_LON)
    navigator.get_logger().info(
        f'=== Navigating to lava tube: GPS({TARGET_LAT:.6f}, {TARGET_LON:.6f}) → '
        f'Map(x={goal_pose.pose.position.x:.2f}, y={goal_pose.pose.position.y:.2f}) ==='
    )

    # --- Go ---
    navigator.goToPose(goal_pose)

    while not navigator.isTaskComplete():
        feedback = navigator.getFeedback()
        if feedback:
            current = feedback.current_pose
            elapsed = feedback.navigation_time
            navigator.get_logger().info(
                f'  Navigating … robot @ ({current.pose.position.x:.2f}, '
                f'{current.pose.position.y:.2f})  elapsed: {elapsed.sec}s',
                throttle_duration_sec=5.0,
            )
        time.sleep(0.5)

    # --- Report result ---
    result = navigator.getResult()
    if result == TaskResult.SUCCEEDED:
        navigator.get_logger().info('✅ Lava tube reached!')
    elif result == TaskResult.CANCELED:
        navigator.get_logger().warn('⚠️ Navigation was canceled.')
    elif result == TaskResult.FAILED:
        navigator.get_logger().error('❌ Navigation failed!')
    else:
        navigator.get_logger().error(f'Unknown result: {result}')

    navigator.get_logger().info('mission_lavatube shutting down.')
    rclpy.shutdown()
    import sys
    sys.exit(0)


if __name__ == '__main__':
    main()
