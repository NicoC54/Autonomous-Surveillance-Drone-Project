#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
from px4_msgs.msg import VehicleOdometry
from rclpy.qos import QoSProfile, ReliabilityPolicy
import math


def quaternion_to_euler(w, x, y, z):
    """Convertit quaternion → angles Euler (roll, pitch, yaw) en radians"""
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(t0, t1)

    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch = math.asin(t2)

    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(t3, t4)

    return roll, pitch, yaw


class DroneTFPublisher(Node):
    def __init__(self):
        super().__init__('drone_tf_pub')

        # --- TF Broadcasters ---
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)

        # --- Fréquence de publication du TF dynamique ---
        self.tf_period = 0.05  # 20 Hz
        self.last_tf_time = 0  # nanoseconds

        # Flag pour logguer un message une seule fois
        self._started_logged = False

        # --- Subscriber PX4 ---
        qos_profile = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.subscription = self.create_subscription(
            VehicleOdometry,
            '/fmu/out/vehicle_odometry',
            self.pose_callback,
            qos_profile
        )

        # --- TF Statique : base_link -> camera_link ---
        t_cam = TransformStamped()
        t_cam.header.stamp = self.get_clock().now().to_msg()
        t_cam.header.frame_id = 'base_link'
        t_cam.child_frame_id = 'camera_link'

        t_cam.transform.translation.x = 0.12
        t_cam.transform.translation.y = 0.03
        t_cam.transform.translation.z = 0.242
        t_cam.transform.rotation.x = 0.0
        t_cam.transform.rotation.y = 0.0
        t_cam.transform.rotation.z = 0.0
        t_cam.transform.rotation.w = 1.0

        self.static_tf_broadcaster.sendTransform(t_cam)
        self.get_logger().info("✅ Published static TF base_link -> camera_link (axes alignés)")
        self.get_logger().info("✅ DroneTFPublisher initialized, waiting for /clock...")

    # --- callback dynamique : dès que Px4 publie sur le topic /fmu/out/odometry pour l'odométrie du drone on publie le tf
    def pose_callback(self, msg: VehicleOdometry):
        """TF DYNAMIQUE : odom -> base_link"""
        now = self.get_clock().now().nanoseconds
        if now - self.last_tf_time < int(self.tf_period * 1e9): #on verifie que la frequence nest pas superieure a 20hz
            return
        self.last_tf_time = now

        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'x500_depth_0/odom'
        t.child_frame_id = 'base_link'

        # --- ✅ Conversion position NED -> ENU corrigée ---  on inverse y et z
        t.transform.translation.x = float(msg.position[0])    # avant/arrière → X
        t.transform.translation.y = float(-msg.position[1])   # gauche/droite → Y inversé
        t.transform.translation.z = float(-msg.position[2])   # haut/bas inversé

        # --- ✅ Conversion quaternion NED -> ENU corrigée --- on inverse y et z
        w = float(msg.q[0])
        x = float(msg.q[1])
        y = float(msg.q[2])
        z = float(msg.q[3]) 

        q_w = w
        q_x = x
        q_y = -y
        q_z = -z

        # Normalisation la norme d'un quaternion doit etre 1
        norm = math.sqrt(q_w*q_w + q_x*q_x + q_y*q_y + q_z*q_z)  
        if norm > 0.0:
            q_w /= norm
            q_x /= norm
            q_y /= norm
            q_z /= norm


        # On publie le nouveau quaternion adequat
        t.transform.rotation.w = q_w                
        t.transform.rotation.x = q_x
        t.transform.rotation.y = q_y
        t.transform.rotation.z = q_z

        self.tf_broadcaster.sendTransform(t)

        # --- DEBUG : affichage euler avant/après conversion ---
        roll_ned, pitch_ned, yaw_ned = quaternion_to_euler(w, x, y, z)
        roll_enu, pitch_enu, yaw_enu = quaternion_to_euler(q_w, q_x, q_y, q_z)

        if not self._started_logged:
            self.get_logger().info("✅ TF publishing started (20 Hz)")
            self._started_logged = True

        self.get_logger().debug(
            f"Yaw NED={math.degrees(yaw_ned):.1f}°, ENU={math.degrees(yaw_enu):.1f}° | "
            f"Pitch NED={math.degrees(pitch_ned):.1f}°, ENU={math.degrees(pitch_enu):.1f}° | "
            f"Roll NED={math.degrees(roll_ned):.1f}°, ENU={math.degrees(roll_enu):.1f}°"
        )


def main(args=None):
    rclpy.init(args=args)
    node = DroneTFPublisher()

    # Attente du /clock
    while rclpy.ok() and node.get_clock().now().nanoseconds == 0:
        rclpy.spin_once(node, timeout_sec=0.1)

    node.get_logger().info("✅ /clock detected, publishing TFs now.")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
