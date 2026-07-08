import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('oit')

    return LaunchDescription([
        Node(
            package='oit',
            executable='failsafe_watchdog',
            name='failsafe_watchdog_node',
            output='screen',
            parameters=[
                os.path.join(pkg_share, 'config', 'failsafe_params.yaml')
            ],
        ),
    ])
