import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess

def generate_launch_description():
    pkg_share = get_package_share_directory('oit')
    
    twist_mux_config = os.path.join(
        pkg_share,
        'config',
        'twist_mux.yaml'
    )
    
    return LaunchDescription([
        # 1. twist_muxノードの起動（トピックの優先順位を管理する司令塔）
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux_node',
            output='screen',
            parameters=[twist_mux_config],
            remappings=[
                ('cmd_vel_out', 'cmd_vel')
            ],
        ),
        # 2. 正方形自動走行ノードの起動
        # Node(
        #     package='oit',
        #     executable='square_node',
        #     name='square_node',
        #     output='screen',
        # ),

        # 3. ハンコンノードの起動
        Node(
            package='oit',
            executable='handle',
            name='HandleNode',
            output='screen',
        ),
        
        # 4. 自作トピックセレクターノードの起動（最優先を判断する司令塔）
        # Node(
        #     package='oit',                       
        #     executable='vel_selector',     
        #     name='vel_selector_node',
        #     output='screen',
        #     parameters=[{
        #         'steering_deadzone': 0.01,      # 遊びを最小限にする
        #         'steering_exponent': 0.4,      # 浅い角度での変化量を大幅に強調する
        #         'angular_gain': 2.2,           # 全体的な旋回力を底上げする
        #         'angle_mode': False,           # ハンドル角度→旋回速度変換モードはOFF（直接的な速度指令モード）
        #     }]
        #     #  vel_selector_nodeの内部で、すでに 'cmd_vel', 'cmd_vel_auto', 'cmd_vel_joy' を
        #     #    直接指定して作成しているため、ここでは remappings によるトピック名の変更は不要です。
        # ),
        
        ExecuteProcess(
            cmd=[
                'ffset',
                '/dev/input/by-id/usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_USYMUGUXEREJOFORUFUMEZIDU-event-joystick',
                '-a',
                '80'
            ],
            output='screen'
        ),
    ])