from threading import Event

import rclpy
from classes.underwater.Underwater import Underwater
from geometry_msgs.msg import Pose, Vector3
from rclpy.node import Node


class CurrentsPublisher(Node):
    def __init__(self):
        super().__init__("node_pub_currents")
        self.pub_current = self.create_publisher(Vector3, "/ocean_current", 10)
        self.uw = Underwater("hflab4.jpg")
        self.subscription = self.create_subscription(
            Pose, "model/tethys/pose", self.currents_publisher_callback, 10
        )
        self.get_logger().info("Subscribed to the topic, waiting for messages...")
        self._exit_event = Event()

    def currents_publisher_callback(self, msg_pose):
        self.get_logger().info(f"Message received: {msg_pose.position}")

        # Compute the ocean current at the position from the message
        U, V, W = self.uw.compute(
            abs(msg_pose.position.x), abs(msg_pose.position.y), abs(msg_pose.position.z)
        )

        self.get_logger().info(f"Currents message published U: {U} V: {V} W: {W}")

        # Create the message to send
        msg_current = Vector3()
        msg_current.x = U
        msg_current.y = V
        msg_current.z = W

        # Publish the current velocity
        self.pub_current.publish(msg_current)

    def shutdown(self):
        self._exit_event.set()
        self.get_logger().info("Subscription finished, resources have been released.")


def main(args=None):
    rclpy.init(args=args)

    currents_publisher = CurrentsPublisher()

    # Wait for user to stop by closing the dialog or CTRL+C
    try:
        while not currents_publisher._exit_event.is_set():
            rclpy.spin_once(currents_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        currents_publisher.shutdown()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
