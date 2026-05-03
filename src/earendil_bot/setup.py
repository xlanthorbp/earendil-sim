import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'earendil_bot'

setup(
    name=package_name,
    version='0.4.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'description'),
            glob('description/*.xacro') + glob('description/*.gazebo') + glob('description/*.yaml')),
        (os.path.join('share', package_name, 'meshes', 'environment'), [
            'world/meshes/environment/environment.obj',
            'world/meshes/environment/environment.mtl',
            'world/meshes/environment/aruco-100.png',
            'world/meshes/environment/aruco-101.png',
            'world/meshes/environment/object_bake.png',
            'world/meshes/environment/rock_bake.png',
            'world/meshes/environment/terrain_bake.png',
            'world/meshes/environment/model.config',
        ]),
        (os.path.join('share', package_name, 'config'), [
            'config/twist_mux.yaml',
            'config/nav2_params.yaml',
            'config/mapper_params_online_async.yaml',
            'config/ukf_local.yaml',
            'config/ukf_global.yaml',
            'config/navsat.yaml',
            'config/missions.yaml',
        ]),
        (os.path.join('share', package_name, 'world'), glob('world/*.world')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='berkay',
    maintainer_email='berkaypaksoy07@gmail.com',
    description='Autonomous navigation and sensor fusion stack for the Earendil Bot rover simulation in ROS 2 Humble.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'tank_teleop = earendil_bot.tank_teleop:main',
            'arduino_joy = earendil_bot.arduino_joy:main',
            'joy_teleop = earendil_bot.joy_teleop:main',
            'waypoint_nav = earendil_bot.waypoint_nav:main',
            'circle_drive = earendil_bot.circle_drive:main',
            'tunnel_aruco_nav = earendil_bot.tunnel_aruco_nav:main',
            'base_exit = earendil_bot.base_exit:main',
            'mission_nav = earendil_bot.mission_nav:main',
            'base_return = earendil_bot.base_return:main',
            'mission_start = earendil_bot.mission_start:main',
            'scan_ground_filter = earendil_bot.scan_ground_filter:main',
            'pointcloud_ground_filter = earendil_bot.pointcloud_ground_filter:main',
        ],
    },
)
