import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node
import xacro

def generate_launch_description():

	robotXacroName='my_robot'
	
	namePackage='earendil_bot'
	
	modelFileRelativePath = 'description/robot.urdf.xacro'
	pathModelFile = os.path.join(get_package_share_directory(namePackage),modelFileRelativePath)
	
	robotDescription = xacro.process_file(pathModelFile).toxml()
	
	worldFilePath = os.path.join(get_package_share_directory(namePackage), 'world', 'environment.world')

	aruco_marker_size = LaunchConfiguration('aruco_marker_size')
	aruco_reference_frame = LaunchConfiguration('aruco_reference_frame')
	aruco_camera_frame = LaunchConfiguration('aruco_camera_frame')
	aruco_image_topic = LaunchConfiguration('aruco_image_topic')
	aruco_camera_info_topic = LaunchConfiguration('aruco_camera_info_topic')
	enable_tunnel_aruco_nav = LaunchConfiguration('enable_tunnel_aruco_nav')
	enable_circle_escape = LaunchConfiguration('enable_circle_escape')

	gazebo_rosPackageLaunch=PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('gazebo_ros'),'launch','gazebo.launch.py'))	
		
	gazeboLaunch=IncludeLaunchDescription(gazebo_rosPackageLaunch, launch_arguments={'world': worldFilePath}.items())

	spawnModelNode = Node(package='gazebo_ros',executable='spawn_entity.py',
	arguments=['-topic','robot_description','-entity', robotXacroName,
	'-x', '-9.8', '-y', '-58.0', '-z', '3.0', '-Y', '1.5708'], output='screen')
	
	nodeRobotStatePublisher = Node(
	package='robot_state_publisher',
	executable='robot_state_publisher',
	output='screen',
	parameters=[{'robot_description': robotDescription,
	'use_sim_time': True}]
	)

	twist_mux_node = Node(
		package='twist_mux',
		executable='twist_mux',
		output='screen',
		remappings=[('/cmd_vel_out', '/cmd_vel')],
		parameters=[
			os.path.join(get_package_share_directory(namePackage), 'config', 'twist_mux.yaml'),
			{'use_sim_time': True}
		]
	)
	
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

	# --- SLAM Toolbox (commented out per user request) ---
	slam_params_file = os.path.join(
		get_package_share_directory(namePackage),
		'description', 'mapper_params_online_async.yaml'
	)

	slam_toolbox_launch = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(
			os.path.join(get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')
		),
		launch_arguments={
			'slam_params_file': slam_params_file,
			'use_sim_time': 'true'
		}.items()
	)

	delayed_slam = TimerAction(period=3.0, actions=[slam_toolbox_launch])

	# --- Robot Localization (Dual EKF + NavSat) ---
	ekf_config_path = os.path.join(get_package_share_directory(namePackage), 'config', 'ekf.yaml')
	navsat_config_path = os.path.join(get_package_share_directory(namePackage), 'config', 'navsat.yaml')

	ekf_local_node = Node(
		package='robot_localization',
		executable='ekf_node',
		name='ekf_filter_node_odom',
		output='screen',
		parameters=[ekf_config_path, {'use_sim_time': True}],
		remappings=[('odometry/filtered', 'odometry/local')]
	)

	ekf_global_node = Node(
		package='robot_localization',
		executable='ekf_node',
		name='ekf_filter_node_map',
		output='screen',
		parameters=[ekf_config_path, {'use_sim_time': True}],
		remappings=[('odometry/filtered', 'odometry/global')]
	)

	navsat_transform_node = Node(
		package='robot_localization',
		executable='navsat_transform_node',
		name='navsat_transform_node',
		output='screen',
		parameters=[navsat_config_path, {'use_sim_time': True}],
		remappings=[
			('imu', '/imu/data'),
			('gps/fix', '/gps/fix'),
			('gps/filtered', '/gps/filtered'),
			('odometry/gps', '/odometry/gps'),
			('odometry/filtered', '/odometry/global')
		]
	)

	# --- Scan Ground Filter (removes ground hits on slopes/craters) ---
	scan_ground_filter_node = Node(
		package='earendil_bot',
		executable='scan_ground_filter',
		name='scan_ground_filter',
		output='screen',
		parameters=[{
			'use_sim_time': True,
			'lidar_height': 0.42,
			'ground_tolerance': 0.50,
			'min_pitch_deg': 2.0,
			'scan_topic_in': '/scan',
			'scan_topic_out': '/scan_filtered',
			'imu_topic': '/imu/data',
		}],
	)

	localization_group = TimerAction(period=3.0, actions=[ekf_local_node, ekf_global_node, navsat_transform_node])

	# --- Nav2 (delayed 10s to let EKF start first) ---
	nav2_params_file = os.path.join(
		get_package_share_directory(namePackage),
		'config', 'nav2_params.yaml'
	)

	nav2_launch = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(
			os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
		),
		launch_arguments={
			'use_sim_time': 'true',
			'params_file': nav2_params_file
		}.items()
	)

	delayed_nav2 = TimerAction(period=6.0, actions=[nav2_launch])

	launchDescriptionObject = LaunchDescription()

	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'aruco_marker_size',
		default_value='1.0',
		description='ArUco marker side length in meters for marker_publisher.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'aruco_reference_frame',
		default_value='base_footprint',
		description='Reference frame used for published marker poses.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'aruco_camera_frame',
		default_value='camera_link_optical',
		description='Optical frame of the rover camera.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'aruco_image_topic',
		default_value='/camera/image_raw',
		description='Image topic used by aruco_ros marker_publisher.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'aruco_camera_info_topic',
		default_value='/camera/camera_info',
		description='Camera info topic used by aruco_ros marker_publisher.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'enable_tunnel_aruco_nav',
		default_value='false',
		description='Run the tunnel-driving ArUco autonomy node.',
	))
	launchDescriptionObject.add_action(DeclareLaunchArgument(
		'enable_circle_escape',
		default_value='false',
		description='Drive out of the circular enclosed starting area.',
	))
	
	launchDescriptionObject.add_action(gazeboLaunch)
	
	launchDescriptionObject.add_action(spawnModelNode)
	launchDescriptionObject.add_action(nodeRobotStatePublisher)
	launchDescriptionObject.add_action(twist_mux_node)
	launchDescriptionObject.add_action(arduino_joy_node)
	launchDescriptionObject.add_action(joy_teleop_node)
	launchDescriptionObject.add_action(tunnel_aruco_nav_node)
	launchDescriptionObject.add_action(circle_escape_node)
	launchDescriptionObject.add_action(scan_ground_filter_node)
	
	# SLAM is turned off by default for GPS navigation, uncomment below to use:
	# launchDescriptionObject.add_action(delayed_slam)
	launchDescriptionObject.add_action(localization_group)
	launchDescriptionObject.add_action(delayed_nav2)
	
	return launchDescriptionObject
	
