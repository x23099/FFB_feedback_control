#!/usr/bin/env python3

import math
import subprocess

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from evdev import InputDevice, ecodes, ff


class FfbFollowNode(Node):
    def __init__(self):
        super().__init__('ffb_follow_node')

        # G923のFFB対応eventデバイス
        self.device_path = (
            '/dev/input/by-id/'
            'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
            'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
        )

        # G923を開く
        self.dev = InputDevice(self.device_path)
        self.get_logger().info(f'Opened FFB device: {self.dev.name}')

        # センタリング強度
        self.set_autocenter(40)

        # 450度を360度として扱う
        self.handle_limit_deg = 450.0

        # center値は約-32767〜32767の範囲で扱う
        self.spring_center_limit = 32767

        # Kobukiが360度旋回したら,ハンドルは450度動く対応
        self.kobuki_to_handle_ratio = 450.0 / 360.0
        self.invert_yaw_sign = True

        # 現在のKobuki yaw角[rad]
        self.current_yaw = 0.0

        # 自律旋回開始時のyaw角[rad]
        self.turn_start_yaw = None

        # 自律旋回中かどうか判断
        self.auto_turning = False

        # /cmd_vel_autoが最後に来た時刻
        self.last_auto_cmd_time = 0.0

        # angular.zがこの値以上なら旋回指令とみなす
        self.auto_angular_threshold = 0.05

        # この秒数以上,旋回指令が来なければ旋回終了とみなす
        self.auto_cmd_timeout = 0.3

        # 目標ハンドル角度[deg]
        self.target_handle_deg = 0.0

        # 目標Spring中心値
        self.target_center = 0

        # 実際に現在適用しているSpring中心値
        self.applied_center = 0

        # 1周期でcenterを変化させる最大量
        self.max_center_step = 400

        # center差がこの値未満なら更新しない
        self.center_update_threshold = 80

        # Springの強さ
        self.spring_coeff = 0x4900

        # Spring力の上限
        self.spring_saturation = 0x6000
        
        # Springの力をハンドル角度に対して変更するゲイン
        self.handle_scale_gain = 1.18
        
        # ハンドルを中心に戻すための補正値
        self.center_offset_deg = -3.0

        # 中心付近で力を出さない範囲
        self.spring_deadband = 0

        # 現在登録しているSpringエフェクトID
        self.spring_effect_id = None

        # 旋回終了後,ハンドルを中心へ戻してからSpringを止めるための状態
        self.returning_to_center = False

        # ROS購読
        # 自律走行の速度指令
        self.create_subscription(
            Twist,
            '/cmd_vel_auto',
            self.auto_cmd_callback,
            10
        )

        # Kobukiのodom
        self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # 20HzでSpring中心を更新する
        self.create_timer(0.05, self.spring_update_loop)
        # self.spring_update_period = 0.033
        # self.create_timer(self.spring_update_period, self.spring_update_loop)
        
    def set_autocenter(self, strength):
        """
        G923の標準センタリング力を設定する.
        strengthは0〜100.
        Spring制御中は0〜10くらいが扱いやすい.
        """
        try:
            subprocess.run(
                ['ffset', self.device_path, '-a', str(strength)],
                check=False
            )
            self.get_logger().info(f'Autocenter set to {strength}%')

        except Exception as e:
            self.get_logger().warn(f'Failed to set autocenter: {e}')

    def auto_cmd_callback(self, msg):
        """
        /cmd_vel_autoから自律旋回中かどうかを判定する.
        angular.zが一定以上なら,Kobukiが自律旋回しているとみなす.
        """
        angular = msg.angular.z

        if abs(angular) > self.auto_angular_threshold:
            now = self.get_clock().now().nanoseconds / 1e9
            self.last_auto_cmd_time = now

            # すでに旋回中なら,開始yawはそのまま
            if not self.auto_turning:
                self.auto_turning = True # 旋回中に切り替え
                self.returning_to_center = False # 中心への反力を止める
                self.turn_start_yaw = self.current_yaw # 旋回開始時のyawを記録

                self.target_handle_deg = 0.0
                self.target_center = 0
                self.applied_center = 0

                self.get_logger().info(
                    f'Auto turn started. start_yaw={math.degrees(self.turn_start_yaw):.1f}deg'
                )

    def odom_callback(self, msg):
        """
        /odomから現在yawを読み取る.
        自律旋回中なら,旋回開始時からのyaw差分を計算し,
        それに対応するハンドル目標角を作る.
        """
        self.current_yaw = self.quaternion_to_yaw(msg.pose.pose.orientation)

        # 旋回中でなければ何もしない(直進・停止中はハンドルを動かさない)
        if not self.auto_turning:
            return

        if self.turn_start_yaw is None:
            return

        # 旋回開始時からのyaw差分[rad]
        yaw_delta = self.normalize_angle(self.current_yaw - self.turn_start_yaw)

        # radからdegへ変換
        yaw_delta_deg = math.degrees(yaw_delta)

        # 右旋回がマイナスyawになる場合,ハンドル右をプラスにするため符号を反転する
        if self.invert_yaw_sign:
            yaw_delta_deg = -yaw_delta_deg

        # Kobukiの旋回角からハンドル目標角を計算する
        target_handle_deg = yaw_delta_deg * self.kobuki_to_handle_ratio * self.handle_scale_gain
       
        # ハンドルの物理限界での制限する(例：500度とかは回らないように)
        target_handle_deg = max(
            -self.handle_limit_deg,
            min(self.handle_limit_deg, target_handle_deg)
        )

        self.target_handle_deg = target_handle_deg

        # ハンドル目標角度をSpringのcenter値へ変換する
        self.target_center = self.deg_to_spring_center(self.target_handle_deg)

    def spring_update_loop(self):
        """
        Springの中心位置を少しずつ目標centerへ近づける.
        centerを一気に変えるとハンドルが急に動くので,max_center_stepで制限する.
        """
        now = self.get_clock().now().nanoseconds / 1e9

        # 自律旋回指令が止まったら,旋回終了とみなし,すぐSpringを止めるのではなく,target_centerを0にして中心へ戻す
        if self.auto_turning and now - self.last_auto_cmd_time > self.auto_cmd_timeout:
            self.auto_turning = False
            self.returning_to_center = True
            self.turn_start_yaw = None

            self.target_handle_deg = 0.0
            self.target_center = 0

            self.get_logger().info('Auto turn ended. Returning spring center to 0.')

        # 旋回中でも中心復帰中の両方がFalseならSpringを止める
        if not self.auto_turning and not self.returning_to_center:
            self.stop_spring()
            return

        # 目標center(角度)と現在適用しているcenterの差を計算
        diff = self.target_center - self.applied_center

        # max_center_step以下なら目標centerに直接近づける
        if abs(diff) <= self.max_center_step:
            self.applied_center = self.target_center
        else:
            if diff > 0:
                self.applied_center += self.max_center_step
            else:
                self.applied_center -= self.max_center_step

        # centerが十分0に戻ったらSpringを止める
        if self.returning_to_center and abs(self.applied_center) < self.center_update_threshold:
            self.applied_center = 0
            self.target_center = 0
            self.returning_to_center = False
            self.stop_spring()

            self.get_logger().info('Spring returned to center and stopped.')
            return

        # center差が小さいなら,エフェクト更新をしない
        if (
            self.spring_effect_id is not None
            and abs(diff) < self.center_update_threshold
        ):
            return

        # 新しいcenterでSpringを作り直す
        self.play_spring(self.applied_center)

        self.get_logger().info(
            f'target_handle={self.target_handle_deg:.1f}deg, '
            f'target_center={self.target_center}, '
            f'applied_center={self.applied_center}'
        )

    def deg_to_spring_center(self, deg):
        """
        ハンドル角度[deg]をFF_SPRINGのcenter値へ変換する.
        center_offset_degで実機のセンターずれを補正する.
        """
        # センターズレを補正
        corrected_deg = deg + self.center_offset_deg

        # (補正後の角度 / 450) * 32767 でcenter値を計算
        center = int(corrected_deg / self.handle_limit_deg * self.spring_center_limit)

        center = max(
            -self.spring_center_limit,
            min(self.spring_center_limit, center)
        )

        return center
    
    def make_spring_effect(self, center, effect_id=-1):
        """
        指定したcenterを中心とするSpringエフェクトを作る.
        centerがプラスなら右側,マイナスなら左側を中心にする.
        """
        # X方向とY方向の2軸分のConditionを作る
        condition = ff.Condition(
            self.spring_saturation, # 右方向の力の上限
            self.spring_saturation, # 左方向の力の上限
            self.spring_coeff,      # 右方向のspring係数
            self.spring_coeff,      # 左方向のspring係数
            self.spring_deadband,   # 中心付近で力を出さない範囲
            center                  # springの中心位置
        )

        effect = ff.Effect(
            ecodes.FF_SPRING,    # エフェクトの種類
            effect_id,                  # エフェクトID(-1で新規作成)
            0,                   # エフェクトの強さ
            ff.Trigger(0, 0),    # ボタン押したときのトリガー条件(今回は使わないので0)
            ff.Replay(30000, 0), # エフェクトの再生時間と再生回数
            ff.EffectType(
                ff_condition_effect=(condition, condition)
            )
        )

        return effect

    def play_spring(self, center):
        """
        Springを停止せず、再生中のエフェクトのcenterだけを更新する。
        """
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

                self.dev.upload_effect(effect)

        except Exception as e:
            self.get_logger().error(f'Failed to update spring: {e}')
            self.spring_effect_id = None
            
    def stop_spring(self):
        """
        現在再生中のSpringエフェクトを停止・削除する.
        """
        if self.spring_effect_id is not None:
            try:
                self.dev.write(ecodes.EV_FF, self.spring_effect_id, 0)
                self.dev.erase_effect(self.spring_effect_id)
            except Exception:
                pass

            self.spring_effect_id = None

    def quaternion_to_yaw(self, q):
        """
        OdometryのQuaternion姿勢からyaw角だけを取り出す.
        """
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)

        return math.atan2(siny_cosp, cosy_cosp)

    def normalize_angle(self, angle):
        """
        角度を -pi 〜 pi の範囲に収める.
        yaw差分を計算するとき,±180度付近で値が飛ぶのを防ぐ.
        """
        while angle > math.pi:
            angle -= 2.0 * math.pi

        while angle < -math.pi:
            angle += 2.0 * math.pi

        return angle

    def destroy_node(self):
        """
        ノード終了時の処理.
        Springを止めて,通常のセンタリング力を戻す.
        """
        self.stop_spring()
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