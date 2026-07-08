#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32, String
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


class FailsafeWatchdog(Node):
    def __init__(self):
        super().__init__('failsafe_watchdog_node')

        self.declare_parameter('heartbeat_topic', '/remote_heartbeat')
        self.declare_parameter('safety_cmd_topic', '/cmd_vel_safety')
        self.declare_parameter('timeout_sec', 1.0)
        self.declare_parameter('recovery_sec', 2.0)
        self.declare_parameter('check_rate_hz', 20.0)
        self.declare_parameter('stop_publish_rate_hz', 20.0)
        self.declare_parameter('use_best_effort', True)

        self.heartbeat_topic = self.get_parameter('heartbeat_topic').value
        self.safety_cmd_topic = self.get_parameter('safety_cmd_topic').value
        self.timeout_sec = float(self.get_parameter('timeout_sec').value)
        self.recovery_sec = float(self.get_parameter('recovery_sec').value)
        self.check_rate_hz = float(self.get_parameter('check_rate_hz').value)
        self.stop_publish_rate_hz = float(self.get_parameter('stop_publish_rate_hz').value)
        self.use_best_effort = bool(self.get_parameter('use_best_effort').value)

        if self.timeout_sec <= 0.0:
            self.timeout_sec = 1.0
        if self.recovery_sec < 0.0:
            self.recovery_sec = 0.0
        if self.check_rate_hz <= 0.0:
            self.check_rate_hz = 20.0
        if self.stop_publish_rate_hz <= 0.0:
            self.stop_publish_rate_hz = 20.0

        reliability = (
            ReliabilityPolicy.BEST_EFFORT
            if self.use_best_effort
            else ReliabilityPolicy.RELIABLE
        )

        heartbeat_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=reliability,
        )

        self.sub = self.create_subscription(
            Time,
            self.heartbeat_topic,
            self.heartbeat_callback,
            heartbeat_qos,
        )

        self.cmd_pub = self.create_publisher(Twist, self.safety_cmd_topic, 10)
        self.active_pub = self.create_publisher(Bool, '/failsafe/active', 10)
        self.age_pub = self.create_publisher(Float32, '/failsafe/heartbeat_age', 10)
        self.reason_pub = self.create_publisher(String, '/failsafe/reason', 10)

        self.last_heartbeat_time = None
        self.failsafe_active = True
        self.recovery_start_time = None
        self.last_stop_publish_time = 0.0

        self.timer = self.create_timer(
            1.0 / self.check_rate_hz,
            self.check_failsafe,
        )

        self.get_logger().warn(
            f'Failsafe watchdog started. heartbeat={self.heartbeat_topic}, '
            f'safety_cmd={self.safety_cmd_topic}, timeout={self.timeout_sec:.2f}s, '
            f'recovery={self.recovery_sec:.2f}s'
        )

    def now_sec(self):
        return self.get_clock().now().nanoseconds / 1e9

    def heartbeat_callback(self, _msg):
        now = self.now_sec()
        self.last_heartbeat_time = now

        if self.failsafe_active:
            if self.recovery_start_time is None:
                self.recovery_start_time = now
                self.get_logger().info('Heartbeat received. Starting recovery phase...')
        else:
            self.recovery_start_time = None

    def check_failsafe(self):
        now = self.now_sec()

        if self.last_heartbeat_time is None:
            age = float('inf')
            timed_out = True
        else:
            age = now - self.last_heartbeat_time
            timed_out = age > self.timeout_sec

        if timed_out:
            self.recovery_start_time = None
            reason = 'timeout'
        else:
            reason = 'ok'

        if self.failsafe_active:
            if not timed_out:
                if self.recovery_start_time is not None:
                    recovery_age = now - self.recovery_start_time
                    if recovery_age >= self.recovery_sec:
                        self.failsafe_active = False
                        self.recovery_start_time = None
                        self.get_logger().info(
                            f'Failsafe released after {recovery_age:.2f}s of stable communication.'
                        )
                    else:
                        reason = 'recovering'
                else:
                    self.recovery_start_time = now
                    reason = 'recovering'
            else:
                reason = 'timeout'
        else:
            if timed_out:
                self.failsafe_active = True
                self.get_logger().error(
                    f'Heartbeat timeout. age={age:.3f}s. Emergency stop enabled.'
                )
                reason = 'timeout'

        active_msg = Bool()
        active_msg.data = self.failsafe_active
        self.active_pub.publish(active_msg)

        age_msg = Float32()
        age_msg.data = float(age) if age != float('inf') else -1.0
        self.age_pub.publish(age_msg)

        reason_msg = String()
        reason_msg.data = reason
        self.reason_pub.publish(reason_msg)

        if self.failsafe_active:
            self.publish_stop_if_needed(now)

    def publish_stop_if_needed(self, now):
        interval = 1.0 / self.stop_publish_rate_hz

        if now - self.last_stop_publish_time < interval:
            return

        self.last_stop_publish_time = now
        self.cmd_pub.publish(Twist())

    def destroy_node(self):
        # 終了時にも念のため停止指令を数回送る.
        try:
            for _ in range(5):
                self.cmd_pub.publish(Twist())
        except Exception:
            pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = FailsafeWatchdog()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
