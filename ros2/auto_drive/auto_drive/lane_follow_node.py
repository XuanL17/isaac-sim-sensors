#!/usr/bin/env python3
"""
Simple lane follower for Isaac Sim OAK-D RGB camera.

Publishes steering to /camera_cmd for fusion by cmd_arbiter (not directly to /ackermann_cmd).
"""

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

import cv2
import numpy as np


class LaneFollowNode(Node):
    def __init__(self):
        super().__init__('lane_follow_node')

        self.declare_parameter('image_topic', 'oak/rgb/image_raw')
        self.declare_parameter('cmd_topic', 'camera_cmd')
        self.declare_parameter('speed', 1.0)
        self.declare_parameter('kp', 0.003)
        self.declare_parameter('max_steer', 0.35)
        self.declare_parameter('show_debug', False)

        self.image_topic = self.get_parameter('image_topic').value
        self.cmd_topic = self.get_parameter('cmd_topic').value
        self.speed = float(self.get_parameter('speed').value)
        self.kp = float(self.get_parameter('kp').value)
        self.max_steer = float(self.get_parameter('max_steer').value)
        self.show_debug = bool(self.get_parameter('show_debug').value)

        self.bridge = CvBridge()

        self.image_sub = self.create_subscription(
            Image, self.image_topic, self.image_callback, 10)
        self.cmd_pub = self.create_publisher(
            AckermannDriveStamped, self.cmd_topic, 10)

        self.get_logger().info('Lane follow node started.')
        self.get_logger().info(f'Subscribing to: {self.image_topic}')
        self.get_logger().info(f'Publishing to: {self.cmd_topic}')

    def image_callback(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'cv_bridge error: {e}')
            return

        height, width, _ = frame.shape
        roi = frame[int(height * 0.55):height, :]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 60, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)

        lower_yellow = np.array([15, 80, 80])
        upper_yellow = np.array([40, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

        mask = cv2.bitwise_or(white_mask, yellow_mask)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)

        moments = cv2.moments(mask)
        image_center = width // 2
        lane_center = image_center

        if moments['m00'] > 0:
            lane_center = int(moments['m10'] / moments['m00'])

        error = image_center - lane_center
        steering_angle = self.kp * error
        steering_angle = max(-self.max_steer, min(self.max_steer, steering_angle))

        cmd = AckermannDriveStamped()
        cmd.header.stamp = msg.header.stamp
        cmd.header.frame_id = 'base_link'
        cmd.drive.speed = self.speed
        cmd.drive.steering_angle = steering_angle
        self.cmd_pub.publish(cmd)

        if self.show_debug:
            debug = roi.copy()
            cv2.circle(debug, (lane_center, debug.shape[0] // 2), 8, (0, 0, 255), -1)
            cv2.line(debug, (image_center, 0), (image_center, debug.shape[0]), (255, 0, 0), 2)
            try:
                cv2.imshow('Lane Detection ROI', debug)
                cv2.imshow('Lane Mask', mask)
                cv2.waitKey(1)
            except cv2.error as e:
                self.get_logger().warn(f'Debug display unavailable: {e}')

        self.get_logger().debug(
            f'lane_center={lane_center}, error={error}, steering={steering_angle:.3f}')


def main(args=None):
    rclpy.init(args=args)
    node = LaneFollowNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if node.show_debug:
            cv2.destroyAllWindows()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
