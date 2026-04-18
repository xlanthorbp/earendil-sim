import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_name = 'earendil_bot'
    
    # Gazebo'yu başlatma süreci
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')]),
    )

    # URDF dosyasını okuma
    urdf_file = os.path.join(
        get_package_share_directory(pkg_name), 'description', 'robot.urdf.xacro'
    )
    
    # Robot State Publisher (URDF'i topic olarak yayınlar)
    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        arguments=[urdf_file]
    )

    # Robotu Gazebo'ya "Spawn" etme (Yaratma)
    spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'my_bot'],
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        rsp,
        spawn_entity,
    ])
