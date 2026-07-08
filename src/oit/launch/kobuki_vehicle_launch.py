import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('oit')

    # 1. kobuki_node の公式ローンチファイルを取得
    kobuki_node_dir = get_package_share_directory('kobuki_node')
    kobuki_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(kobuki_node_dir, 'launch', 'kobuki_node-launch.py')
        )
    )

    # 2. twist_muxノードの起動 (設定ファイルは oit の twist_mux.yaml を使用)
    twist_mux_config = os.path.join(
        pkg_share,
        'config',
        'twist_mux.yaml'
    )
    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux_node',
        output='screen',
        parameters=[twist_mux_config],
        remappings=[
            ('/cmd_vel_out', '/commands/velocity'),
            ('cmd_vel_out', '/commands/velocity'),
            ('/twist', '/commands/velocity'),
            ('twist', '/commands/velocity'),
        ],
    )

    # 3. failsafe_watchdogノードの起動 (設定ファイルは oit の failsafe_params.yaml を使用)
    watchdog_config = os.path.join(
        pkg_share,
        'config',
        'failsafe_params.yaml'
    )
    watchdog_node = Node(
        package='oit',
        executable='failsafe_watchdog',
        name='failsafe_watchdog_node',
        output='screen',
        parameters=[watchdog_config],
    )

    return LaunchDescription([
        kobuki_launch,
        twist_mux_node,
        watchdog_node,
    ])
