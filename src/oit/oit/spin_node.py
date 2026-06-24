#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist


class SpinTestNode(Node):
    def __init__(self):
        super().__init__('spin_test_node')

        # 出力先トピック.
        self.declare_parameter('cmd_vel_topic', '/cmd_vel_auto')

        # 前進速度.
        self.declare_parameter('linear_x', 0.0)

        # 旋回速度.
        self.declare_parameter('angular_z', -0.7)

        # publish周期.
        self.declare_parameter('publish_hz', 20.0)

        self.cmd_vel_topic = (
            self.get_parameter('cmd_vel_topic')
            .get_parameter_value()
            .string_value
        )

        self.linear_x = (
            self.get_parameter('linear_x')
            .get_parameter_value()
            .double_value
        )

        self.angular_z = (
            self.get_parameter('angular_z')
            .get_parameter_value()
            .double_value
        )

        self.publish_hz = (
            self.get_parameter('publish_hz')
            .get_parameter_value()
            .double_value
        )

        self.cmd_pub = self.create_publisher(
            Twist,
            self.cmd_vel_topic,
            10
        )

        self.timer = self.create_timer(
            1.0 / self.publish_hz,
            self.publish_loop
        )

        self.get_logger().info(
            f'Spin test started. '
            f'topic={self.cmd_vel_topic}, '
            f'linear_x={self.linear_x:.3f}, '
            f'angular_z={self.angular_z:.3f}'
        )

    def publish_loop(self):
        """
        その場回転指令をpublishする.
        """
        twist = Twist()
        twist.linear.x = self.linear_x
        twist.angular.z = self.angular_z

        self.cmd_pub.publish(twist)

    def publish_stop(self):
        """
        停止指令をpublishする.
        """
        self.cmd_pub.publish(Twist())


def main(args=None):
    rclpy.init(args=args)

    node = SpinTestNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.get_logger().info('Stopping robot.')

        # 終了時にゼロ指令を数回送る.
        for _ in range(10):
            node.publish_stop()
            rclpy.spin_once(node, timeout_sec=0.02)

        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()