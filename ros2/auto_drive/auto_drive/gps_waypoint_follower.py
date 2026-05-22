#!/usr/bin/env python3
"""
GPS waypoint follower for AV4EV Isaac Sim.

Subscribes to NavSatFix (default /atlas/fix from gps_bridge.py) and optional
odometry for heading. Publishes AckermannDriveStamped on /gps_cmd.
"""

import json
import math
import os

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from ament_index_python.packages import get_package_share_directory
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import NavSatFix

from auto_drive.geo_utils import bearing_deg, haversine_m, normalize_angle_deg


def yaw_from_odom(msg: Odometry) -> float:
    """Extract yaw (rad) from odometry quaternion; 0 = +X in Isaac ENU-style frames."""
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class GPSWaypointFollower(Node):
    def __init__(self):
        super().__init__('gps_waypoint_follower')

        self.declare_parameter('fix_topic', 'atlas/fix')
        self.declare_parameter('odom_topic', 'atlas/odometry')
        self.declare_parameter('cmd_topic', 'gps_cmd')
        self.declare_parameter('waypoints_file', '')
        self.declare_parameter('waypoint_radius_m', 5.0)
        self.declare_parameter('default_speed_mps', 2.0)
        self.declare_parameter('max_steer_rad', 0.35)
        self.declare_parameter('heading_kp', 0.02)

        fix_topic = self.get_parameter('fix_topic').value
        odom_topic = self.get_parameter('odom_topic').value
        cmd_topic = self.get_parameter('cmd_topic').value
        waypoints_file = self.get_parameter('waypoints_file').value

        self.waypoint_radius_m = float(self.get_parameter('waypoint_radius_m').value)
        self.default_speed_mps = float(self.get_parameter('default_speed_mps').value)
        self.max_steer_rad = float(self.get_parameter('max_steer_rad').value)
        self.heading_kp = float(self.get_parameter('heading_kp').value)

        self.waypoints = self._load_waypoints(waypoints_file)
        self.waypoint_index = 0

        self.current_lat = None
        self.current_lon = None
        self.current_yaw_rad = 0.0
        self.have_fix = False
        self.have_odom = False

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        self.fix_sub = self.create_subscription(
            NavSatFix, fix_topic, self.fix_callback, qos)
        self.odom_sub = self.create_subscription(
            Odometry, odom_topic, self.odom_callback, qos)
        self.cmd_pub = self.create_publisher(
            AckermannDriveStamped, cmd_topic, qos)

        self.timer = self.create_timer(0.1, self.control_loop)

        self.get_logger().info(
            f'GPS waypoint follower: {fix_topic} + {odom_topic} -> {cmd_topic} '
            f'({len(self.waypoints)} waypoints, radius={self.waypoint_radius_m}m)')

    def _load_waypoints(self, waypoints_file: str):
        if not waypoints_file:
            try:
                share = get_package_share_directory('auto_drive')
                waypoints_file = os.path.join(
                    share, 'waypoints', 'track_waypoints.json')
            except Exception:
                repo_root = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
                waypoints_file = os.path.join(
                    repo_root, 'ros2', 'auto_drive', 'waypoints', 'track_waypoints.json')

        with open(waypoints_file, encoding='utf-8') as f:
            data = json.load(f)

        self.waypoint_radius_m = float(
            data.get('waypoint_radius_m', self.waypoint_radius_m))
        self.default_speed_mps = float(
            data.get('default_speed_mps', self.default_speed_mps))
        self.max_steer_rad = float(
            data.get('max_steer_rad', self.max_steer_rad))

        wps = data.get('waypoints', [])
        loaded = [(float(w['lat']), float(w['lon'])) for w in wps]
        if not loaded:
            raise ValueError(f'No waypoints in {waypoints_file}')
        self.get_logger().info(f'Loaded waypoints from {waypoints_file}')
        if data.get('description'):
            self.get_logger().info(data['description'])
        return loaded

    def fix_callback(self, msg: NavSatFix):
        if math.isnan(msg.latitude) or math.isnan(msg.longitude):
            return
        self.current_lat = msg.latitude
        self.current_lon = msg.longitude
        self.have_fix = True

    def odom_callback(self, msg: Odometry):
        self.current_yaw_rad = yaw_from_odom(msg)
        self.have_odom = True

    def _advance_waypoint_if_needed(self):
        if not self.have_fix or self.waypoint_index >= len(self.waypoints):
            return
        wp_lat, wp_lon = self.waypoints[self.waypoint_index]
        dist = haversine_m(
            self.current_lat, self.current_lon, wp_lat, wp_lon)
        if dist <= self.waypoint_radius_m:
            self.get_logger().info(
                f'Reached waypoint {self.waypoint_index} '
                f'({wp_lat:.6f}, {wp_lon:.6f}), dist={dist:.2f}m')
            self.waypoint_index += 1
            if self.waypoint_index >= len(self.waypoints):
                self.get_logger().info('All waypoints completed — holding last target.')

    def control_loop(self):
        if not self.have_fix:
            return

        self._advance_waypoint_if_needed()

        if self.waypoint_index >= len(self.waypoints):
            wp_lat, wp_lon = self.waypoints[-1]
        else:
            wp_lat, wp_lon = self.waypoints[self.waypoint_index]

        target_bearing_deg = bearing_deg(
            self.current_lat, self.current_lon, wp_lat, wp_lon)

        # Odometry yaw is ENU-style (+X east); convert to compass heading (0=north).
        if self.have_odom:
            current_heading_deg = (90.0 - math.degrees(self.current_yaw_rad)) % 360.0
        else:
            current_heading_deg = target_bearing_deg

        heading_error_deg = normalize_angle_deg(
            target_bearing_deg - current_heading_deg)
        steering = self.heading_kp * math.radians(heading_error_deg)
        steering = max(-self.max_steer_rad, min(self.max_steer_rad, steering))

        dist = haversine_m(
            self.current_lat, self.current_lon, wp_lat, wp_lon)
        speed = self.default_speed_mps
        if dist < self.waypoint_radius_m * 2.0:
            speed = max(0.5, self.default_speed_mps * (dist / self.waypoint_radius_m))

        cmd = AckermannDriveStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.header.frame_id = 'base_link'
        cmd.drive.speed = speed
        cmd.drive.steering_angle = steering
        self.cmd_pub.publish(cmd)

        self.get_logger().debug(
            f'wp={self.waypoint_index} dist={dist:.1f}m '
            f'bearing={target_bearing_deg:.1f} err={heading_error_deg:.1f} '
            f'steer={steering:.3f} speed={speed:.2f}')


def main(args=None):
    rclpy.init(args=args)
    node = GPSWaypointFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
