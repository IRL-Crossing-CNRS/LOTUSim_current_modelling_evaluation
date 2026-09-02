from abc import ABC, abstractmethod


class IWindModel(ABC):
    """
    Abstract base class for wind models.
    """

    @abstractmethod
    def getWindVelocity(self, z):
        """
        Method to calculate the wind velocity at height z.
        """

    @abstractmethod
    def visualize(self, zRange):
        """
        Method to visualize the wind velocity profile.
        """
