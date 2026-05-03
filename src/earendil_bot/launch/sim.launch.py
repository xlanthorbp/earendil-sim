import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node
import xacro


def generate_launch_description():

    robot_xacro_name = 'my_robot'
    package_name = 'earendil_bot'

    model_file_path = os.path.join(
        get_package_share_directory(package_name),
        'description', 'robot.urdf.xacro',
    )
    robot_description = xacro.process_file(model_file_path).toxml()

    world_file_path = os.path.join(
        get_package_share_directory(package_name),
        'world', 'environment.world',
    )

    # Gazebo model path — so model:// URIs resolve for environment meshes
    meshes_path = os.path.join(
        get_package_share_directory(package_name), 'meshes',
    )
    # Also include the source tree path for symlink-install builds
    src_meshes_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'world', 'meshes',
    )
    gazebo_model_path = ':'.join(filter(os.path.isdir, [
        meshes_path,
        src_meshes_path,
        os.environ.get('GAZEBO_MODEL_PATH', ''),
    ]))

    # Launch arguments
    aruco_marker_size = LaunchConfiguration('aruco_marker_size')
    aruco_reference_frame = LaunchConfiguration('aruco_reference_frame')
    aruco_camera_frame = LaunchConfiguration('aruco_camera_frame')
    aruco_image_topic = LaunchConfiguration('aruco_image_topic')
    aruco_camera_info_topic = LaunchConfiguration('aruco_camera_info_topic')
    enable_tunnel_aruco_nav = LaunchConfiguration('enable_tunnel_aruco_nav')
    enable_circle_escape = LaunchConfiguration('enable_circle_escape')

    # ── Gazebo ─────────────────────────────────────────────────────────
    gazebo_ros_launch = PythonLaunchDescriptionSource(
        os.path.join(
            get_package_share_directory('gazebo_ros'),
            'launch', 'gazebo.launch.py',
        )
    )
    gazebo_launch = IncludeLaunchDescription(
        gazebo_ros_launch,
        launch_arguments={'world': world_file_path}.items(),
    )

    # ── Spawn ──────────────────────────────────────────────────────────
    spawn_model_node = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', 'robot_description',
            '-entity', robot_xacro_name,
            '-x', '-9.8',
            '-y', '-58.0',
            '-z', '3.0',
            '-Y', '1.5708',
        ],
        output='screen',
    )

    # ── Robot State Publisher ──────────────────────────────────────────
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    # ── Twist Mux ─────────────────────────────────────────────────────
    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        output='screen',
        remappings=[('/cmd_vel_out', '/cmd_vel')],
        parameters=[
            os.path.join(
                get_package_share_directory(package_name),
                'config', 'twist_mux.yaml',
            ),
            {'use_sim_time': True},
        ],
    )

    # ── Joystick nodes ────────────────────────────────────────────────
    arduino_joy_node = Node(
        package='earendil_bot',
        executable='arduino_joy',
        name='arduino_joy_node',
        output='screen',
    )

    joy_teleop_node = Node(
        package='earendil_bot',
        executable='joy_teleop',
        name='joy_teleop',
        output='screen',
        parameters=[{'use_sim_time': True}],
    )

    # ── Conditional autonomy nodes ────────────────────────────────────
    tunnel_aruco_nav_node = Node(
        package='earendil_bot',
        executable='tunnel_aruco_nav',
        name='tunnel_aruco_nav',
        output='screen',
        condition=IfCondition(enable_tunnel_aruco_nav),
        parameters=[{
            'use_sim_time': True,
            'image_topic': aruco_image_topic,
            'camera_info_topic': aruco_camera_info_topic,
            'marker_size': aruco_marker_size,
            'dictionary': 'DICT_ARUCO_ORIGINAL',
            'camera_frame': aruco_camera_frame,
            'cmd_vel_topic': 'cmd_vel_tunnel',
            'base_frame': 'base_footprint',
            'world_frame': 'map',
        }],
    )

    circle_escape_node = Node(
        package='earendil_bot',
        executable='circle_escape',
        name='circle_escape',
        output='screen',
        condition=IfCondition(enable_circle_escape),
        parameters=[{
            'use_sim_time': True,
            'scan_topic': 'scan',
            'cmd_vel_topic': 'cmd_vel_escape',
        }],
    )

    # ── Sensor filters ────────────────────────────────────────────────
    scan_ground_filter_node = Node(
        package='earendil_bot',
        executable='scan_ground_filter',
        name='scan_ground_filter',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'lidar_height': 0.42,
            'ground_tolerance': 0.80,
            'ground_tolerance_min': 0.10,
            'ground_tolerance_scale': 0.12,
            'min_pitch_deg': 0.5,
            'scan_topic_in': '/scan',
            'scan_topic_out': '/scan_filtered',
            'imu_topic': '/imu/data',
        }],
    )

    pointcloud_ground_filter_node = Node(
        package='earendil_bot',
        executable='pointcloud_ground_filter',
        name='pointcloud_ground_filter',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'input_topic': '/camera/points',
            'output_topic': '/camera/points_filtered',
            'imu_topic': '/imu/data',
            'base_frame': 'body_link',
            'sensor_height': 0.412,
            'min_obstacle_height': 0.15,
            'max_obstacle_height': 1.8,
            'min_range': 0.15,
            'max_range': 5.0,
            'point_stride': 6,
            'imu_alpha': 0.20,
        }],
    )

    # ── SLAM Toolbox ──────────────────────────────────────────────────
    slam_params_file = os.path.join(
        get_package_share_directory(package_name),
        'config', 'mapper_params_online_async.yaml',
    )

    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('slam_toolbox'),
                'launch', 'online_async_launch.py',
            )
        ),
        launch_arguments={
            'slam_params_file': slam_params_file,
            'use_sim_time': 'true',
        }.items(),
    )

    # ── Robot Localization (Dual UKF + NavSat) ────────────────────────
    ukf_local_config = os.path.join(
        get_package_share_directory(package_name), 'config', 'ukf_local.yaml',
    )
    ukf_global_config = os.path.join(
        get_package_share_directory(package_name), 'config', 'ukf_global.yaml',
    )
    navsat_config_path = os.path.join(
        get_package_share_directory(package_name), 'config', 'navsat.yaml',
    )

    ukf_local_node = Node(
        package='robot_localization',
        executable='ukf_node',
        name='ukf_local_node',
        output='screen',
        parameters=[ukf_local_config, {'use_sim_time': True}],
        remappings=[('odometry/filtered', '/odometry/local')],
    )

    ukf_global_node = Node(
        package='robot_localization',
        executable='ukf_node',
        name='ukf_global_node',
        output='screen',
        parameters=[ukf_global_config, {'use_sim_time': True}],
        remappings=[('odometry/filtered', '/odometry/filtered')],
    )

    navsat_transform_node = Node(
        package='robot_localization',
        executable='navsat_transform_node',
        name='navsat_transform_node',
        output='screen',
        parameters=[navsat_config_path, {'use_sim_time': True}],
        remappings=[
            ('imu', '/imu/data'),
            ('gps/fix', '/gps/raw_fix'),
            ('gps/filtered', '/gps/filtered'),
            ('odometry/gps', '/odometry/gps'),
            ('odometry/filtered', '/odometry/filtered'),
        ],
    )

    # ── Nav2 ──────────────────────────────────────────────────────────
    nav2_params_file = os.path.join(
        get_package_share_directory(package_name),
        'config', 'nav2_params.yaml',
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('nav2_bringup'),
                'launch', 'navigation_launch.py',
            )
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'params_file': nav2_params_file,
        }.items(),
    )

    # ── Timed launch sequence ─────────────────────────────────────────
    # UKF Local starts after spawn completes (event-based)
    # SLAM, UKF Global, NavSat, Nav2 chain with TimerActions after that
    start_localization_after_spawn = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_model_node,
            on_exit=[
                ukf_local_node,
                TimerAction(period=6.0, actions=[slam_toolbox_launch]),
                TimerAction(period=8.0, actions=[ukf_global_node]),
                TimerAction(period=10.0, actions=[navsat_transform_node]),
                TimerAction(period=18.0, actions=[nav2_launch]),
            ],
        )
    )

    # ── Launch description ────────────────────────────────────────────
    ld = LaunchDescription()

    # Declare launch arguments
    ld.add_action(DeclareLaunchArgument(
        'aruco_marker_size',
        default_value='1.0',
        description='ArUco marker side length in meters for marker_publisher.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'aruco_reference_frame',
        default_value='base_footprint',
        description='Reference frame used for published marker poses.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'aruco_camera_frame',
        default_value='camera_link_optical',
        description='Optical frame of the rover camera.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'aruco_image_topic',
        default_value='/camera/image_raw',
        description='Image topic used by aruco_ros marker_publisher.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'aruco_camera_info_topic',
        default_value='/camera/camera_info',
        description='Camera info topic used by aruco_ros marker_publisher.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'enable_tunnel_aruco_nav',
        default_value='false',
        description='Run the tunnel-driving ArUco autonomy node.',
    ))
    ld.add_action(DeclareLaunchArgument(
        'enable_circle_escape',
        default_value='false',
        description='Drive out of the circular enclosed starting area.',
    ))

    # Environment variable for Gazebo model lookup
    ld.add_action(SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH', gazebo_model_path,
    ))

    # Core actions
    ld.add_action(gazebo_launch)
    ld.add_action(spawn_model_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(twist_mux_node)
    ld.add_action(arduino_joy_node)
    ld.add_action(joy_teleop_node)
    ld.add_action(tunnel_aruco_nav_node)
    ld.add_action(circle_escape_node)
    ld.add_action(scan_ground_filter_node)
    ld.add_action(pointcloud_ground_filter_node)

    # Event-based localization + navigation chain
    ld.add_action(start_localization_after_spawn)

    return ld
