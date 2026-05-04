#!/usr/bin/env python3
"""
GPS Bridge Node for Point One Nav Atlas simulation.

Subscribes to Isaac Sim odometry (atlas/odometry) and publishes
sensor_msgs/NavSatFix on atlas/fix.

Converts local XYZ position (meters) to GPS coordinates using
a configurable origin point (default: Purdue Grand Prix track).

Usage:
    ros2 run --prefix 'python3' isaac_sim scripts/gps_bridge.py
    # or simply:
    python3 gps_bridge.py
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Header

# Purdue Grand Prix Track approximate center
ORIGIN_LAT = 40.4432
ORIGIN_LON = -86.9427
ORIGIN_ALT = 190.0

_WGS84_A = 6378137.0
_WGS84_E2 = 0.00669437999014


def meters_to_gps(x_east, y_north, z_up, origin_lat, origin_lon, origin_alt):
    """ENU offset in metres → (latitude_deg, longitude_deg, altitude_m)."""
    lat_rad = math.radians(origin_lat)
    n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat_rad) ** 2)
    m_per_deg_lat = math.radians(1) * n * (1 - _WGS84_E2) / (1 - _WGS84_E2 * math.sin(lat_rad) ** 2)
    m_per_deg_lon = math.radians(1) * n * math.cos(lat_rad)
    lat = origin_lat + (y_north / m_per_deg_lat)
    lon = origin_lon + (x_east / m_per_deg_lon)
    alt = origin_alt + z_up
    return lat, lon, alt


class GPSBridge(Node):
    def __init__(self):
        super().__init__("gps_bridge")

        # Declare parameters for GPS origin
        self.declare_parameter("origin_lat", ORIGIN_LAT)
        self.declare_parameter("origin_lon", ORIGIN_LON)
        self.declare_parameter("origin_alt", ORIGIN_ALT)
        self.declare_parameter("odom_topic", "atlas/odometry")
        self.declare_parameter("fix_topic", "atlas/fix")

        self.origin_lat = self.get_parameter("origin_lat").value
        self.origin_lon = self.get_parameter("origin_lon").value
        self.origin_alt = self.get_parameter("origin_alt").value

        odom_topic = self.get_parameter("odom_topic").value
        fix_topic = self.get_parameter("fix_topic").value

        # QoS: match Isaac Sim's default (reliable)
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        self.odom_sub = self.create_subscription(
            Odometry, odom_topic, self.odom_callback, qos
        )
        self.fix_pub = self.create_publisher(NavSatFix, fix_topic, qos)

        self.get_logger().info(
            f"GPS Bridge started: {odom_topic} -> {fix_topic} "
            f"(origin: {self.origin_lat:.4f}, {self.origin_lon:.4f}, {self.origin_alt:.1f}m)"
        )

    def odom_callback(self, msg: Odometry):
        pos = msg.pose.pose.position

        # Isaac Sim uses Y-forward, X-right, Z-up by default in the odom frame
        # Map to ENU: East=X, North=Y, Up=Z
        lat, lon, alt = meters_to_gps(
            x_east=pos.x,
            y_north=pos.y,
            z_up=pos.z,
            origin_lat=self.origin_lat,
            origin_lon=self.origin_lon,
            origin_alt=self.origin_alt,
        )

        fix = NavSatFix()
        fix.header = Header()
        fix.header.stamp = msg.header.stamp
        fix.header.frame_id = "atlas_gps_frame"

        fix.status.status = NavSatStatus.STATUS_FIX
        fix.status.service = NavSatStatus.SERVICE_GPS

        fix.latitude = lat
        fix.longitude = lon
        fix.altitude = alt

        # Position covariance — Point One Nav Atlas RTK accuracy ~1-2cm
        # Diagonal: [lat_var, lon_var, alt_var] in m^2
        fix.position_covariance = [
            0.0004, 0.0, 0.0,    # ~2cm std in lat
            0.0, 0.0004, 0.0,    # ~2cm std in lon
            0.0, 0.0, 0.0009,    # ~3cm std in alt
        ]
        fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN

        self.fix_pub.publish(fix)


def main(args=None):
    rclpy.init(args=args)
    node = GPSBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
