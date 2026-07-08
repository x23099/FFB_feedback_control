#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from builtin_interfaces.msg import Time


class HeartbeatSender(Node):
    def __init__(self):
        super().__init__('heartbeat_sender_node')

        self.declare_parameter('heartbeat_topic', '/remote_heartbeat')
        self.declare_parameter('publish_rate_hz', 20.0)

        self.heartbeat_topic = self.get_parameter('heartbeat_topic').value
        self.publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)

        if self.publish_rate_hz <= 0.0:
            self.publish_rate_hz = 20.0

        self.pub = self.create_publisher(Time, self.heartbeat_topic, 10)

        self.timer = self.create_timer(
            1.0 / self.publish_rate_hz,
            self.publish_heartbeat
        )

        self.get_logger().info(
            f'Heartbeat sender started. topic={self.heartbeat_topic}, '
            f'rate={self.publish_rate_hz:.1f}Hz'
        )

    def publish_heartbeat(self):
        msg = self.get_clock().now().to_msg()
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = HeartbeatSender()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
