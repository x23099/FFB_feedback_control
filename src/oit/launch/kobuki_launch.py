import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('oit')

    twist_mux_config = os.path.join(
        pkg_share,
        'config',
        'twist_mux.yaml'
    )

    ffb_config = os.path.join(
        pkg_share,
        'config',
        'ffb_follow_kobuki.yaml'
    )

    return LaunchDescription([
        # twist_muxノードを起動する.
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            output='screen',
            parameters=[twist_mux_config],
            remappings=[
                ('/cmd_vel_out', '/cmd_vel'),
                ('cmd_vel_out', '/cmd_vel'),
                ('/twist', '/cmd_vel'),
                ('twist', '/cmd_vel'),
            ],
        ),

        # ハンコンノードを起動する.
        Node(
            package='oit',
            executable='handle',
            name='handle_node',
            output='screen',
        ),

        # Kobukiの動きをG923へ反映する.
        Node(
            package='oit',
            executable='ffb_follow',
            name='ffb_follow_node',
            output='screen',
            parameters=[
                ffb_config
            ],
        ),
        
        Node(
            package='oit',
            executable='heartbeat_sender',
            name='heartbeat_sender_node',
            output='screen',
            parameters=[
                os.path.join(pkg_share, 'config', 'failsafe_params.yaml')
            ],
        ),

        Node(
            package='oit',
            executable='cmd_vel_mirror',
            name='cmd_vel_mirror_node',
            output='screen',
            parameters=[
                os.path.join(
                    pkg_share,
                    'config',
                    'cmd_vel_mirror_aiformula.yaml'
                )
            ],
        ),
    ])
