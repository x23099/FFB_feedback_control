#!/usr/bin/env python3

import os
import glob
import time
import select
import threading
import math

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, Int32

from evdev import InputDevice, ecodes
from std_msgs.msg import Bool


class HandleNode(Node):
    def __init__(self):
        super().__init__('handle_node')

        # Kobuki手動操作用の速度指令
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_joy', 10)

        # FFB制御側で使うためのハンドル情報
        self.steering_deg_pub = self.create_publisher(Float32, '/handle/steering_angle_deg', 10)
        self.steering_norm_pub = self.create_publisher(Float32, '/handle/steering_norm', 10)

        # 人間が手動操作中かFFB側へ通知する。
        self.manual_active_pub = self.create_publisher(Bool, '/handle/manual_active', 10)
       
        # 現在、人間が手動介入中か。
        self.manual_active = False
        
        # 現在のギア情報.
        self.gear_pub = self.create_publisher(Int32, '/handle/gear', 10)

        # ===== 操縦パラメータ =====

        # Kobukiの最大速度
        self.max_linear = 0.6

        # Kobukiの最大旋回速度.小さいとハンドルを切っても曲がりにくい
        self.max_angular = 1.6

        # G923は左右それぞれ450度まで
        self.steering_limit_deg = 450.0

        # ハンドル中心付近の小さなブレを無視する範囲
        self.steering_deadzone_deg = 2.0
        
        # このハンドル角で基準となる旋回速度を出す
        self.reference_steering_deg = 112.5
        
        # ハンドル112.5度時に出す旋回角速度[rad/s].
        self.reference_angular = 0.8
        
        # 小さい舵角の感度を高くする指数
        # 1.0なら完全な比例、0.5〜0.8なら中心付近が敏感になる.
        self.steering_curve_exponent = 0.60

        # アクセルを少し踏んだら手動操作中とみなす閾値
        self.throttle_threshold = 0.03

        # ブレーキ判定
        self.brake_threshold_raw = 240
        
        # 小さな直進指令を0として扱う閾値.
        self.linear_command_deadzone = 0.01

        # 小さな旋回指令を0として扱う閾値.
        self.angular_command_deadzone = 0.03

        # 手動操作終了時にゼロ指令を送る回数.
        self.stop_publish_cycles = 3

        # 残りのゼロ指令送信回数.
        self.stop_publish_remaining = 0

        # ===== G923を開く =====

        self.g923 = self.find_g923_device()

        if self.g923 is None:
            self.get_logger().error('Logitech G923 not found.')
            return

        self.get_logger().info(f'Connected: {self.g923.name}')

        # ステアリング軸ABS_Xの範囲を取得する
        try:
            absinfo = self.g923.absinfo(ecodes.ABS_X)

            self.steering_center = (absinfo.min + absinfo.max) / 2.0
            self.steering_half_range = max((absinfo.max - absinfo.min) / 2.0, 1.0)

            self.get_logger().info(
                f'ABS_X min={absinfo.min}, max={absinfo.max}, '
                f'center={self.steering_center}, half={self.steering_half_range}'
            )

        except Exception as e:
            self.get_logger().warn(f'Failed to get ABS_X info: {e}')

            self.steering_center = 32768.0
            self.steering_half_range = 32768.0

        # ===== 入力状態 =====

        self.steering_raw = int(self.steering_center)
        self.steering_norm = 0.0
        self.steering_deg = 0.0

        self.throttle_norm = 0.0
        self.brake_active = False
        self.clutch_active = False

        # ギア状態.
        # 1〜5: 前進
        # -1 : リバース
        self.gear = 1
        self.linear_gain = 1.0

        # 入力スレッド管理
        self.running = True

        self.input_thread = threading.Thread(
            target=self.input_loop,
            daemon=True
        )
        self.input_thread.start()

        # 20Hzで現在状態をpublishし続ける
        self.publish_period = 0.05
        self.create_timer(self.publish_period, self.publish_loop)

        self.get_logger().info('handle.py started.')

    def find_g923_device(self):
        """
        G923のevent-joystickデバイスを探して開く.
        固定パスがあればそれを優先する.
        """
        stable_path = (
            '/dev/input/by-id/'
            'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
            'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
        )

        if os.path.exists(stable_path):
            try:
                return InputDevice(stable_path)
            except Exception as e:
                self.get_logger().warn(f'Failed to open stable path: {e}')

        patterns = [
            '/dev/input/by-id/*G923*event-joystick',
            '/dev/input/by-id/*G29*event-joystick',
            '/dev/input/by-id/*Logitech*Racing*event-joystick',
        ]

        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    return InputDevice(path)
                except Exception:
                    pass

        for path in glob.glob('/dev/input/event*'):
            try:
                dev = InputDevice(path)
                name = dev.name.lower()

                if 'g923' in name or ('logitech' in name and 'racing wheel' in name):
                    return dev

                dev.close()

            except Exception:
                pass

        return None

    def input_loop(self):
        """
        G923の入力イベントを読み続ける.
        ここではpublishせず、内部状態だけ更新する.
        実際のpublishはpublish_loopで20Hz周期で行う.
        """
        while self.running:
            try:
                r, _, _ = select.select([self.g923.fd], [], [], 0.01)

                if not r:
                    continue

                for event in self.g923.read():
                    if event.type == ecodes.EV_ABS:
                        self.handle_abs_event(event)

                    elif event.type == ecodes.EV_KEY and event.value == 1:
                        self.handle_key_event(event)

            except BlockingIOError:
                continue

            except Exception as e:
                self.get_logger().error(f'Input error: {e}')

    def calculate_angular_command(self):
        """
        ハンドル角度から汎用的な旋回角速度angular.zを計算する.

        ハンドル角を最終的な旋回角度には変換せず、
        ハンドルを切っている間の旋回速度としてTwistへ変換する.
        """
        steering_deg = self.steering_deg

        # 中心付近の小さな揺れを無視する.
        if abs(steering_deg) <= self.steering_deadzone_deg:
            return 0.0

        # デッドゾーンを除いた実効ハンドル角を求める.
        effective_deg = abs(steering_deg) - self.steering_deadzone_deg

        # 112.5度を基準として0以上の比率に変換する.
        steering_ratio = effective_deg / self.reference_steering_deg

        # 小さい舵角でも旋回しやすくする.
        curved_ratio = steering_ratio ** self.steering_curve_exponent

        # 基準角速度を掛けてangular.zを計算する.
        angular = curved_ratio * self.reference_angular

        # 最大旋回速度を超えないように制限する.
        angular = min(angular, self.max_angular)

        # ハンドルの左右方向を反映する.
        angular = math.copysign(angular, steering_deg)

        # ROSでは通常、右旋回がangular.zのマイナスになるため反転する.
        return -angular

    def handle_abs_event(self, event):
        """
        ステアリング、アクセル、ブレーキ、クラッチの入力処理.
        """
        
        # ハンコンの生値
        raw_val = event.value
        code = event.code

        # ステアリング.
        if code == ecodes.ABS_X:
            self.steering_raw = raw_val # 現在のハンコン位置の生値を保存

            # 生値を-1.0〜1.0に正規化
            norm = (raw_val - self.steering_center) / self.steering_half_range
            norm = max(-1.0, min(1.0, norm))

            # 正規化値×450
            deg = norm * self.steering_limit_deg

            if abs(deg) < self.steering_deadzone_deg:
                deg = 0.0
                norm = 0.0

            self.steering_norm = norm
            self.steering_deg = deg

        # アクセル.
        elif code == ecodes.ABS_Z:
            if raw_val < 250:
                self.throttle_norm = (250 - raw_val) / 250.0
            else:
                self.throttle_norm = 0.0

            self.throttle_norm = max(0.0, min(1.0, self.throttle_norm))

        # ブレーキ.
        elif code == ecodes.ABS_RZ:
            self.brake_active = raw_val < self.brake_threshold_raw

        # クラッチ.
        elif code == ecodes.ABS_Y:
            self.clutch_active = raw_val < 240

    def handle_key_event(self, event):
        """
        Hシフト入力の処理.
        パドルシフトは使わない.
        クラッチを踏んでいる間だけギア変更を受け付ける.
        """

        # クラッチを踏んでいないなら、Hシフトは無視する.
        if not self.clutch_active:
            return

        # Hパターンシフト.
        if event.code == 300:
            self.gear = 1
            self.linear_gain = 0.5

        elif event.code == 301:
            self.gear = 2
            self.linear_gain = 1.0

        elif event.code == 302:
            self.gear = 3
            self.linear_gain = 1.5

        elif event.code == 303:
            self.gear = 4
            self.linear_gain = 2.0

        elif event.code == 704:
            self.gear = 5
            self.linear_gain = 2.5

        elif event.code == 705:
            self.gear = 6
            self.linear_gain = 3.0
            
        elif event.code == 706:
            self.gear = -1
            self.linear_gain = -0.5

        else:
            return

        self.get_logger().info(
            f'H-shifter accepted: gear={self.gear}, linear_gain={self.linear_gain:.1f}'
        )

    def publish_loop(self):
        """
        現在の入力状態を20Hzでpublishし続ける.
        手動操作終了時はゼロ指令を数回送ってからpublishを停止する.
        """

        # ハンドル角度[deg]をpublish.
        deg_msg = Float32()
        deg_msg.data = float(self.steering_deg)
        self.steering_deg_pub.publish(deg_msg)

        # ハンドル正規化値[-1.0〜1.0]をpublish.
        norm_msg = Float32()
        norm_msg.data = float(self.steering_norm)
        self.steering_norm_pub.publish(norm_msg)

        # ギア情報をpublish.
        gear_msg = Int32()
        gear_msg.data = int(self.gear)
        self.gear_pub.publish(gear_msg)

        # アクセルかブレーキ操作中を手動操作として扱う.
        manual_active = (
            self.throttle_norm > self.throttle_threshold
            or self.brake_active
        )

        # FFB側へ手動操作状態を通知する.
        manual_msg = Bool()
        manual_msg.data = manual_active
        self.manual_active_pub.publish(manual_msg)

        if manual_active:
            # 手動操作終了後に送るゼロ指令回数を準備する.
            self.stop_publish_remaining = self.stop_publish_cycles

            twist = Twist()

            if self.brake_active:
                # ブレーキ中は直進と旋回を両方停止する.
                twist.linear.x = 0.0
                twist.angular.z = 0.0

            else:
                # アクセル量とギア倍率から直進速度を作る.
                twist.linear.x = (
                    self.throttle_norm
                    * self.max_linear
                    * self.linear_gain
                )

                # ハンドル角度から旋回角速度を作る.
                angular_command = self.calculate_angular_command()

                # 後退時は操舵方向を反転する.
                if self.linear_gain < 0:
                    twist.angular.z = -angular_command
                else:
                    twist.angular.z = angular_command

                # 小さな直進指令を0にする.
                if abs(twist.linear.x) < self.linear_command_deadzone:
                    twist.linear.x = 0.0

                # 小さな旋回指令を0にする.
                if abs(twist.angular.z) < self.angular_command_deadzone:
                    twist.angular.z = 0.0

            self.cmd_pub.publish(twist)
            return

        # 手動操作終了後にゼロ指令を数回だけ送る.
        if self.stop_publish_remaining > 0:
            self.cmd_pub.publish(Twist())
            self.stop_publish_remaining -= 1

    def destroy_node(self):
        self.running = False

        try:
            if self.g923 is not None:
                self.g923.close()
        except Exception:
            pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = HandleNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()