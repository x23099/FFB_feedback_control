#!/usr/bin/env python3

import math
import subprocess

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
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

            self.reset_auto_turn()

            self.get_logger().info(
                'Manual override ended. '
                f'Autocenter={self.idle_autocenter}'
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

    '''
    Spring更新処理
    '''
    def spring_update_loop(self):
        # 状態に応じてSpring中心と強さを更新する.
        
        now = self.get_clock().now().nanoseconds / 1e9

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

        # FFB内部状態をROSトピックへpublishする.
        self.publish_ffb_state()

        # 変化が小さい場合は更新を省略する
        if not self.should_update_spring(now):
            return

        # Springを停止せず,同じeffect_idで更新する
        if self.play_spring(self.applied_center):
            self.last_sent_center = self.applied_center
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