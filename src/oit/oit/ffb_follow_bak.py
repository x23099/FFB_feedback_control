#!/usr/bin/env python3

import math
import subprocess

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool

from evdev import InputDevice, ecodes, ff


class FfbFollowNode(Node):
    def __init__(self):
        super().__init__('ffb_follow_node')

        # G923デバイス設定
        self.device_path = (
            '/dev/input/by-id/'
            'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
            'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
        )

        # G923を開く
        self.dev = InputDevice(self.device_path)
        self.get_logger().info(f'Opened FFB device: {self.dev.name}')

        '''
        # Autocenter設定
        '''
        # 動作状態ごとのAutocenter強度
        self.auto_autocenter = 0
        self.manual_autocenter = 60
        self.idle_autocenter = 15

        # 現在設定中の値.重複したコマンド送信を防ぐ
        self.current_autocenter = None

        # 起動時は待機用の強さにする
        self.apply_autocenter(self.idle_autocenter)
        
        '''
        角度変換設定
        '''
        # 450度を360度として扱う
        self.handle_limit_deg = 450.0

        # center値は約-32767〜32767の範囲で扱う
        self.spring_center_limit = 32767

        # Kobukiが360度旋回したら,ハンドルは450度動く対応
        self.kobuki_to_handle_ratio = 450.0 / 360.0

        # 右旋回時の符号を合わせる
        self.invert_yaw_sign = True

        # ハンドルを中心に戻すための補正値
        # 自律旋回中だけ適用する
        self.center_offset_deg = -3.0

        '''
        自律旋回判定設定
        '''
        # angular.zがこの値以上なら旋回指令とみなす
        self.auto_angular_threshold = 0.05

        # この秒数以上,旋回指令が来なければ旋回終了とみなす
        self.auto_cmd_timeout = 0.3

        '''
        Spring強度設定
        '''
        # 自律走行用のSpring設定
        self.auto_spring_coeff = 0x4900
        self.auto_spring_saturation = 0x6000

        # 手動操作時の基本反力
        self.manual_spring_coeff = 0x4900
        self.manual_spring_saturation = 0x6000

        # 自律直進中の基本的なハンドルの重さ
        self.idle_spring_coeff = 0x3000
        self.idle_spring_saturation = 0x4800

        # 中心付近で力を出さない範囲
        self.spring_deadband = 0

        '''
        Spring更新設定
        '''
        # 1周期でcenterを変化させる最大量
        self.max_center_step = 400

        # 強さを急変させないための更新幅
        self.coeff_step = 0x0200
        self.saturation_step = 0x0200

        # 小さな変化ではSpringを更新しない
        self.center_send_threshold = 20
        self.coeff_send_threshold = 0x0080
        self.saturation_send_threshold = 0x0080

        # 一定時間ごとにSpringを再送する
        self.effect_refresh_sec = 1.0

        # 20HzでSpring中心を更新する
        self.spring_update_period = 0.05

        # Springエフェクトの再生時間
        self.spring_replay_ms = 30000

        '''
        走行状態
        '''
        # 現在のKobuki yaw角[rad]
        self.current_yaw = 0.0

        # /odomを受信したか
        self.odom_received = False

        # 自律旋回開始時のyaw角[rad]
        self.turn_start_yaw = None

        # 自律旋回中かどうか判断
        self.auto_turning = False

        # 手動操作中かどうか
        self.manual_active = False

        # /cmd_vel_autoが最後に来た時刻
        self.last_auto_cmd_time = 0.0

        # 目標ハンドル角度[deg]
        self.target_handle_deg = 0.0

        # 自律走行から計算したSpring中心
        self.auto_target_center = 0

        '''
        適用中のSpring状態
        '''
        # 実際に現在適用しているSpring中心値
        self.applied_center = 0

        # 現在適用中のSpringパラメータ
        self.applied_coeff = self.idle_spring_coeff
        self.applied_saturation = self.idle_spring_saturation

        # 現在登録しているSpringエフェクトID
        self.spring_effect_id = None

        # 最後に送った値
        self.last_sent_center = None
        self.last_sent_coeff = None
        self.last_sent_saturation = None
        self.last_effect_update_time = 0.0

        '''
        ROS通信
        '''
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

        # 手動介入状態
        self.create_subscription(
            Bool,
            '/handle/manual_active',
            self.manual_active_callback,
            10
        )

        # Spring中心を更新する
        self.create_timer(
            self.spring_update_period,
            self.spring_update_loop
        )

        self.get_logger().info('FFB follow node started.')

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
        # 手動介入中は自律走行の旋回をFFBへ反映しない
        if self.manual_active:
            return

        # odom受信前は旋回を開始しない
        if not self.odom_received:
            return

        angular = msg.angular.z

        if abs(angular) <= self.auto_angular_threshold:
            return

        now = self.get_clock().now().nanoseconds / 1e9
        self.last_auto_cmd_time = now

        # すでに旋回中なら,開始yawはそのまま
        if not self.auto_turning:
            self.auto_turning = True

            # 自律追従中はSpring中心の移動を優先する
            self.apply_autocenter(self.auto_autocenter)

            self.turn_start_yaw = self.current_yaw
            self.target_handle_deg = 0.0
            self.auto_target_center = 0

            self.get_logger().info(
                f'Auto turn started. '
                f'start_yaw={math.degrees(self.turn_start_yaw):.1f}deg'
            )

    def odom_callback(self, msg):
        # /odomからKobukiのyaw角を取得する.
        self.current_yaw = self.quaternion_to_yaw(
            msg.pose.pose.orientation
        )
        self.odom_received = True

        # 人間が操作中は自律走行の目標Spring中心を更新しない
        if self.manual_active:
            return

        if not self.auto_turning:
            return

        if self.turn_start_yaw is None:
            return

        yaw_delta = self.normalize_angle(
            self.current_yaw - self.turn_start_yaw
        )

        yaw_delta_deg = math.degrees(yaw_delta)

        if self.invert_yaw_sign:
            yaw_delta_deg = -yaw_delta_deg

        # Kobukiの旋回角をハンドル角へ変換する
        target_handle_deg = (
            yaw_delta_deg
            * self.kobuki_to_handle_ratio
        )

        target_handle_deg = max(
            -self.handle_limit_deg,
            min(self.handle_limit_deg, target_handle_deg)
        )

        self.target_handle_deg = target_handle_deg

        # 自律走行用の中心値として保存する
        self.auto_target_center = self.deg_to_spring_center(
            target_handle_deg
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
        # 自律旋回状態を初期化する.
        
        self.auto_turning = False
        self.turn_start_yaw = None
        self.target_handle_deg = 0.0
        self.auto_target_center = 0

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
        # ノード終了時の処理.
        # Springを止めて,通常のセンタリング力を戻す.
        
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