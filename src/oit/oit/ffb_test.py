#!/usr/bin/env python3

import math
import subprocess

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32

from evdev import InputDevice, ecodes, ff


class FfbFollowNode(Node):
    def __init__(self):
        super().__init__('ffb_follow_node')

        # G923のFFB対応eventデバイス。
        self.device_path = (
            '/dev/input/by-id/'
            'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
            'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
        )

        # G923を開く。
        self.dev = InputDevice(self.device_path)
        self.get_logger().info(f'Opened FFB device: {self.dev.name}')

        # 実験中はセンタリングを弱める。
        self.set_autocenter(10)

        # FFB方向設定
        self.RIGHT_DIR = 0x4000
        self.LEFT_DIR = 0xC000
        
        # 左右の限界角度
        self.handle_limit_deg = 450.0

        # Kobukiが360度回ったとき、ハンドルは450度回るとみなす。
        # 90度旋回なら 90 * 450 / 360 = 112.5度。
        self.kobuki_to_handle_ratio = 450.0 / 360.0

        # 現在のハンドル角度。
        # handle.py の /handle/steering_angle_deg から受け取る。
        self.current_handle_deg = 0.0

        # FFBで動かしたい目標ハンドル角度。
        self.target_handle_deg = 0.0

        # ============================================================
        # Kobukiの旋回管理
        # ============================================================
        self.current_yaw = 0.0
        self.turn_start_yaw = None
        self.auto_turning = False

        # /cmd_vel_auto が最後に来た時刻。
        self.last_auto_cmd_time = 0.0

        # 自律旋回指令がこの秒数以上来なければ旋回終了とみなす。
        self.auto_cmd_timeout = 0.3

        # この値以上のangular.zなら旋回中とみなす。
        self.auto_angular_threshold = 0.05

        # ============================================================
        # FFB制御パラメータ
        # ============================================================
        # 角度誤差[deg]に対してどれくらい力を出すか。
        # 大きいほど強く反応する。
        self.kp = 100.0

        # 最小FFB力。
        # 小さすぎるとログは出てもハンドルが動かない。
        self.min_level = 0x1800

        # 最大FFB力。
        # 大きすぎると一気に端まで回る。
        self.max_level = 0x3800

        # 目標角との差がこの範囲内ならFFBを止める。
        self.deadzone_deg = 5.0

        # FFB力を一度に変化させる最大量。
        # 小さいほどなめらか、大きいほど素早い。
        self.level_step = 0x0400

        # 現在出しているFFB状態。
        self.current_level = 0
        self.current_direction = 0x0000

        # evdevに登録したFFBエフェクトID。
        self.effect_id = None
        self.last_level = 0
        self.last_direction = 0x0000

        # ============================================================
        # ROS購読
        # ============================================================
        # 自律走行の速度指令。旋回開始・終了の判定に使う。
        self.create_subscription(
            Twist,
            '/cmd_vel_auto',
            self.auto_cmd_callback,
            10
        )

        # Kobukiの自己位置。yaw角を取り出して、実際に何度回ったか計算する。
        self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # handle.pyがpublishする現在ハンドル角度。
        self.create_subscription(
            Float32,
            '/handle/steering_angle_deg',
            self.handle_angle_callback,
            10
        )

        # 20HzでFFBを更新する。
        self.create_timer(0.05, self.ffb_update_loop)

        self.get_logger().info('FFB follow node started.')

    def set_autocenter(self, strength):
        """
        G923の自動センタリング力を設定する。
        strengthは0〜100。
        """
        try:
            subprocess.run(
                ['ffset', self.device_path, '-a', str(strength)],
                check=False
            )
            self.get_logger().info(f'Autocenter set to {strength}%')

        except Exception as e:
            self.get_logger().warn(f'Failed to set autocenter: {e}')

    def handle_angle_callback(self, msg):
        """
        handle.pyから現在のハンドル角度[deg]を受け取る。
        例：
          右112.5度 → 112.5
          中心       → 0.0
          左112.5度 → -112.5
        """
        self.current_handle_deg = msg.data

    def auto_cmd_callback(self, msg):
        """
        /cmd_vel_autoから自律旋回中かどうかを判定する。
        angular.zが一定以上なら、Kobukiが自律旋回しているとみなす。
        """
        angular = msg.angular.z

        if abs(angular) > self.auto_angular_threshold:
            now = self.get_clock().now().nanoseconds / 1e9
            self.last_auto_cmd_time = now

            # 旋回が始まった瞬間だけ、開始時のyawを保存する。
            if not self.auto_turning:
                self.auto_turning = True
                self.turn_start_yaw = self.current_yaw
                self.target_handle_deg = 0.0

                self.get_logger().info(
                    f'Auto turn started. start_yaw={math.degrees(self.turn_start_yaw):.1f}deg'
                )

    def odom_callback(self, msg):
        """
        /odomからKobukiの現在yaw角を取り出す。
        自律旋回中なら、旋回開始時からの角度差を計算し、
        それに比例した目標ハンドル角を作る。
        """
        self.current_yaw = self.quaternion_to_yaw(msg.pose.pose.orientation)

        if not self.auto_turning:
            return

        if self.turn_start_yaw is None:
            return

        # 旋回開始時からのyaw差分[rad]。
        yaw_delta = self.normalize_angle(self.current_yaw - self.turn_start_yaw)

        # degに変換。
        yaw_delta_deg = math.degrees(yaw_delta)

        # Kobukiの旋回角から目標ハンドル角を計算する。
        # 例：Kobuki 90度 → ハンドル 112.5度。
        target = yaw_delta_deg * self.kobuki_to_handle_ratio

        # ハンドルの物理限界を超えないように制限する。
        target = max(-self.handle_limit_deg, min(self.handle_limit_deg, target))

        self.target_handle_deg = target

    def ffb_update_loop(self):
        """
        目標ハンドル角と現在ハンドル角の差からFFBを出す。
        ここでは角度命令を送っているのではなく、
        目標角に近づく方向へ力を出している。
        """
        now = self.get_clock().now().nanoseconds / 1e9

        # 自律旋回指令がしばらく来なければ旋回終了とみなす。
        if self.auto_turning and now - self.last_auto_cmd_time > self.auto_cmd_timeout:
            self.auto_turning = False
            self.turn_start_yaw = None
            self.target_handle_deg = 0.0

            self.current_level = 0
            self.stop_effect()

            self.get_logger().info('Auto turn ended.')
            return

        # 自律旋回中でなければFFBを出さない。
        if not self.auto_turning:
            self.stop_effect()
            return

        # 目標角と現在角の差。
        error_deg = self.target_handle_deg - self.current_handle_deg

        # 目標角付近ならFFBを止める。
        if abs(error_deg) < self.deadzone_deg:
            self.current_level = 0
            self.stop_effect()
            return

        # 目標より左にいるなら右へ、目標より右にいるなら左へ力を出す。
        if error_deg > 0:
            target_direction = self.RIGHT_DIR
        else:
            target_direction = self.LEFT_DIR

        # 誤差が大きいほど強い力を出す。
        target_level = int(abs(error_deg) * self.kp)

        # 力の範囲を制限する。
        target_level = max(self.min_level, min(self.max_level, target_level))

        # 方向が変わるとき、いきなり逆方向へ最大出力しないように一度弱める。
        if self.current_direction != target_direction and self.current_level > 0:
            self.current_level = max(0, self.current_level - self.level_step)

            if self.current_level == 0:
                self.current_direction = target_direction
            else:
                self.play_constant_force(self.current_level, self.current_direction)
                return

        else:
            self.current_direction = target_direction

            # FFB力を目標値へ少しずつ近づける。
            if self.current_level < target_level:
                self.current_level = min(target_level, self.current_level + self.level_step)

            elif self.current_level > target_level:
                self.current_level = max(target_level, self.current_level - self.level_step)

        if self.current_level <= 0:
            self.stop_effect()
            return

        self.play_constant_force(self.current_level, self.current_direction)

        self.get_logger().info(
            f'target={self.target_handle_deg:.1f}deg, '
            f'current={self.current_handle_deg:.1f}deg, '
            f'error={error_deg:.1f}deg, '
            f'level={self.current_level}, '
            f'dir=0x{self.current_direction:04x}'
        )

    def play_constant_force(self, level, direction):
        """
        G923へ一定方向のFFB力を出す。
        levelが力の強さ、directionが力の方向。
        """
        # 前回とほぼ同じ力なら、エフェクトを作り直さない。
        # 作り直しすぎるとG923の挙動が不安定になりやすい。
        if (
            self.effect_id is not None
            and abs(level - self.last_level) < 300
            and direction == self.last_direction
        ):
            return

        self.stop_effect()

        effect = ff.Effect(
            ecodes.FF_CONSTANT,
            -1,
            direction,
            ff.Trigger(0, 0),
            ff.Replay(5000, 0),
            ff.EffectType(
                ff_constant_effect=ff.Constant(
                    level=level,
                    envelope=ff.Envelope(0, 0, 0, 0)
                )
            )
        )

        try:
            self.effect_id = self.dev.upload_effect(effect)
            self.dev.write(ecodes.EV_FF, self.effect_id, 1)

            self.last_level = level
            self.last_direction = direction

        except Exception as e:
            self.get_logger().error(f'Failed to play FFB: {e}')
            self.effect_id = None

    def stop_effect(self):
        """
        現在出しているFFBエフェクトを停止・削除する。
        """
        if self.effect_id is not None:
            try:
                self.dev.write(ecodes.EV_FF, self.effect_id, 0)
                self.dev.erase_effect(self.effect_id)
            except Exception:
                pass

            self.effect_id = None
            self.last_level = 0

    def quaternion_to_yaw(self, q):
        """
        OdometryのQuaternion姿勢からyaw角だけを取り出す。
        """
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)

        return math.atan2(siny_cosp, cosy_cosp)

    def normalize_angle(self, angle):
        """
        角度を -pi 〜 pi の範囲に収める。
        yaw差分を計算するときに、±180度付近で値が飛ぶのを防ぐ。
        """
        while angle > math.pi:
            angle -= 2.0 * math.pi

        while angle < -math.pi:
            angle += 2.0 * math.pi

        return angle

    def destroy_node(self):
        self.stop_effect()

        # 終了時はハンドルの通常の重さを戻す。
        self.set_autocenter(80)

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