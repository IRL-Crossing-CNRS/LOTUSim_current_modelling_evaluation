import rclpy
from rclpy.node import Node


class Ros2Subscriber:
    def __init__(self, topic_name, msg_type, callback_fcn):
        """
        Constructeur de la classe Ros2Subscriber
        :param topic_name: nom du topic ROS2
        :param msg_type: type de message ROS2
        :param callback_fcn: fonction de rappel pour traiter les messages
        """
        # Initialisation du noeud ROS2
        rclpy.init()
        self.node = Node("matlab_node")

        # Initialisation du subscriber ROS2
        self.subscriber = self.node.create_subscription(
            msg_type,
            topic_name,
            self.message_callback,
            10,  # Taille de la file d'attente
        )

        # Stockage de la fonction de rappel
        self.callback_fcn = callback_fcn

    def message_callback(self, msg):
        """
        Fonction de rappel appelée lorsqu'un message est reçu
        :param msg: message reçu
        """
        # Exécuter la fonction de rappel utilisateur
        self.callback_fcn(msg)

    def destroy(self):
        """
        Destructeur de la classe Ros2Subscriber
        Supprime le nœud et le subscriber ROS2
        """
        self.subscriber.destroy()
        self.node.destroy_node()
        rclpy.shutdown()


# Exemple d'utilisation
def callback(msg):
    print(f"Message reçu: {msg.data}")


# if __name__ == '__main__':
#     subscriber = Ros2Subscriber('topic_name', String, callback)

#     try:
#         rclpy.spin(subscriber.node)  # Garder le nœud ROS2 en fonctionnement
#     except KeyboardInterrupt:
#         pass
#     finally:
#         subscriber.destroy()
