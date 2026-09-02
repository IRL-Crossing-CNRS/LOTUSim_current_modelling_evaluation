import time

import numpy as np
import rclpy
from classes.underwater.Underwater import Underwater
from geometry_msgs.msg import Pose
from rclpy.node import Node


class CubePublisher(Node):
    def __init__(self):
        super().__init__("node_pub_cube")
        self.pose_pub = self.create_publisher(Pose, "/cube_currents", 10)
        self.uw = Underwater("hflab4.jpg")

        # Create a subscriber for the pose data to get initial position
        self.first_pose_sub = self.create_subscription(
            Pose, "/model/tethys/pose", self.first_pose_callback, 10
        )
        self.first_pose = None
        self.ready_event = rclpy.wait_for_service(1)

    def first_pose_callback(self, msg):
        self.first_pose = msg
        self.get_logger().info(f"Received initial pose: {msg.position}")
        self.get_logger().info(
            f"Initial position: X: {msg.position.x}, Y: {msg.position.y}, Z: {msg.position.z}"
        )

    def publish_cube_currents(self):
        if self.first_pose is None:
            self.get_logger().warn("Waiting for the first pose message...")
            return

        x0 = self.first_pose.position.x
        y0 = self.first_pose.position.y
        z0 = self.first_pose.position.z
        s = 50  # Side length of the cube
        half_s = s / 2

        x_range = np.linspace(x0 - half_s, x0 + half_s, 10)
        y_range = np.linspace(y0 - half_s, y0 + half_s, 10)
        z_range = np.linspace(z0 - half_s, z0 + half_s, 10)

        # Create the grid of points (meshgrid equivalent)
        X, Y, Z = np.meshgrid(x_range, y_range, z_range)
        points = np.vstack((X.flatten(), Y.flatten(), Z.flatten())).T

        # Create the message and publish for 1000 points
        for point in points[:1000]:
            msg_pub = Pose()
            msg_pub.position.x = point[0]
            msg_pub.position.y = point[1]
            msg_pub.position.z = point[2]

            # Compute ocean currents at the current point
            U, V, W = self.uw.compute(abs(point[0]), abs(point[1]), abs(point[2]))

            self.get_logger().info(
                f"X: {msg_pub.position.x}, Y: {msg_pub.position.y}, Z: {msg_pub.position.z}"
            )
            self.get_logger().info(f"U: {U}, V: {V}, W: {W}")

            # Set the orientation of the message based on currents
            msg_pub.orientation.x = U
            msg_pub.orientation.y = V
            msg_pub.orientation.z = -W  # As per the original MATLAB code

            # Publish the message
            self.pose_pub.publish(msg_pub)
            time.sleep(0.05)  # Simulate pause (in MATLAB: pause(0.05))

        self.get_logger().info("Finished publishing cube currents.")

    def shutdown(self):
        self.get_logger().info("Subscription finished, resources have been released.")


def main(args=None):
    rclpy.init(args=args)
    cube_publisher = CubePublisher()

    try:
        # Wait for the first pose message
        while not cube_publisher.first_pose:
            rclpy.spin_once(cube_publisher)

        # After getting the first pose, start publishing the cube currents
        cube_publisher.publish_cube_currents()

    except KeyboardInterrupt:
        pass
    finally:
        cube_publisher.shutdown()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
