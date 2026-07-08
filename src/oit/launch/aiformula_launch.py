import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('oit')

    # AIFORMULA用FFB設定ファイルを取得する.
    ffb_config = os.path.join(
        pkg_share,
        'config',
        'ffb_follow_aiformula.yaml'
    )

    return LaunchDescription([
        # ハンコン指令をAIFORMULA側twist_muxの手動入力へ送る.
        Node(
            package='oit',
            executable='handle',
            name='handle_node',
            output='screen',
            remappings=[
                (
                    '/cmd_vel_joy',
                    '/aiformula_control/handle_controller/cmd_vel'
                )
            ],
        ),

        # AIFORMULAの動きをG923へ反映する.
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
    ])