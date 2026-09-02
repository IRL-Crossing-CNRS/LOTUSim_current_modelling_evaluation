import matplotlib.pyplot as plt
import numpy as np
from classes.aerial.IWindModel import IWindModel  # Import de la classe abstraite


class LogWindVelocityProfile(IWindModel):
    def __init__(self, velocity, z0, zRef):
        if zRef <= 0:
            raise ValueError("The reference height must be strictly positive")
        if z0 <= 0:
            raise ValueError("The roughness length must be strictly positive")

        self.velocity = velocity
        self.z0 = z0
        self.zRef = zRef

    def getWindVelocity(self, z):
        """
        Compute the wind velocity at height z using the logarithmic profile.
        """
        v = np.zeros_like(z)
        v[z >= 0] = (
            self.velocity * np.log(z[z >= 0] / self.z0) / np.log(self.zRef / self.z0)
        )
        return v

    def visualize(self, zRange):
        """
        Visualize the wind velocity profile.
        """
        v = self.getWindVelocity(zRange)

        plt.figure()
        plt.plot(v, -zRange)  # Assuming negative zRange for plot
        plt.title("Logarithmic Wind Velocity Profile")
        plt.xlabel("Wind Velocity (m/s)")
        plt.ylabel("Height (m)")
        plt.grid(True)
        plt.show()
