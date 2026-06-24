import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math
from enum import Enum


class State(Enum):
    # 状態をわかりやすく名前で管理する
    WAITING = 0   # odomを待っている状態
    DRIVING = 1   # 直進中
    TURNING = 2   # 旋回中
    DONE = 3      # 完了


class SquareNode(Node):
    def __init__(self):
        super().__init__('square_node')

        """
        Publisher / Subscriber
        """
        # 自動走行用の速度指令を publish
        # twist_mux を使う場合は cmd_vel_auto に出す
        self.pub = self.create_publisher(Twist, 'cmd_vel_auto', 10)

        # odom から現在位置と向きを取得
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)

        """
        走行パラメータ
        """
        self.side_length = 0.5          # 正方形の1辺の長さ [m]
        self.linear_speed = 0.15        # 直進速度 [m/s]
        self.angular_speed = -0.7       # 旋回速度 [rad/s] 右回転なのでマイナス
        self.dist_thresh = 0.02         # 直進完了の許容誤差 [m]
        self.turn_angle = math.radians(90.0)  # 旋回角度 90度をradに変換
        self.turn_thresh = math.radians(5.0)  # 旋回完了の許容誤差 3度
        self.total_sides = 4            # 正方形なので4辺

        """
        odomから得る現在値
        """
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

        """
        各動作開始時の基準値
        """
        self.ref_x = 0.0
        self.ref_y = 0.0
        self.ref_yaw = 0.0

        """
        状態管理
        """
        self.state = State.WAITING
        self.sides_done = 0

        # 走行完了後にノードを終了するためのフラグ
        self.finished = False
        
        # 20Hzで制御ループを回す
        self.timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info('起動しました。odom待機中...')

    """
    odomコールバック
    """
    def odom_callback(self, msg):
        # 現在位置を取得
        pos = msg.pose.pose.position
        self.x = pos.x
        self.y = pos.y

        # quaternion から yaw 角を計算
        self.yaw = self._quat_to_yaw(msg.pose.pose.orientation)

        # 初めて odom を受け取ったら走行開始
        if self.state == State.WAITING:
            self._set_ref()
            self.state = State.DRIVING
            self.get_logger().info('odom受信。走行開始!')

    """
    メイン制御ループ
    """
    def control_loop(self):
        if self.state == State.WAITING:
            # odomをまだ受け取っていない場合は何もしない
            return

        if self.state == State.DONE:
            # 完了後は停止指令を出し続ける
            self._publish(0.0, 0.0)
            return

        if self.state == State.DRIVING:
            self._drive()

        elif self.state == State.TURNING:
            self._turn()

    """
    直進処理
    """
    def _drive(self):
        # 直進開始地点からどれだけ進んだかを計算
        dist = self._distance()

        # 目標距離にまだ届いていないなら直進
        if dist < self.side_length - self.dist_thresh:
            self._publish(linear=self.linear_speed, angular=0.0)

        else:
            # 1辺分進んだので一旦停止
            self.get_logger().info(
                f'辺{self.sides_done + 1} 直進完了 dist={dist:.3f}m'
            )

            self._publish(0.0, 0.0)

            # 旋回開始時の位置・角度を記録
            self._set_ref()

            # 状態を旋回へ変更
            self.state = State.TURNING

    """
    旋回処理
    """
    def _turn(self):
        # 旋回開始時のyawから、現在どれだけ向きが変わったかを計算
        turned = abs(self._normalize_angle(self.yaw - self.ref_yaw))

        # 目標角度にまだ届いていないなら回転
        if turned < self.turn_angle - self.turn_thresh:
            self._publish(linear=0.0, angular=self.angular_speed)

        else:
            # 90度近く回ったので旋回完了
            self.get_logger().info(
                f'辺{self.sides_done + 1} 旋回完了 angle={math.degrees(turned):.1f}度'
            )

            self._publish(0.0, 0.0)

            # 完了した辺の数を増やす
            self.sides_done += 1

            # 4辺終わったら終了
            if self.sides_done >= self.total_sides:
                self.get_logger().info('完走')
                
                self._publish(0.0, 0.0)
                
                self.state = State.DONE
                self.finished = True

            else:
                # 次の直進のために基準位置を更新
                self._set_ref()
                self.state = State.DRIVING

    """
    基準値を現在値に更新
    """
    def _set_ref(self):
        self.ref_x = self.x
        self.ref_y = self.y
        self.ref_yaw = self.yaw

    """
    直進開始地点からの距離を計算
    """
    def _distance(self):
        return math.hypot(self.x - self.ref_x, self.y - self.ref_y)

    """
    速度指令をpublish
    """
    def _publish(self, linear=0.0, angular=0.0):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.pub.publish(msg)

    """
    quaternion から yaw を計算
    """
    @staticmethod
    def _quat_to_yaw(q):
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny, cosy)

    """
    角度を -pi から pi の範囲に正規化
    """
    @staticmethod
    def _normalize_angle(angle):
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle


def main(args=None):
    rclpy.init(args=args)
    node = SquareNode()

    try:
        # 走行完了まではROSのコールバックを処理する
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)

    except KeyboardInterrupt:
        node.get_logger().info('Ctrl+Cで終了します。')

    finally:
        # 終了時に停止指令を送る
        node._publish(0.0, 0.0)

        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()