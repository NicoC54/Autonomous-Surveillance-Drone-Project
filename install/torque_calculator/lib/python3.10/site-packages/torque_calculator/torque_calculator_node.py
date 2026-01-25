#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import numpy as np

# Messages
from actuator_msgs.msg import Actuators
from geometry_msgs.msg import WrenchStamped


class TorqueCalculatorNode(Node):
    def __init__(self):
        super().__init__('torque_calculator_node')

        # --- Constantes (issues du SDF PX4 x500) ---
        self.kf = 8.54858e-06           # motorConstant → Poussée (N / (rad/s)²)
        self.moment_constant = 0.016    # momentConstant → rapport km/kf
        self.km = self.moment_constant * self.kf  # ← km = 1.368e-7 Nm/(rad/s)²
        self.L = 0.174                  # Bras de levier (m)

        # --- Publisher ---
        self.torque_publisher_ = self.create_publisher(
            WrenchStamped,
            '/commanded_torques',
            10
        )

        # --- Subscriber ---
        self.motor_subscriber_ = self.create_subscription(
            Actuators,
            '/x500_depth_0/command/motor_speed',
            self.motor_callback,
            10
        )

        self.get_logger().info("Calculateur de couple démarré (PX4/Gazebo compatible).")

    def motor_callback(self, msg):
        if len(msg.velocity) < 4:
            return

        w = msg.velocity
        w0_sq = w[0]**2  # rotor_0: AVD (+x, -y), CCW
        w1_sq = w[1]**2  # rotor_1: ARG (-x, +y), CCW
        w2_sq = w[2]**2  # rotor_2: AVG (+x, +y), CW
        w3_sq = w[3]**2  # rotor_3: ARD (-x, -y), CW

        # --- Calcul des entrées de contrôle (U2, U3, U4) ---
        U2 = self.L * self.kf * (-w0_sq + w1_sq + w2_sq - w3_sq)  # Roulis (Nm)
        U3 = self.L * self.kf * (-w0_sq + w1_sq - w2_sq + w3_sq)  # Tangage (Nm)
        U4 = self.km * (w0_sq + w1_sq - w2_sq - w3_sq)            # Lacet (Nm)

        # --- Log pour debug (optionnel, à commenter en prod) ---
        self.get_logger().debug(
            f"Torques → Roll: {U2:+.3f}, Pitch: {U3:+.3f}, Yaw: {U4:+.3f} Nm"
        )

        # --- Publication ---
        wrench_msg = WrenchStamped()
        wrench_msg.header.stamp = self.get_clock().now().to_msg()
        wrench_msg.header.frame_id = 'base_link'

        wrench_msg.wrench.torque.x = U2
        wrench_msg.wrench.torque.y = U3
        wrench_msg.wrench.torque.z = U4

        self.torque_publisher_.publish(wrench_msg)


def main(args=None):
    rclpy.init(args=args)
    node = TorqueCalculatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()