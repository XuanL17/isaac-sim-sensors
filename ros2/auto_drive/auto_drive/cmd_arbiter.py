#!/usr/bin/env python3
"""
Fuse camera lane-follow and GPS waypoint steering into a single Ackermann command.

Default blend: 70% camera steering + 30% GPS steering; speed from GPS command.
"""

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


class CmdArbiter(Node):
    def __init__(self):
        super().__init__('cmd_arbiter')

        self.declare_parameter('camera_cmd_topic', 'camera_cmd')
        self.declare_parameter('gps_cmd_topic', 'gps_cmd')
        self.declare_parameter('output_topic', 'ackermann_cmd')
        self.declare_parameter('camera_steer_weight', 0.7)
        self.declare_parameter('gps_steer_weight', 0.3)

        camera_topic = self.get_parameter('camera_cmd_topic').value
        gps_topic = self.get_parameter('gps_cmd_topic').value
        output_topic = self.get_parameter('output_topic').value
        self.camera_weight = float(self.get_parameter('camera_steer_weight').value)
        self.gps_weight = float(self.get_parameter('gps_steer_weight').value)

        total = self.camera_weight + self.gps_weight
        if total <= 0.0:
            self.camera_weight = 0.7
            self.gps_weight = 0.3
            total = 1.0
        self.camera_weight /= total
        self.gps_weight /= total

        self.camera_cmd = None
        self.gps_cmd = None

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        self.camera_sub = self.create_subscription(
            AckermannDriveStamped, camera_topic, self.camera_callback, qos)
        self.gps_sub = self.create_subscription(
            AckermannDriveStamped, gps_topic, self.gps_callback, qos)
        self.cmd_pub = self.create_publisher(
            AckermannDriveStamped, output_topic, qos)

        self.timer = self.create_timer(0.05, self.publish_fused)

        self.get_logger().info(
            f'Cmd arbiter: {camera_topic} ({self.camera_weight:.0%} steer) + '
            f'{gps_topic} ({self.gps_weight:.0%} steer) -> {output_topic} '
            f'(speed from GPS)')

    def camera_callback(self, msg: AckermannDriveStamped):
        self.camera_cmd = msg

    def gps_callback(self, msg: AckermannDriveStamped):
        self.gps_cmd = msg

    def publish_fused(self):
        if self.gps_cmd is None:
            return

        camera_steer = 0.0
        if self.camera_cmd is not None:
            camera_steer = self.camera_cmd.drive.steering_angle

        gps_steer = self.gps_cmd.drive.steering_angle
        fused_steer = (
            self.camera_weight * camera_steer + self.gps_weight * gps_steer
        )

        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = 'base_link'
        out.drive.steering_angle = fused_steer
        out.drive.speed = self.gps_cmd.drive.speed
        self.cmd_pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = CmdArbiter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
