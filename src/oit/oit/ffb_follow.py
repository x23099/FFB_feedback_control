#!/usr/bin/env python3

import math
import subprocess

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, Float32, Int32, String

from evdev import InputDevice, ecodes, ff


class FfbFollowNode(Node):
    def __init__(self):
        super().__init__('ffb_follow_node')
        # ROSパラメータを宣言する
        self.declare_ros_parameters()

        # ROSパラメータを読み込む
        self.load_ros_parameters()

        # 実行状態を初期化する
        self.initialize_runtime_states()

        # G923を初期化する
        self.initialize_ffb_device()

        # ROS通信を初期化する
        self.initialize_ros_interfaces()

        self.get_logger().info(
            'FFB follow node started.'
        )
    
    def declare_ros_parameters(self):
        """
        ROSパラメータとデフォルト値を宣言する.
        """

        # トピック名
        self.declare_parameter(
            'auto_cmd_topic',
            '/cmd_vel_auto'
        )

        self.declare_parameter(
            'odom_topic',
            '/odom'
        )

        self.declare_parameter(
            'manual_active_topic',
            '/handle/manual_active'
        )

        self.declare_parameter(
            'emergency_stop_topic',
            '/handle/emergency_stop'
        )

        self.declare_parameter(
            'gear_topic',
            '/handle/gear'
        )

        self.declare_parameter(
            'steering_norm_topic',
            '/handle/steering_norm'
        )

        self.declare_parameter(
            'imu_topic',
            '/sensors/imu_data_raw'
        )

        # G923デバイス
        self.declare_parameter(
            'device_path',
            (
                '/dev/input/by-id/'
                'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
                'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
            )
        )

        # Autocenter
        self.declare_parameter(
            'auto_autocenter',
            0
        )

        self.declare_parameter(
            'manual_autocenter',
            60
        )

        self.declare_parameter(
            'idle_autocenter',
            15
        )

        self.declare_parameter(
            'shutdown_autocenter',
            80
        )

        # 角度変換
        self.declare_parameter(
            'handle_limit_deg',
            450.0
        )

        self.declare_parameter(
            'yaw_to_handle_ratio',
            450.0 / 360.0
        )

        self.declare_parameter(
            'invert_yaw_sign',
            True
        )

        self.declare_parameter(
            'center_offset_deg',
            -3.0
        )

        # 自律旋回判定
        self.declare_parameter(
            'auto_angular_threshold',
            0.05
        )

        self.declare_parameter(
            'auto_cmd_timeout',
            0.3
        )

        # 自律旋回中のSpring
        self.declare_parameter(
            'auto_spring_coeff',
            0x4900
        )

        self.declare_parameter(
            'auto_spring_saturation',
            0x6000
        )

        # 手動操作中のSpring
        self.declare_parameter(
            'manual_spring_coeff',
            0x4900
        )

        self.declare_parameter(
            'manual_spring_saturation',
            0x6000
        )

        # 待機中のSpring
        self.declare_parameter(
            'idle_spring_coeff',
            0x3000
        )

        self.declare_parameter(
            'idle_spring_saturation',
            0x4800
        )

        self.declare_parameter(
            'spring_deadband',
            0
        )

        # Spring更新
        self.declare_parameter(
            'max_center_step',
            400
        )

        self.declare_parameter(
            'coeff_step',
            0x0200
        )

        self.declare_parameter(
            'saturation_step',
            0x0200
        )

        self.declare_parameter(
            'center_send_threshold',
            20
        )

        self.declare_parameter(
            'coeff_send_threshold',
            0x0080
        )

        self.declare_parameter(
            'saturation_send_threshold',
            0x0080
        )

        self.declare_parameter(
            'effect_refresh_sec',
            1.0
        )

        self.declare_parameter(
            'spring_update_period',
            0.05
        )

        self.declare_parameter(
            'spring_replay_ms',
            30000
        )

        # Damper
        self.declare_parameter(
            'damper_enabled',
            False
        )

        self.declare_parameter(
            'damper_coeff',
            2500
        )

        self.declare_parameter(
            'damper_saturation',
            6000
        )

        self.declare_parameter(
            'damper_deadband',
            0
        )

        # 段差振動FFB
        self.declare_parameter(
            'bump_feedback_enabled',
            False
        )

        self.declare_parameter(
            'bump_angular_threshold',
            0.18
        )

        self.declare_parameter(
            'bump_angular_full_scale',
            0.55
        )

        self.declare_parameter(
            'bump_min_interval_sec',
            0.25
        )

        self.declare_parameter(
            'bump_cooldown_override_rate',
            0.60
        )

        self.declare_parameter(
            'bump_min_speed',
            0.03
        )

        self.declare_parameter(
            'bump_rumble_duration_ms',
            120
        )

        self.declare_parameter(
            'bump_rumble_enabled',
            False
        )

        self.declare_parameter(
            'bump_rumble_weak_min',
            0x1000
        )

        self.declare_parameter(
            'bump_rumble_weak_max',
            0x4600
        )

        self.declare_parameter(
            'bump_rumble_strong_min',
            0x3000
        )

        self.declare_parameter(
            'bump_rumble_strong_max',
            0x7fff
        )

        self.declare_parameter(
            'bump_center_kick_enabled',
            True
        )

        self.declare_parameter(
            'bump_center_kick_min_deg',
            6.0
        )

        self.declare_parameter(
            'bump_center_kick_max_deg',
            28.0
        )

        self.declare_parameter(
            'bump_center_kick_duration_sec',
            0.22
        )

        self.declare_parameter(
            'bump_center_kick_frequency_hz',
            18.0
        )

        self.declare_parameter(
            'bump_center_kick_coeff',
            28000
        )

        self.declare_parameter(
            'bump_center_kick_saturation',
            32000
        )

        self.declare_parameter(
            'bump_constant_kick_enabled',
            True
        )

        self.declare_parameter(
            'bump_constant_min_level',
            9000
        )

        self.declare_parameter(
            'bump_constant_max_level',
            24000
        )

        self.declare_parameter(
            'bump_constant_pulse_ms',
            45
        )

        self.declare_parameter(
            'bump_constant_second_delay_sec',
            0.055
        )

        self.declare_parameter(
            'bump_periodic_enabled',
            True
        )

        self.declare_parameter(
            'bump_periodic_preload_enabled',
            True
        )

        self.declare_parameter(
            'bump_periodic_min_magnitude',
            12000
        )

        self.declare_parameter(
            'bump_periodic_max_magnitude',
            32767
        )

        self.declare_parameter(
            'bump_periodic_period_ms',
            35
        )

        self.declare_parameter(
            'bump_periodic_duration_ms',
            120
        )

        self.declare_parameter(
            'bump_periodic_direction',
            0x4000
        )

        self.declare_parameter(
            'bump_angular_z_weight',
            0.6
        )

        self.declare_parameter(
            'bump_angular_delta_weight',
            0.7
        )

        self.declare_parameter(
            'bump_debug_enabled',
            True
        )

        self.declare_parameter(
            'bump_debug_period_sec',
            1.0
        )

        # 緊急停止通知FFB
        self.declare_parameter(
            'emergency_feedback_enabled',
            True
        )

        self.declare_parameter(
            'emergency_feedback_magnitude',
            3500
        )

        self.declare_parameter(
            'emergency_feedback_period_ms',
            35
        )

        self.declare_parameter(
            'emergency_feedback_duration_ms',
            60
        )

        self.declare_parameter(
            'emergency_feedback_direction',
            0x4000
        )

        # カーブ負荷FFB
        self.declare_parameter(
            'corner_load_enabled',
            True
        )

        self.declare_parameter(
            'corner_load_reference',
            0.8
        )

        self.declare_parameter(
            'corner_load_min_speed',
            0.10
        )

        self.declare_parameter(
            'corner_load_coeff_gain',
            4000
        )

        self.declare_parameter(
            'corner_load_saturation_gain',
            5000
        )

        self.declare_parameter(
            'corner_load_filter_alpha',
            0.25
        )

        # カーブ負荷による中心ずらしFFB
        self.declare_parameter(
            'corner_center_shift_enabled',
            True
        )

        self.declare_parameter(
            'corner_center_shift_max_deg',
            45.0
        )

        self.declare_parameter(
            'corner_center_shift_min_rate',
            0.10
        )

        self.declare_parameter(
            'corner_center_shift_direction',
            -1.0
        )

        # カーブ負荷によるAutocenter補正
        self.declare_parameter(
            'corner_autocenter_enabled',
            True
        )

        self.declare_parameter(
            'corner_autocenter_min_rate',
            0.20
        )

        self.declare_parameter(
            'corner_autocenter_max',
            85
        )

        self.declare_parameter(
            'corner_autocenter_update_threshold',
            5
        )

        # 高ギアカーブ時のAutocenter切り替え
        self.declare_parameter(
            'corner_gate_autocenter_enabled',
            True
        )

        self.declare_parameter(
            'corner_gate_min_gear',
            4
        )

        self.declare_parameter(
            'corner_gate_min_speed',
            0.45
        )

        self.declare_parameter(
            'corner_gate_min_angular',
            0.35
        )

        self.declare_parameter(
            'corner_gate_min_steering_norm',
            0.20
        )

        self.declare_parameter(
            'corner_gate_min_load_rate',
            0.25
        )

        self.declare_parameter(
            'corner_gate_enter_sec',
            0.15
        )

        self.declare_parameter(
            'corner_gate_hold_sec',
            0.50
        )

        self.declare_parameter(
            'corner_gate_autocenter',
            95
        )
    
    def load_ros_parameters(self):
        """
        ROSパラメータをクラス変数へ読み込む.
        """

        # トピック名
        self.auto_cmd_topic = str(
            self.get_parameter('auto_cmd_topic').value
        )

        self.odom_topic = str(
            self.get_parameter('odom_topic').value
        )

        self.manual_active_topic = str(
            self.get_parameter('manual_active_topic').value
        )

        self.emergency_stop_topic = str(
            self.get_parameter('emergency_stop_topic').value
        )

        self.gear_topic = str(
            self.get_parameter('gear_topic').value
        )

        self.steering_norm_topic = str(
            self.get_parameter('steering_norm_topic').value
        )

        self.imu_topic = str(
            self.get_parameter('imu_topic').value
        )

        # G923デバイス
        self.device_path = str(
            self.get_parameter('device_path').value
        )

        # Autocenter
        self.auto_autocenter = int(
            self.get_parameter('auto_autocenter').value
        )

        self.manual_autocenter = int(
            self.get_parameter('manual_autocenter').value
        )

        self.idle_autocenter = int(
            self.get_parameter('idle_autocenter').value
        )

        self.shutdown_autocenter = int(
            self.get_parameter('shutdown_autocenter').value
        )

        # 角度変換
        self.handle_limit_deg = float(
            self.get_parameter('handle_limit_deg').value
        )

        self.yaw_to_handle_ratio = float(
            self.get_parameter('yaw_to_handle_ratio').value
        )

        self.invert_yaw_sign = bool(
            self.get_parameter('invert_yaw_sign').value
        )

        self.center_offset_deg = float(
            self.get_parameter('center_offset_deg').value
        )

        # 自律旋回判定
        self.auto_angular_threshold = float(
            self.get_parameter('auto_angular_threshold').value
        )

        self.auto_cmd_timeout = float(
            self.get_parameter('auto_cmd_timeout').value
        )

        # 自律旋回中のSpring
        self.auto_spring_coeff = int(
            self.get_parameter('auto_spring_coeff').value
        )

        self.auto_spring_saturation = int(
            self.get_parameter(
                'auto_spring_saturation'
            ).value
        )

        # 手動操作中のSpring
        self.manual_spring_coeff = int(
            self.get_parameter('manual_spring_coeff').value
        )

        self.manual_spring_saturation = int(
            self.get_parameter(
                'manual_spring_saturation'
            ).value
        )

        # 待機中のSpring
        self.idle_spring_coeff = int(
            self.get_parameter('idle_spring_coeff').value
        )

        self.idle_spring_saturation = int(
            self.get_parameter(
                'idle_spring_saturation'
            ).value
        )

        self.spring_deadband = int(
            self.get_parameter('spring_deadband').value
        )

        # Spring更新
        self.max_center_step = int(
            self.get_parameter('max_center_step').value
        )

        self.coeff_step = int(
            self.get_parameter('coeff_step').value
        )

        self.saturation_step = int(
            self.get_parameter('saturation_step').value
        )

        self.center_send_threshold = int(
            self.get_parameter(
                'center_send_threshold'
            ).value
        )

        self.coeff_send_threshold = int(
            self.get_parameter(
                'coeff_send_threshold'
            ).value
        )

        self.saturation_send_threshold = int(
            self.get_parameter(
                'saturation_send_threshold'
            ).value
        )

        self.effect_refresh_sec = float(
            self.get_parameter('effect_refresh_sec').value
        )

        self.spring_update_period = float(
            self.get_parameter(
                'spring_update_period'
            ).value
        )

        self.spring_replay_ms = int(
            self.get_parameter('spring_replay_ms').value
        )
        
        # Damper
        self.damper_enabled = bool(
            self.get_parameter('damper_enabled').value
        )

        self.damper_coeff = int(
            self.get_parameter('damper_coeff').value
        )

        self.damper_saturation = int(
            self.get_parameter('damper_saturation').value
        )

        self.damper_deadband = int(
            self.get_parameter('damper_deadband').value
        )

        # 段差振動FFB
        self.bump_feedback_enabled = bool(
            self.get_parameter('bump_feedback_enabled').value
        )

        self.bump_angular_threshold = float(
            self.get_parameter('bump_angular_threshold').value
        )

        self.bump_angular_full_scale = float(
            self.get_parameter('bump_angular_full_scale').value
        )

        self.bump_min_interval_sec = float(
            self.get_parameter('bump_min_interval_sec').value
        )

        self.bump_cooldown_override_rate = float(
            self.get_parameter('bump_cooldown_override_rate').value
        )

        self.bump_min_speed = float(
            self.get_parameter('bump_min_speed').value
        )

        self.bump_rumble_duration_ms = int(
            self.get_parameter('bump_rumble_duration_ms').value
        )

        self.bump_rumble_enabled = bool(
            self.get_parameter('bump_rumble_enabled').value
        )

        self.bump_rumble_weak_min = int(
            self.get_parameter('bump_rumble_weak_min').value
        )

        self.bump_rumble_weak_max = int(
            self.get_parameter('bump_rumble_weak_max').value
        )

        self.bump_rumble_strong_min = int(
            self.get_parameter('bump_rumble_strong_min').value
        )

        self.bump_rumble_strong_max = int(
            self.get_parameter('bump_rumble_strong_max').value
        )

        self.bump_center_kick_enabled = bool(
            self.get_parameter('bump_center_kick_enabled').value
        )

        self.bump_center_kick_min_deg = float(
            self.get_parameter('bump_center_kick_min_deg').value
        )

        self.bump_center_kick_max_deg = float(
            self.get_parameter('bump_center_kick_max_deg').value
        )

        self.bump_center_kick_duration_sec = float(
            self.get_parameter(
                'bump_center_kick_duration_sec'
            ).value
        )

        self.bump_center_kick_frequency_hz = float(
            self.get_parameter(
                'bump_center_kick_frequency_hz'
            ).value
        )

        self.bump_center_kick_coeff = int(
            self.get_parameter('bump_center_kick_coeff').value
        )

        self.bump_center_kick_saturation = int(
            self.get_parameter(
                'bump_center_kick_saturation'
            ).value
        )

        self.bump_constant_kick_enabled = bool(
            self.get_parameter('bump_constant_kick_enabled').value
        )

        self.bump_constant_min_level = int(
            self.get_parameter('bump_constant_min_level').value
        )

        self.bump_constant_max_level = int(
            self.get_parameter('bump_constant_max_level').value
        )

        self.bump_constant_pulse_ms = int(
            self.get_parameter('bump_constant_pulse_ms').value
        )

        self.bump_constant_second_delay_sec = float(
            self.get_parameter(
                'bump_constant_second_delay_sec'
            ).value
        )

        self.bump_periodic_enabled = bool(
            self.get_parameter('bump_periodic_enabled').value
        )

        self.bump_periodic_preload_enabled = bool(
            self.get_parameter(
                'bump_periodic_preload_enabled'
            ).value
        )

        self.bump_periodic_min_magnitude = int(
            self.get_parameter('bump_periodic_min_magnitude').value
        )

        self.bump_periodic_max_magnitude = int(
            self.get_parameter('bump_periodic_max_magnitude').value
        )

        self.bump_periodic_period_ms = int(
            self.get_parameter('bump_periodic_period_ms').value
        )

        self.bump_periodic_duration_ms = int(
            self.get_parameter('bump_periodic_duration_ms').value
        )

        self.bump_periodic_direction = int(
            self.get_parameter('bump_periodic_direction').value
        )

        self.bump_angular_z_weight = float(
            self.get_parameter('bump_angular_z_weight').value
        )

        self.bump_angular_delta_weight = float(
            self.get_parameter('bump_angular_delta_weight').value
        )

        self.bump_debug_enabled = bool(
            self.get_parameter('bump_debug_enabled').value
        )

        self.bump_debug_period_sec = float(
            self.get_parameter('bump_debug_period_sec').value
        )

        self.emergency_feedback_enabled = bool(
            self.get_parameter('emergency_feedback_enabled').value
        )

        self.emergency_feedback_magnitude = int(
            self.get_parameter('emergency_feedback_magnitude').value
        )

        self.emergency_feedback_period_ms = int(
            self.get_parameter('emergency_feedback_period_ms').value
        )

        self.emergency_feedback_duration_ms = int(
            self.get_parameter('emergency_feedback_duration_ms').value
        )

        self.emergency_feedback_direction = int(
            self.get_parameter('emergency_feedback_direction').value
        )

        # カーブ負荷FFB
        self.corner_load_enabled = bool(
            self.get_parameter('corner_load_enabled').value
        )

        self.corner_load_reference = float(
            self.get_parameter('corner_load_reference').value
        )

        self.corner_load_min_speed = float(
            self.get_parameter('corner_load_min_speed').value
        )

        self.corner_load_coeff_gain = int(
            self.get_parameter('corner_load_coeff_gain').value
        )

        self.corner_load_saturation_gain = int(
            self.get_parameter(
                'corner_load_saturation_gain'
            ).value
        )

        self.corner_load_filter_alpha = float(
            self.get_parameter('corner_load_filter_alpha').value
        )

        # カーブ負荷による中心ずらしFFB
        self.corner_center_shift_enabled = bool(
            self.get_parameter('corner_center_shift_enabled').value
        )

        self.corner_center_shift_max_deg = float(
            self.get_parameter('corner_center_shift_max_deg').value
        )

        self.corner_center_shift_min_rate = float(
            self.get_parameter('corner_center_shift_min_rate').value
        )

        self.corner_center_shift_direction = float(
            self.get_parameter('corner_center_shift_direction').value
        )

        # カーブ負荷によるAutocenter補正
        self.corner_autocenter_enabled = bool(
            self.get_parameter('corner_autocenter_enabled').value
        )

        self.corner_autocenter_min_rate = float(
            self.get_parameter('corner_autocenter_min_rate').value
        )

        self.corner_autocenter_max = int(
            self.get_parameter('corner_autocenter_max').value
        )

        self.corner_autocenter_update_threshold = int(
            self.get_parameter(
                'corner_autocenter_update_threshold'
            ).value
        )

        # 高ギアカーブ時のAutocenter切り替え
        self.corner_gate_autocenter_enabled = bool(
            self.get_parameter(
                'corner_gate_autocenter_enabled'
            ).value
        )

        self.corner_gate_min_gear = int(
            self.get_parameter('corner_gate_min_gear').value
        )

        self.corner_gate_min_speed = float(
            self.get_parameter('corner_gate_min_speed').value
        )

        self.corner_gate_min_angular = float(
            self.get_parameter('corner_gate_min_angular').value
        )

        self.corner_gate_min_steering_norm = float(
            self.get_parameter(
                'corner_gate_min_steering_norm'
            ).value
        )

        self.corner_gate_min_load_rate = float(
            self.get_parameter('corner_gate_min_load_rate').value
        )

        self.corner_gate_enter_sec = float(
            self.get_parameter('corner_gate_enter_sec').value
        )

        self.corner_gate_hold_sec = float(
            self.get_parameter('corner_gate_hold_sec').value
        )

        self.corner_gate_autocenter = int(
            self.get_parameter('corner_gate_autocenter').value
        )

        # FF_SPRINGのcenter値上限
        self.spring_center_limit = 32767
    
    
    def initialize_runtime_states(self):
        """
        実行中に変化する状態を初期化する.
        """

        # 現在設定中のAutocenter値
        self.current_autocenter = None

        # 現在のKobuki yaw角[rad]
        self.current_yaw = 0.0
        
        # 前回のyaw.
        self.previous_yaw = None

        # 折り返し補正済みの累積yaw[rad].
        self.accumulated_yaw = 0.0

        # 自律旋回開始時の累積yaw[rad].
        self.auto_start_accumulated_yaw = 0.0

        # FFB計算用のyaw差分[deg].
        self.yaw_delta_deg = 0.0

        # /odomを受信したか
        self.odom_received = False

        # 自律旋回開始時のyaw角[rad]
        self.turn_start_yaw = None

        # 自律旋回中かどうか
        self.auto_turning = False

        # 手動操作中かどうか
        self.manual_active = False

        # 緊急停止ラッチ中かどうか.
        self.emergency_stop_active = False

        # handle.pyから受信した現在ギア.
        self.current_gear = 0

        # handle.pyから受信したステア量[-1.0〜1.0].
        self.steering_norm = 0.0

        # 高ギアカーブ判定中かどうか.
        self.corner_gate_active = False

        # 高ギアカーブ条件を満たし始めた時刻.
        self.corner_gate_candidate_since = None

        # 高ギアカーブ条件を最後に満たした時刻.
        self.corner_gate_last_active_time = 0.0

        # 高ギアカーブ判定の理由.
        self.corner_gate_reason = 'inactive'

        # /cmd_vel_autoを最後に受信した時刻
        self.last_auto_cmd_time = 0.0

        # 目標ハンドル角度[deg]
        self.target_handle_deg = 0.0

        # 自律走行から計算したSpring中心
        self.auto_target_center = 0

        # 現在適用しているSpring中心
        self.applied_center = 0

        # 現在適用しているSpring係数
        self.applied_coeff = self.idle_spring_coeff

        # 現在適用しているSpring上限値
        self.applied_saturation = self.idle_spring_saturation

        # 現在登録しているSpringエフェクトID
        self.spring_effect_id = None
        
        # 現在登録しているDamperエフェクトID
        self.damper_effect_id = None

        # 現在登録している段差RumbleエフェクトID.
        self.bump_effect_id = None

        # 現在登録している段差ConstantエフェクトID.
        self.bump_constant_effect_id = None

        # 現在登録している段差PeriodicエフェクトID.
        self.bump_periodic_effect_id = None

        # 現在登録している緊急停止通知エフェクトID.
        self.emergency_feedback_effect_id = None

        # 最後に段差振動を出した時刻.
        self.last_bump_time = 0.0

        # 前回のIMU角速度.
        self.previous_imu_angular = None

        # 段差検出値の診断用.
        self.bump_debug_last_log_time = 0.0
        self.bump_debug_max_rate = 0.0
        self.bump_debug_last_speed = 0.0

        # 段差Constantキックの2発目管理.
        self.bump_constant_second_due_time = 0.0
        self.bump_constant_second_level = 0

        # 段差時にSpring中心を短時間だけ揺らす状態.
        self.bump_kick_start_time = 0.0
        self.bump_kick_until_time = 0.0
        self.bump_kick_peak_center = 0

        # odomから取得した走行速度[m/s].
        self.odom_linear_x = 0.0

        # odomから取得した旋回角速度[rad/s].
        self.odom_angular_z = 0.0

        # カーブ負荷の生値.
        self.corner_load_raw = 0.0

        # 平滑化したカーブ負荷.
        self.corner_load = 0.0

        # 0.0〜1.0に正規化したカーブ負荷.
        self.corner_load_rate = 0.0

        # カーブ負荷で追加したSpring係数.
        self.corner_extra_coeff = 0

        # カーブ負荷で追加したSpring上限.
        self.corner_extra_saturation = 0

        # カーブ負荷でずらしたSpring中心角度[deg].
        self.corner_center_shift_deg = 0.0

        # カーブ負荷でずらしたSpring中心値.
        self.corner_center_shift_center = 0

        # カーブ負荷で変更したAutocenter値.
        self.corner_autocenter = self.manual_autocenter

        # 最後に送信したSpring設定
        self.last_sent_center = None
        self.last_sent_coeff = None
        self.last_sent_saturation = None

        # 最後にSpringを更新した時刻
        self.last_effect_update_time = 0.0    
    
    def initialize_ffb_device(self):
        """
        G923を開き,待機用Autocenterを設定する.
        """

        self.dev = InputDevice(self.device_path)

        self.get_logger().info(
            f'Opened FFB device: {self.dev.name}'
        )

        self.apply_autocenter(
            self.idle_autocenter
        )
        
        if self.damper_enabled:
            self.play_damper()

        self.prepare_bump_periodic_effect()
        self.prepare_emergency_feedback_effect()
    
    def initialize_ros_interfaces(self):
        """
        ROSの購読とタイマーを作成する.
        """

        # 自律走行の速度指令
        self.create_subscription(
            Twist,
            self.auto_cmd_topic,
            self.auto_cmd_callback,
            10
        )

        # 車体のオドメトリ
        self.create_subscription(
            Odometry,
            self.odom_topic,
            self.odom_callback,
            10
        )

        # 手動介入状態
        self.create_subscription(
            Bool,
            self.manual_active_topic,
            self.manual_active_callback,
            10
        )

        # 緊急停止状態
        self.create_subscription(
            Bool,
            self.emergency_stop_topic,
            self.emergency_stop_callback,
            10
        )

        # 現在ギア
        self.create_subscription(
            Int32,
            self.gear_topic,
            self.gear_callback,
            10
        )

        # ステアリング入力
        self.create_subscription(
            Float32,
            self.steering_norm_topic,
            self.steering_norm_callback,
            10
        )

        if self.bump_feedback_enabled:
            imu_qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.BEST_EFFORT
            )
            self.create_subscription(
                Imu,
                self.imu_topic,
                self.imu_callback,
                imu_qos
            )

        # FFB状態をpublishする.
        self.ffb_mode_pub = self.create_publisher(
            String,
            '/ffb/mode',
            10
        )

        self.yaw_delta_deg_pub = self.create_publisher(
            Float32,
            '/ffb/yaw_delta_deg',
            10
        )

        self.target_handle_deg_pub = self.create_publisher(
            Float32,
            '/ffb/target_handle_deg',
            10
        )

        self.auto_target_center_pub = self.create_publisher(
            Int32,
            '/ffb/auto_target_center',
            10
        )

        self.applied_center_pub = self.create_publisher(
            Int32,
            '/ffb/applied_center',
            10
        )

        self.autocenter_pub = self.create_publisher(
            Int32,
            '/ffb/autocenter',
            10
        )

        self.spring_coeff_pub = self.create_publisher(
            Int32,
            '/ffb/spring_coeff',
            10
        )

        self.spring_saturation_pub = self.create_publisher(
            Int32,
            '/ffb/spring_saturation',
            10
        )

        self.corner_load_pub = self.create_publisher(
            Float32,
            '/ffb/corner_load',
            10
        )

        self.corner_load_rate_pub = self.create_publisher(
            Float32,
            '/ffb/corner_load_rate',
            10
        )

        self.corner_extra_coeff_pub = self.create_publisher(
            Int32,
            '/ffb/corner_extra_coeff',
            10
        )

        self.corner_extra_saturation_pub = self.create_publisher(
            Int32,
            '/ffb/corner_extra_saturation',
            10
        )

        self.corner_center_shift_deg_pub = self.create_publisher(
            Float32,
            '/ffb/corner_center_shift_deg',
            10
        )

        self.corner_center_shift_center_pub = self.create_publisher(
            Int32,
            '/ffb/corner_center_shift_center',
            10
        )

        self.corner_autocenter_pub = self.create_publisher(
            Int32,
            '/ffb/corner_autocenter',
            10
        )

        self.corner_gate_active_pub = self.create_publisher(
            Bool,
            '/ffb/corner_gate_active',
            10
        )

        self.corner_gate_reason_pub = self.create_publisher(
            String,
            '/ffb/corner_gate_reason',
            10
        )

        self.current_gear_pub = self.create_publisher(
            Int32,
            '/ffb/current_gear',
            10
        )

        self.steering_norm_pub = self.create_publisher(
            Float32,
            '/ffb/steering_norm',
            10
        )

        # Spring中心を更新する
        self.create_timer(
            self.spring_update_period,
            self.spring_update_loop
        )
    
    '''
    Autocenter制御
    '''
    def set_autocenter(self, strength):
        
        # G923の標準センタリング力を設定する.
        # strengthは0〜100.
        try:
            result = subprocess.run(
                ['ffset', self.device_path, '-a', str(int(strength))],
                check=False,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.get_logger().warn(
                    f'ffset failed: {result.stderr.strip()}'
                )
                return False

            self.get_logger().info(
                f'Autocenter set to {int(strength)}%'
            )
            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to set autocenter: {e}'
            )
            return False

    def apply_autocenter(self, strength):
        
        # Autocenterの値が変わった場合だけG923へ設定する.
        strength = int(strength)

        if strength == self.current_autocenter:
            return

        if self.set_autocenter(strength):
            self.current_autocenter = strength

    '''
    ROSコールバック
    '''
    def auto_cmd_callback(self, msg):
        # /cmd_vel_autoから自律旋回中かどうかを判定する.
        # 手動介入中は自律走行の旋回をFFBへ反映しない.
        if self.manual_active:
            return

        # odom受信前は旋回を開始しない.
        if not self.odom_received:
            return

        angular = msg.angular.z

        if abs(angular) <= self.auto_angular_threshold:
            return

        now = self.get_clock().now().nanoseconds / 1e9
        self.last_auto_cmd_time = now

        # すでに旋回中なら, 開始位置はそのまま.
        if not self.auto_turning:
            self.auto_turning = True

            # 自律追従中はSpring中心の移動を優先する.
            self.apply_autocenter(self.auto_autocenter)

            # 旋回開始時の累積yawを保存する.
            self.auto_start_accumulated_yaw = self.accumulated_yaw

            self.yaw_delta_deg = 0.0
            self.target_handle_deg = 0.0
            self.auto_target_center = 0

            self.get_logger().info(
                f'Auto turn started. '
                f'start_accumulated_yaw='
                f'{math.degrees(self.auto_start_accumulated_yaw):.1f}deg'
            )

    def odom_callback(self, msg):
        """
        odomからyawを取得し, 累積yawを更新する.
        """
        orientation = msg.pose.pose.orientation

        current_yaw = self.quaternion_to_yaw(
            orientation
        )

        self.current_yaw = current_yaw
        self.odom_received = True

        self.odom_linear_x = msg.twist.twist.linear.x
        self.odom_angular_z = msg.twist.twist.angular.z
        self.update_corner_load()

        # 初回だけ前回yawを初期化する.
        if self.previous_yaw is None:
            self.previous_yaw = current_yaw
            self.accumulated_yaw = 0.0
            return

        # 前回から今回までのyaw変化量だけを正規化する.
        yaw_step = self.normalize_angle(
            current_yaw - self.previous_yaw
        )

        # yawの折り返しをまたいでも累積角として足す.
        self.accumulated_yaw += yaw_step

        # 次回計算用に保存する.
        self.previous_yaw = current_yaw

        # 自律旋回中だけFFB目標角を更新する.
        if not self.auto_turning:
            return

        yaw_delta = (
            self.accumulated_yaw
            - self.auto_start_accumulated_yaw
        )

        if self.invert_yaw_sign:
            yaw_delta *= -1.0

        self.yaw_delta_deg = math.degrees(yaw_delta)

        target_handle_deg = (
            self.yaw_delta_deg
            * self.yaw_to_handle_ratio
        )

        target_handle_deg = max(
            -self.handle_limit_deg,
            min(
                self.handle_limit_deg,
                target_handle_deg
            )
        )

        self.target_handle_deg = target_handle_deg

        # 自律走行用のSpring中心値として保存する.
        self.auto_target_center = self.deg_to_spring_center(
            self.target_handle_deg
        )

    def gear_callback(self, msg):
        # handle.pyから現在ギアを受け取る.
        self.current_gear = int(msg.data)

    def steering_norm_callback(self, msg):
        # handle.pyからステアリング入力を受け取る.
        self.steering_norm = float(msg.data)

    def imu_callback(self, msg):
        """
        KobukiのIMU角速度から段差乗り越え時の揺れを検出する.
        """
        if not self.bump_feedback_enabled:
            return

        angular_x = float(msg.angular_velocity.x)
        angular_y = float(msg.angular_velocity.y)
        angular_z = float(msg.angular_velocity.z)

        angular_delta = 0.0
        if self.previous_imu_angular is not None:
            prev_x, prev_y, prev_z = self.previous_imu_angular
            angular_delta = math.sqrt(
                (angular_x - prev_x) ** 2
                + (angular_y - prev_y) ** 2
                + (angular_z - prev_z) ** 2
            )

        self.previous_imu_angular = (
            angular_x,
            angular_y,
            angular_z
        )

        bump_rate = (
            math.hypot(angular_x, angular_y)
            + abs(angular_z) * self.bump_angular_z_weight
            + angular_delta * self.bump_angular_delta_weight
        )

        now = self.get_clock().now().nanoseconds / 1e9
        self.update_bump_debug(
            bump_rate,
            abs(self.odom_linear_x),
            now
        )

        if abs(self.odom_linear_x) < self.bump_min_speed:
            return

        if bump_rate < self.bump_angular_threshold:
            return

        if (
            now - self.last_bump_time < self.bump_min_interval_sec
            and bump_rate < self.bump_cooldown_override_rate
        ):
            return

        self.last_bump_time = now
        self.play_bump_periodic(bump_rate)
        self.play_bump_constant_kick(bump_rate, angular_x, now)
        self.trigger_bump_center_kick(bump_rate, now)
        self.play_bump_rumble(bump_rate)

    def update_bump_debug(self, bump_rate, speed, now):
        # 段差検出値がしきい値に届いているか確認するためのログ.
        if not self.bump_debug_enabled:
            return

        self.bump_debug_max_rate = max(
            self.bump_debug_max_rate,
            bump_rate
        )
        self.bump_debug_last_speed = speed

        if (
            now - self.bump_debug_last_log_time
            < self.bump_debug_period_sec
        ):
            return

        self.bump_debug_last_log_time = now

        self.get_logger().info(
            f'Bump debug: max_rate={self.bump_debug_max_rate:.3f}, '
            f'threshold={self.bump_angular_threshold:.3f}, '
            f'speed={self.bump_debug_last_speed:.3f}, '
            f'min_speed={self.bump_min_speed:.3f}'
        )
        self.bump_debug_max_rate = 0.0

    def manual_active_callback(self, msg):
        # handle.pyから手動介入状態を受け取る.
        
        new_state = bool(msg.data)

        if new_state == self.manual_active:
            return

        self.manual_active = new_state

        if self.manual_active:
            # 手動中は基本的なセンタリング力を有効にする
            self.apply_autocenter(self.manual_autocenter)

            self.reset_auto_turn()

            self.get_logger().info(
                'Manual override started. '
                f'Autocenter={self.manual_autocenter}'
            )

        else:
            # 手動終了後は待機用の弱いセンタリングへ戻す
            self.apply_autocenter(self.idle_autocenter)

            self.corner_gate_active = False
            self.corner_gate_candidate_since = None
            self.corner_gate_reason = 'manual_inactive'

            self.reset_auto_turn()

            self.get_logger().info(
                'Manual override ended. '
                f'Autocenter={self.idle_autocenter}'
            )

    def emergency_stop_callback(self, msg):
        # 緊急停止のON/OFF変化を軽い振動で通知する.
        new_state = bool(msg.data)

        if new_state == self.emergency_stop_active:
            return

        self.emergency_stop_active = new_state

        if self.play_emergency_feedback():
            state_text = 'activated' if new_state else 'released'
            self.get_logger().info(
                f'Emergency stop feedback: {state_text}'
            )

    """
    現在のFFBモード名を返す.
    """
    def get_ffb_mode(self):
        if self.manual_active:
            return 'manual'

        if self.auto_turning:
            return 'auto'

        return 'idle'

    """
    FFB内部状態をROSトピックへpublishする.
    """
    def publish_ffb_state(self):
        mode_msg = String()
        mode_msg.data = self.get_ffb_mode()
        self.ffb_mode_pub.publish(mode_msg)

        yaw_msg = Float32()
        yaw_msg.data = float(self.yaw_delta_deg)
        self.yaw_delta_deg_pub.publish(yaw_msg)

        target_handle_msg = Float32()
        target_handle_msg.data = float(self.target_handle_deg)
        self.target_handle_deg_pub.publish(target_handle_msg)

        auto_center_msg = Int32()
        auto_center_msg.data = int(self.auto_target_center)
        self.auto_target_center_pub.publish(auto_center_msg)

        applied_center_msg = Int32()
        applied_center_msg.data = int(self.applied_center)
        self.applied_center_pub.publish(applied_center_msg)

        autocenter_msg = Int32()
        autocenter_msg.data = int(self.current_autocenter or 0)
        self.autocenter_pub.publish(autocenter_msg)

        coeff_msg = Int32()
        coeff_msg.data = int(self.applied_coeff)
        self.spring_coeff_pub.publish(coeff_msg)

        saturation_msg = Int32()
        saturation_msg.data = int(self.applied_saturation)
        self.spring_saturation_pub.publish(saturation_msg)

        corner_load_msg = Float32()
        corner_load_msg.data = float(self.corner_load)
        self.corner_load_pub.publish(corner_load_msg)

        corner_rate_msg = Float32()
        corner_rate_msg.data = float(self.corner_load_rate)
        self.corner_load_rate_pub.publish(corner_rate_msg)

        extra_coeff_msg = Int32()
        extra_coeff_msg.data = int(self.corner_extra_coeff)
        self.corner_extra_coeff_pub.publish(extra_coeff_msg)

        extra_saturation_msg = Int32()
        extra_saturation_msg.data = int(self.corner_extra_saturation)
        self.corner_extra_saturation_pub.publish(extra_saturation_msg)

        center_shift_deg_msg = Float32()
        center_shift_deg_msg.data = float(self.corner_center_shift_deg)
        self.corner_center_shift_deg_pub.publish(center_shift_deg_msg)

        center_shift_center_msg = Int32()
        center_shift_center_msg.data = int(self.corner_center_shift_center)
        self.corner_center_shift_center_pub.publish(center_shift_center_msg)

        corner_autocenter_msg = Int32()
        corner_autocenter_msg.data = int(self.corner_autocenter)
        self.corner_autocenter_pub.publish(corner_autocenter_msg)

        gate_active_msg = Bool()
        gate_active_msg.data = bool(self.corner_gate_active)
        self.corner_gate_active_pub.publish(gate_active_msg)

        gate_reason_msg = String()
        gate_reason_msg.data = str(self.corner_gate_reason)
        self.corner_gate_reason_pub.publish(gate_reason_msg)

        gear_msg = Int32()
        gear_msg.data = int(self.current_gear)
        self.current_gear_pub.publish(gear_msg)

        steering_msg = Float32()
        steering_msg.data = float(self.steering_norm)
        self.steering_norm_pub.publish(steering_msg)

    def update_corner_load(self):
        """
        速度と旋回角速度からカーブ負荷を計算する.
        """
        if not self.corner_load_enabled:
            self.corner_load_raw = 0.0
            self.corner_load = 0.0
            self.corner_load_rate = 0.0
            return

        speed = abs(self.odom_linear_x)

        if speed < self.corner_load_min_speed:
            raw_load = 0.0
        else:
            raw_load = abs(
                self.odom_linear_x
                * self.odom_angular_z
            )

        alpha = max(
            0.0,
            min(1.0, self.corner_load_filter_alpha)
        )

        self.corner_load_raw = raw_load
        self.corner_load = (
            (1.0 - alpha) * self.corner_load
            + alpha * raw_load
        )

        reference = max(
            self.corner_load_reference,
            0.001
        )

        self.corner_load_rate = max(
            0.0,
            min(1.0, self.corner_load / reference)
        )

    def apply_corner_load_feedback(
        self,
        desired_coeff,
        desired_saturation
    ):
        """
        カーブ負荷に応じてSpringを重くする.
        """
        self.corner_extra_coeff = 0
        self.corner_extra_saturation = 0

        if not self.corner_load_enabled:
            return desired_coeff, desired_saturation

        if not self.manual_active and not self.auto_turning:
            return desired_coeff, desired_saturation

        self.corner_extra_coeff = int(
            self.corner_load_coeff_gain
            * self.corner_load_rate
        )

        self.corner_extra_saturation = int(
            self.corner_load_saturation_gain
            * self.corner_load_rate
        )

        desired_coeff += self.corner_extra_coeff
        desired_saturation += self.corner_extra_saturation

        desired_coeff = max(
            0,
            min(32767, desired_coeff)
        )

        desired_saturation = max(
            0,
            min(32767, desired_saturation)
        )

        return desired_coeff, desired_saturation

    def apply_corner_center_shift(self, desired_center):
        """
        カーブ負荷に応じてSpring中心を少し外側へずらす.
        """
        self.corner_center_shift_deg = 0.0
        self.corner_center_shift_center = 0

        if not self.corner_center_shift_enabled:
            return desired_center

        # 操作者へ伝える目的なので手動操作中だけ使う.
        if not self.manual_active:
            return desired_center

        if self.corner_load_rate <= self.corner_center_shift_min_rate:
            return desired_center

        if abs(self.odom_angular_z) <= 0.03:
            return desired_center

        rate = (
            self.corner_load_rate
            - self.corner_center_shift_min_rate
        ) / (
            1.0 - self.corner_center_shift_min_rate
        )

        rate = max(
            0.0,
            min(1.0, rate)
        )

        curve_direction = math.copysign(
            1.0,
            self.odom_angular_z
        )

        shift_deg = (
            curve_direction
            * self.corner_center_shift_direction
            * self.corner_center_shift_max_deg
            * rate
        )

        shift_center = self.deg_to_spring_center(
            shift_deg
        )

        self.corner_center_shift_deg = shift_deg
        self.corner_center_shift_center = shift_center

        shifted_center = desired_center + shift_center

        shifted_center = max(
            -self.spring_center_limit,
            min(
                self.spring_center_limit,
                shifted_center
            )
        )

        return shifted_center

    def is_corner_gate_condition_met(self):
        """
        高ギアかつ一定以上のカーブ状態かを判定する.
        """
        if not self.manual_active:
            self.corner_gate_reason = 'manual_inactive'
            return False

        if self.current_gear < self.corner_gate_min_gear:
            self.corner_gate_reason = 'gear_low'
            return False

        if abs(self.odom_linear_x) < self.corner_gate_min_speed:
            self.corner_gate_reason = 'speed_low'
            return False

        if abs(self.steering_norm) < self.corner_gate_min_steering_norm:
            self.corner_gate_reason = 'steering_small'
            return False

        angular_ok = (
            abs(self.odom_angular_z)
            >= self.corner_gate_min_angular
        )

        load_ok = (
            self.corner_load_rate
            >= self.corner_gate_min_load_rate
        )

        if not angular_ok and not load_ok:
            self.corner_gate_reason = 'curve_small'
            return False

        self.corner_gate_reason = 'active_condition'
        return True

    def update_corner_gate_state(self):
        """
        高ギアカーブ状態を時間条件付きでON/OFFする.
        """
        now = self.get_clock().now().nanoseconds / 1e9

        if not self.corner_gate_autocenter_enabled:
            self.corner_gate_active = False
            self.corner_gate_candidate_since = None
            self.corner_gate_reason = 'gate_disabled'
            return

        condition_met = self.is_corner_gate_condition_met()

        if condition_met:
            if self.corner_gate_candidate_since is None:
                self.corner_gate_candidate_since = now

            elapsed = now - self.corner_gate_candidate_since

            if elapsed >= self.corner_gate_enter_sec:
                self.corner_gate_active = True
                self.corner_gate_last_active_time = now
                self.corner_gate_reason = 'active'

            return

        self.corner_gate_candidate_since = None

        if not self.corner_gate_active:
            return

        # 条件が一瞬だけ外れても, 少しだけ重さを維持する.
        if now - self.corner_gate_last_active_time <= self.corner_gate_hold_sec:
            self.corner_gate_reason = 'hold'
            return

        self.corner_gate_active = False

    def calculate_corner_autocenter(self):
        """
        カーブ状態に応じて手動中のAutocenter値を決める.
        """
        self.corner_autocenter = int(self.manual_autocenter)

        if not self.manual_active:
            return self.corner_autocenter

        if self.corner_gate_autocenter_enabled:
            self.update_corner_gate_state()

            if self.corner_gate_active:
                self.corner_autocenter = int(
                    self.corner_gate_autocenter
                )
                return self.corner_autocenter

            return self.corner_autocenter

        if not self.corner_autocenter_enabled:
            return self.corner_autocenter

        if self.corner_load_rate <= self.corner_autocenter_min_rate:
            return self.corner_autocenter

        rate = (
            self.corner_load_rate
            - self.corner_autocenter_min_rate
        ) / (
            1.0 - self.corner_autocenter_min_rate
        )

        rate = max(
            0.0,
            min(1.0, rate)
        )

        target_autocenter = (
            self.manual_autocenter
            + (self.corner_autocenter_max - self.manual_autocenter)
            * rate
        )

        target_autocenter = max(
            0,
            min(100, int(round(target_autocenter)))
        )

        self.corner_autocenter = target_autocenter
        return self.corner_autocenter

    def update_manual_autocenter(self):
        """
        手動中だけカーブ負荷に応じてAutocenterを変更する.
        """
        if not self.manual_active:
            self.corner_autocenter = int(self.manual_autocenter)
            self.corner_gate_active = False
            self.corner_gate_candidate_since = None
            return

        target_autocenter = self.calculate_corner_autocenter()

        if self.current_autocenter is None:
            self.apply_autocenter(target_autocenter)
            return

        # カーブが終わったら基本値へ確実に戻す.
        if (
            target_autocenter == self.manual_autocenter
            and self.current_autocenter != self.manual_autocenter
        ):
            self.apply_autocenter(target_autocenter)
            return

        # 小さな変化ではffsetを連発しない.
        if (
            abs(target_autocenter - self.current_autocenter)
            >= self.corner_autocenter_update_threshold
        ):
            self.apply_autocenter(target_autocenter)

    '''
    Spring更新処理
    '''
    def spring_update_loop(self):
        # 状態に応じてSpring中心と強さを更新する.
        
        now = self.get_clock().now().nanoseconds / 1e9

        self.update_bump_constant_second_pulse(now)

        # 旋回指令が一定時間来なければ,自律旋回終了と判断する
        if (
            self.auto_turning
            and not self.manual_active
            and now - self.last_auto_cmd_time > self.auto_cmd_timeout
        ):
            self.reset_auto_turn()

            # 自律旋回終了後は弱いセンタリングを戻す
            self.apply_autocenter(self.idle_autocenter)

            self.get_logger().info(
                'Auto turn ended. '
                f'Autocenter={self.idle_autocenter}'
            )

        # 手動中はカーブ負荷に応じてAutocenterを変える.
        self.update_manual_autocenter()

        # 手動操作中は物理中心へ戻る反力を与える
        if self.manual_active:
            desired_center = 0
            desired_coeff = self.manual_spring_coeff
            desired_saturation = self.manual_spring_saturation

        # 自律旋回中はKobukiの旋回量へ追従する
        elif self.auto_turning:
            desired_center = self.auto_target_center
            desired_coeff = self.auto_spring_coeff
            desired_saturation = self.auto_spring_saturation

        # 自律旋回終了後や待機中も,弱い中心復帰力を残す
        else:
            desired_center = 0
            desired_coeff = self.idle_spring_coeff
            desired_saturation = self.idle_spring_saturation

        desired_coeff, desired_saturation = (
            self.apply_corner_load_feedback(
                desired_coeff,
                desired_saturation
            )
        )

        desired_center = self.apply_corner_center_shift(
            desired_center
        )

        # Spring中心を目標へ少しずつ移動する
        self.applied_center = self.move_toward(
            self.applied_center,
            desired_center,
            self.max_center_step
        )

        # Springの強さも滑らかに変える
        self.applied_coeff = self.move_toward(
            self.applied_coeff,
            desired_coeff,
            self.coeff_step
        )

        self.applied_saturation = self.move_toward(
            self.applied_saturation,
            desired_saturation,
            self.saturation_step
        )

        if now < self.bump_kick_until_time:
            self.applied_coeff = max(
                self.applied_coeff,
                self.bump_center_kick_coeff
            )
            self.applied_saturation = max(
                self.applied_saturation,
                self.bump_center_kick_saturation
            )

        center_to_send = self.apply_bump_center_offset(
            self.applied_center,
            now
        )

        # FFB内部状態をROSトピックへpublishする.
        self.publish_ffb_state()

        # 変化が小さい場合は更新を省略する
        if not self.should_update_spring(now):
            return

        # Springを停止せず,同じeffect_idで更新する
        if self.play_spring(center_to_send):
            self.last_sent_center = center_to_send
            self.last_sent_coeff = self.applied_coeff
            self.last_sent_saturation = self.applied_saturation
            self.last_effect_update_time = now

    def should_update_spring(self, now):
        # Spring更新が必要か判断する.
        
        if self.spring_effect_id is None:
            return True

        if self.last_sent_center is None:
            return True

        center_changed = (
            abs(self.applied_center - self.last_sent_center)
            >= self.center_send_threshold
        )

        coeff_changed = (
            abs(self.applied_coeff - self.last_sent_coeff)
            >= self.coeff_send_threshold
        )

        saturation_changed = (
            abs(
                self.applied_saturation
                - self.last_sent_saturation
            )
            >= self.saturation_send_threshold
        )

        refresh_required = (
            now - self.last_effect_update_time
            >= self.effect_refresh_sec
        )

        return (
            center_changed
            or coeff_changed
            or saturation_changed
            or now < self.bump_kick_until_time
            or refresh_required
        )

    def reset_auto_turn(self):
        """
        自律旋回状態をリセットする.
        """
        self.auto_turning = False

        # 次の旋回開始時に現在位置から計測できるようにする.
        self.auto_start_accumulated_yaw = self.accumulated_yaw

        self.yaw_delta_deg = 0.0
        self.target_handle_deg = 0.0
        self.auto_target_center = 0
        self.turn_start_yaw = None

    @staticmethod
    def move_toward(current, target, step):
        # 現在値を目標値へstep以内で近づける.
        
        if abs(target - current) <= step:
            return target

        if target > current:
            return current + step

        return current - step

    def deg_delta_to_spring_center(self, deg):
        # 角度差[deg]をFF_SPRINGのcenter差分へ変換する.
        center = int(
            deg
            / self.handle_limit_deg
            * self.spring_center_limit
        )

        return max(
            -self.spring_center_limit,
            min(self.spring_center_limit, center)
        )

    def bump_strength_rate(self, bump_rate):
        # 段差検出値を0.0〜1.0へ正規化する.
        scale_denominator = max(
            self.bump_angular_full_scale
            - self.bump_angular_threshold,
            0.001
        )

        strength_rate = (
            bump_rate
            - self.bump_angular_threshold
        ) / scale_denominator

        return max(
            0.0,
            min(1.0, strength_rate)
        )

    def trigger_bump_center_kick(self, bump_rate, now):
        """
        段差をSpring中心の短い左右キックとしてハンドルへ返す.
        """
        if not self.bump_center_kick_enabled:
            return

        strength_rate = self.bump_strength_rate(bump_rate)

        kick_deg = self.bump_center_kick_min_deg + (
            self.bump_center_kick_max_deg
            - self.bump_center_kick_min_deg
        ) * strength_rate

        self.bump_kick_peak_center = self.deg_delta_to_spring_center(
            kick_deg
        )
        self.bump_kick_start_time = now
        self.bump_kick_until_time = (
            now
            + self.bump_center_kick_duration_sec
        )

        self.get_logger().info(
            f'Bump center kick: rate={bump_rate:.3f}, '
            f'kick_deg={kick_deg:.1f}, '
            f'peak_center={self.bump_kick_peak_center}'
        )

    def calculate_bump_center_offset(self, now):
        # 段差キック中だけ減衰する左右オフセットを返す.
        if now >= self.bump_kick_until_time:
            return 0

        duration = max(
            self.bump_center_kick_duration_sec,
            0.001
        )
        elapsed = max(
            0.0,
            now - self.bump_kick_start_time
        )
        progress = min(
            1.0,
            elapsed / duration
        )

        decay = 1.0 - progress
        phase = (
            2.0
            * math.pi
            * self.bump_center_kick_frequency_hz
            * elapsed
        )
        direction = 1.0 if math.sin(phase) >= 0.0 else -1.0

        return int(
            self.bump_kick_peak_center
            * direction
            * decay
        )

    def apply_bump_center_offset(self, center, now):
        # Springの通常中心に段差キック分を重ねる.
        kicked_center = center + self.calculate_bump_center_offset(now)

        return max(
            -self.spring_center_limit,
            min(self.spring_center_limit, kicked_center)
        )

    """
    Springエフェクト
    """
    def deg_to_spring_center(self, deg):
        # ハンドル角度[deg]をFF_SPRINGのcenter値へ変換する.
        # center_offset_degで実機のセンターずれを補正する.
        
        # センターズレを補正
        corrected_deg = deg + self.center_offset_deg

        # (補正後の角度 / 450) * 32767 でcenter値を計算
        center = int(
            corrected_deg
            / self.handle_limit_deg
            * self.spring_center_limit
        )

        return max(
            -self.spring_center_limit,
            min(self.spring_center_limit, center)
        )

    def make_spring_effect(self, center, effect_id=-1):
        # 状態に応じた中心位置と強さでSpringを作る.
        
        condition = ff.Condition(
            int(self.applied_saturation),
            int(self.applied_saturation),
            int(self.applied_coeff),
            int(self.applied_coeff),
            int(self.spring_deadband),
            int(center)
        )

        return ff.Effect(
            ecodes.FF_SPRING,
            effect_id,
            0,
            ff.Trigger(0, 0),
            ff.Replay(self.spring_replay_ms, 0),
            ff.EffectType(
                ff_condition_effect=(condition, condition)
            )
        )

    def play_spring(self, center):
        # Springを停止せず,再生中のエフェクトを更新する.
        
        try:
            # まだSpringを作っていない場合
            if self.spring_effect_id is None:
                effect = self.make_spring_effect(
                    center=center,
                    effect_id=-1
                )

                self.spring_effect_id = self.dev.upload_effect(effect)
                self.dev.write(
                    ecodes.EV_FF,
                    self.spring_effect_id,
                    1
                )

            # すでに再生中なら同じIDで内容だけ更新する
            else:
                effect = self.make_spring_effect(
                    center=center,
                    effect_id=self.spring_effect_id
                )

                updated_id = self.dev.upload_effect(effect)

                if updated_id is not None:
                    self.spring_effect_id = updated_id

            return True

        except Exception as e:
            self.get_logger().error(
                f'Failed to update spring: {e}'
            )
            return False

    """
    Damperエフェクト
    """
    def make_damper_effect(self, effect_id=-1):
        # ハンドルを動かす速さに対して抵抗を与える.
        
        condition = ff.Condition(
            int(self.damper_saturation),
            int(self.damper_saturation),
            int(self.damper_coeff),
            int(self.damper_coeff),
            int(self.damper_deadband),
            0
        )

        return ff.Effect(
            ecodes.FF_DAMPER,
            effect_id,
            0,
            ff.Trigger(0, 0),
            ff.Replay(self.spring_replay_ms, 0),
            ff.EffectType(
                ff_condition_effect=(condition, condition)
            )
        )

    def play_damper(self):
        # Damperを再生する.
        
        if not self.damper_enabled:
            return False

        try:
            if self.damper_effect_id is None:
                effect = self.make_damper_effect(
                    effect_id=-1
                )

                self.damper_effect_id = self.dev.upload_effect(
                    effect
                )

                self.dev.write(
                    ecodes.EV_FF,
                    self.damper_effect_id,
                    1
                )

                self.get_logger().info(
                    'Damper effect started.'
                )

            else:
                effect = self.make_damper_effect(
                    effect_id=self.damper_effect_id
                )

                updated_id = self.dev.upload_effect(effect)

                if updated_id is not None:
                    self.damper_effect_id = updated_id

            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to update damper: {e}'
            )
            return False

    def stop_damper(self):
        # 現在再生中のDamperエフェクトを停止・削除する.
        
        if self.damper_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.damper_effect_id,
                0
            )

            self.dev.erase_effect(
                self.damper_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop damper: {e}'
            )

        finally:
            self.damper_effect_id = None

    """
    緊急停止通知エフェクト
    """
    def make_emergency_feedback_effect(self, effect_id=-1):
        # 緊急停止のON/OFFを短く軽い振動として通知する.
        envelope = ff.Envelope(
            0,
            0,
            int(self.emergency_feedback_duration_ms),
            0
        )
        periodic = ff.Periodic(
            ecodes.FF_SQUARE,
            int(self.emergency_feedback_period_ms),
            int(self.emergency_feedback_magnitude),
            0,
            0,
            envelope,
            0,
            None
        )

        return ff.Effect(
            ecodes.FF_PERIODIC,
            effect_id,
            int(self.emergency_feedback_direction),
            ff.Trigger(0, 0),
            ff.Replay(self.emergency_feedback_duration_ms, 0),
            ff.EffectType(
                ff_periodic_effect=periodic
            )
        )

    def prepare_emergency_feedback_effect(self):
        if not self.emergency_feedback_enabled:
            return False

        if self.emergency_feedback_effect_id is not None:
            return True

        try:
            effect = self.make_emergency_feedback_effect()
            updated_id = self.dev.upload_effect(effect)

            if updated_id is None:
                return False

            self.emergency_feedback_effect_id = updated_id
            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to preload emergency feedback: {e}'
            )
            return False

    def play_emergency_feedback(self):
        if not self.prepare_emergency_feedback_effect():
            return False

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.emergency_feedback_effect_id,
                0
            )
            self.dev.write(
                ecodes.EV_FF,
                self.emergency_feedback_effect_id,
                1
            )
            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to play emergency feedback: {e}'
            )
            return False

    def stop_emergency_feedback(self):
        if self.emergency_feedback_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.emergency_feedback_effect_id,
                0
            )
            self.dev.erase_effect(
                self.emergency_feedback_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop emergency feedback: {e}'
            )

        finally:
            self.emergency_feedback_effect_id = None

    """
    段差Rumbleエフェクト
    """
    def make_bump_rumble_effect(self, weak, strong, effect_id=-1):
        # 段差を短い振動としてハンドルへ返す.
        rumble = ff.Rumble(
            int(strong),
            int(weak)
        )

        return ff.Effect(
            ecodes.FF_RUMBLE,
            effect_id,
            0,
            ff.Trigger(0, 0),
            ff.Replay(self.bump_rumble_duration_ms, 0),
            ff.EffectType(
                ff_rumble_effect=rumble
            )
        )

    def play_bump_rumble(self, bump_rate):
        # 段差の大きさに応じてRumbleの強さを変える.
        if not self.bump_rumble_enabled:
            return False

        scale_denominator = max(
            self.bump_angular_full_scale
            - self.bump_angular_threshold,
            0.001
        )

        strength_rate = (
            bump_rate
            - self.bump_angular_threshold
        ) / scale_denominator

        strength_rate = max(
            0.0,
            min(1.0, strength_rate)
        )

        weak = self.bump_rumble_weak_min + (
            self.bump_rumble_weak_max
            - self.bump_rumble_weak_min
        ) * strength_rate

        strong = self.bump_rumble_strong_min + (
            self.bump_rumble_strong_max
            - self.bump_rumble_strong_min
        ) * strength_rate

        try:
            effect = self.make_bump_rumble_effect(
                weak=weak,
                strong=strong,
                effect_id=(
                    -1
                    if self.bump_effect_id is None
                    else self.bump_effect_id
                )
            )

            updated_id = self.dev.upload_effect(effect)

            if updated_id is not None:
                self.bump_effect_id = updated_id

            self.dev.write(
                ecodes.EV_FF,
                self.bump_effect_id,
                1
            )

            self.get_logger().info(
                f'Bump rumble: rate={bump_rate:.3f}, '
                f'weak={int(weak)}, strong={int(strong)}'
            )

            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to play bump rumble: {e}'
            )
            return False

    def stop_bump_rumble(self):
        # 現在登録している段差Rumbleエフェクトを停止・削除する.
        if self.bump_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.bump_effect_id,
                0
            )
            self.dev.erase_effect(
                self.bump_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop bump rumble: {e}'
            )

        finally:
            self.bump_effect_id = None

    """
    段差Periodicエフェクト
    """
    def make_bump_periodic_effect(self, magnitude, effect_id=-1):
        # 段差を短い周期トルクとしてハンドルへ返す.
        envelope = ff.Envelope(
            0,
            0,
            int(self.bump_periodic_duration_ms),
            0
        )
        periodic = ff.Periodic(
            ecodes.FF_SQUARE,
            int(self.bump_periodic_period_ms),
            int(magnitude),
            0,
            0,
            envelope,
            0,
            None
        )

        return ff.Effect(
            ecodes.FF_PERIODIC,
            effect_id,
            int(self.bump_periodic_direction),
            ff.Trigger(0, 0),
            ff.Replay(self.bump_periodic_duration_ms, 0),
            ff.EffectType(
                ff_periodic_effect=periodic
            )
        )

    def prepare_bump_periodic_effect(self):
        # 段差検出時の遅延を避けるため,周期エフェクトを先に登録する.
        if not self.bump_periodic_enabled:
            return False

        if not self.bump_periodic_preload_enabled:
            return False

        if self.bump_periodic_effect_id is not None:
            return True

        try:
            effect = self.make_bump_periodic_effect(
                magnitude=self.bump_periodic_max_magnitude,
                effect_id=-1
            )
            updated_id = self.dev.upload_effect(effect)

            if updated_id is None:
                return False

            self.bump_periodic_effect_id = updated_id
            self.get_logger().info(
                f'Bump periodic preloaded: '
                f'effect_id={self.bump_periodic_effect_id}, '
                f'magnitude={self.bump_periodic_max_magnitude}, '
                f'period_ms={self.bump_periodic_period_ms}, '
                f'duration_ms={self.bump_periodic_duration_ms}'
            )
            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to preload bump periodic: {e}'
            )
            return False

    def play_bump_periodic(self, bump_rate):
        if not self.bump_periodic_enabled:
            return False

        strength_rate = self.bump_strength_rate(bump_rate)
        magnitude = self.bump_periodic_min_magnitude + (
            self.bump_periodic_max_magnitude
            - self.bump_periodic_min_magnitude
        ) * strength_rate

        try:
            if self.bump_periodic_preload_enabled:
                if not self.prepare_bump_periodic_effect():
                    return False

            else:
                effect = self.make_bump_periodic_effect(
                    magnitude=magnitude,
                    effect_id=(
                        -1
                        if self.bump_periodic_effect_id is None
                        else self.bump_periodic_effect_id
                    )
                )

                updated_id = self.dev.upload_effect(effect)

                if updated_id is not None:
                    self.bump_periodic_effect_id = updated_id

            self.dev.write(
                ecodes.EV_FF,
                self.bump_periodic_effect_id,
                0
            )

            self.dev.write(
                ecodes.EV_FF,
                self.bump_periodic_effect_id,
                1
            )

            self.get_logger().info(
                f'Bump periodic: rate={bump_rate:.3f}, '
                f'magnitude={int(magnitude)}, '
                f'period_ms={self.bump_periodic_period_ms}, '
                f'preloaded={self.bump_periodic_preload_enabled}'
            )

            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to play bump periodic: {e}'
            )
            return False

    def stop_bump_periodic(self):
        if self.bump_periodic_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.bump_periodic_effect_id,
                0
            )
            self.dev.erase_effect(
                self.bump_periodic_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop bump periodic: {e}'
            )

        finally:
            self.bump_periodic_effect_id = None

    """
    段差Constantキック
    """
    def make_bump_constant_effect(self, level, effect_id=-1):
        # ハンドルへ短い直接トルクを入れる.
        envelope = ff.Envelope(
            0,
            0,
            int(self.bump_constant_pulse_ms),
            0
        )
        constant = ff.Constant(
            int(level),
            envelope
        )

        return ff.Effect(
            ecodes.FF_CONSTANT,
            effect_id,
            0,
            ff.Trigger(0, 0),
            ff.Replay(self.bump_constant_pulse_ms, 0),
            ff.EffectType(
                ff_constant_effect=constant
            )
        )

    def upload_bump_constant_effect(self, level):
        effect = self.make_bump_constant_effect(
            level=level,
            effect_id=(
                -1
                if self.bump_constant_effect_id is None
                else self.bump_constant_effect_id
            )
        )

        updated_id = self.dev.upload_effect(effect)

        if updated_id is not None:
            self.bump_constant_effect_id = updated_id

    def play_bump_constant_level(self, level):
        try:
            self.upload_bump_constant_effect(level)
            self.dev.write(
                ecodes.EV_FF,
                self.bump_constant_effect_id,
                1
            )
            return True

        except Exception as e:
            self.get_logger().warn(
                f'Failed to play bump constant kick: {e}'
            )
            return False

    def play_bump_constant_kick(self, bump_rate, angular_x, now):
        # 直接トルクを左右2発で入れて段差感を作る.
        if not self.bump_constant_kick_enabled:
            return False

        strength_rate = self.bump_strength_rate(bump_rate)
        level = self.bump_constant_min_level + (
            self.bump_constant_max_level
            - self.bump_constant_min_level
        ) * strength_rate

        # ピッチ方向の揺れに合わせて初撃方向を変える.
        direction = -1 if angular_x < 0.0 else 1
        first_level = int(level * direction)
        second_level = -first_level

        if self.play_bump_constant_level(first_level):
            self.bump_constant_second_level = second_level
            self.bump_constant_second_due_time = (
                now
                + self.bump_constant_second_delay_sec
            )
            self.get_logger().info(
                f'Bump constant kick: rate={bump_rate:.3f}, '
                f'level={first_level}, next={second_level}'
            )
            return True

        return False

    def update_bump_constant_second_pulse(self, now):
        # 2発目の逆向きトルクを短い遅延で出す.
        if self.bump_constant_second_due_time <= 0.0:
            return

        if now < self.bump_constant_second_due_time:
            return

        level = self.bump_constant_second_level
        self.bump_constant_second_due_time = 0.0
        self.bump_constant_second_level = 0
        self.play_bump_constant_level(level)

    def stop_bump_constant(self):
        # 現在登録している段差Constantエフェクトを停止・削除する.
        if self.bump_constant_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.bump_constant_effect_id,
                0
            )
            self.dev.erase_effect(
                self.bump_constant_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop bump constant kick: {e}'
            )

        finally:
            self.bump_constant_effect_id = None
    
    def stop_spring(self):
        # 現在再生中のSpringエフェクトを停止・削除する.
        
        if self.spring_effect_id is None:
            return

        try:
            self.dev.write(
                ecodes.EV_FF,
                self.spring_effect_id,
                0
            )
            self.dev.erase_effect(
                self.spring_effect_id
            )

        except Exception as e:
            self.get_logger().warn(
                f'Failed to stop spring: {e}'
            )

        finally:
            self.spring_effect_id = None

    """
    角度計算
    """
    @staticmethod
    def quaternion_to_yaw(q):
        # OdometryのQuaternion姿勢からyaw角だけを取り出す.
        
        siny_cosp = 2.0 * (
            q.w * q.z
            + q.x * q.y
        )

        cosy_cosp = 1.0 - 2.0 * (
            q.y * q.y
            + q.z * q.z
        )

        return math.atan2(
            siny_cosp,
            cosy_cosp
        )

    @staticmethod
    def normalize_angle(angle):
        # 角度を-pi〜piの範囲に収める.
        
        while angle > math.pi:
            angle -= 2.0 * math.pi

        while angle < -math.pi:
            angle += 2.0 * math.pi

        return angle

    """
    終了処理
    """
    def destroy_node(self):
        #ノード終了時の処理.
        #Springを止めて,通常のセンタリング力を戻す.
        
        self.stop_spring()
        self.stop_damper()
        self.stop_bump_rumble()
        self.stop_bump_constant()
        self.stop_bump_periodic()
        self.stop_emergency_feedback()

        self.set_autocenter(
            self.shutdown_autocenter
        )

        try:
            self.dev.close()

        except Exception:
            pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = FfbFollowNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
