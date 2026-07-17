#!/usr/bin/env python3

import copy

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class CmdVelMirrorNode(Node):
    def __init__(self):
        super().__init__('cmd_vel_mirror_node')

        # 入力トピック.
        self.declare_parameter('source_topic', '/cmd_vel_joy')

        # AIFormula側へ送る出力トピック.
        self.declare_parameter(
            'target_topic',
            '/aiformula_control/handle_controller/cmd_vel'
        )

        # publish周期.
        self.declare_parameter('publish_rate_hz', 20.0)

        # 入力がこの秒数以上来なければゼロ指令にする.
        self.declare_parameter('source_timeout_sec', 0.3)

        # AIFormula側だけ速度倍率を変えたい場合に使う.
        self.declare_parameter('linear_scale', 3.0)
        self.declare_parameter('angular_scale', 3.0)

        # stale時にゼロ指令を出し続ける.
        self.declare_parameter('publish_zero_when_stale', True)

        source_topic = (
            self.get_parameter('source_topic')
            .get_parameter_value()
            .string_value
        )
        target_topic = (
            self.get_parameter('target_topic')
            .get_parameter_value()
            .string_value
        )

        self.publish_rate_hz = (
            self.get_parameter('publish_rate_hz')
            .get_parameter_value()
            .double_value
        )
        self.source_timeout_sec = (
            self.get_parameter('source_timeout_sec')
            .get_parameter_value()
            .double_value
        )
        self.linear_scale = (
            self.get_parameter('linear_scale')
            .get_parameter_value()
            .double_value
        )
        self.angular_scale = (
            self.get_parameter('angular_scale')
            .get_parameter_value()
            .double_value
        )
        self.publish_zero_when_stale = (
            self.get_parameter('publish_zero_when_stale')
            .get_parameter_value()
            .bool_value
        )

        self.last_msg = Twist()
        self.last_msg_time = None

        self.active_pub = self.create_publisher(
            Bool,
            '/cmd_vel_mirror/active',
            10
        )

        self.target_pub = self.create_publisher(
            Twist,
            target_topic,
            10
        )

        self.source_sub = self.create_subscription(
            Twist,
            source_topic,
            self.cmd_vel_callback,
            10
        )

        timer_period = 1.0 / max(self.publish_rate_hz, 1.0)
        self.create_timer(timer_period, self.publish_loop)

        self.get_logger().info(
            f'cmd_vel_mirror started. '
            f'{source_topic} -> {target_topic}, '
            f'linear_scale={self.linear_scale}, '
            f'angular_scale={self.angular_scale}'
        )

    def cmd_vel_callback(self, msg):
        """
        最新のcmd_velを保存する.
        """
        self.last_msg = copy.deepcopy(msg)
        self.last_msg_time = self.get_clock().now()

    def is_source_alive(self):
        """
        source_topicが生きているか判定する.
        """
        if self.last_msg_time is None:
            return False

        now = self.get_clock().now()
        age = (now - self.last_msg_time).nanoseconds / 1e9

        return age <= self.source_timeout_sec

    def make_scaled_twist(self, msg):
        """
        AIFormula側へ送るTwistを作る.
        """
        out = Twist()

        out.linear.x = msg.linear.x * self.linear_scale
        out.linear.y = msg.linear.y * self.linear_scale
        out.linear.z = msg.linear.z * self.linear_scale

        out.angular.x = msg.angular.x * self.angular_scale
        out.angular.y = msg.angular.y * self.angular_scale
        out.angular.z = msg.angular.z * self.angular_scale

        return out

    def publish_loop(self):
        """
        AIFormula側へ周期的にcmd_velを送る.
        """
        source_alive = self.is_source_alive()

        active_msg = Bool()
        active_msg.data = source_alive
        self.active_pub.publish(active_msg)

        if source_alive:
            out = self.make_scaled_twist(self.last_msg)
            self.target_pub.publish(out)
            return

        if self.publish_zero_when_stale:
            self.target_pub.publish(Twist())


def main(args=None):
    rclpy.init(args=args)

    node = CmdVelMirrorNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
