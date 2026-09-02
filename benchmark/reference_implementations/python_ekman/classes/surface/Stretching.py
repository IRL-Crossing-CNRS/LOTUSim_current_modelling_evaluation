import matplotlib.pyplot as plt
import numpy as np


class Stretching:
    def __init__(self, delta, h):
        self.delta = delta  # Paramètre delta
        self.h = h  # Profondeur h

    def rescaled_z(self, z, eta):
        # Fonction de mise à l'échelle de z
        z_scaled = z.copy()
        mask = (z <= eta) & (z >= -self.h)
        z_scaled[mask] = (z[mask] + self.h) * (self.delta * eta[mask] + self.h) / (
            eta[mask] + self.h
        ) - self.h
        return z_scaled

    def visualize(self):
        # Visualisation de la fonction de mise à l'échelle
        z = np.arange(-50, 1, 1)  # Plage de valeurs de z
        ksi = 5  # Exemple de hauteur de vague
        z_rescaled = np.zeros_like(z)

        for i in range(len(z)):
            z_rescaled[i] = self.rescaled_z(z[i], ksi)

        # Affichage avec matplotlib
        plt.figure()
        plt.plot(z, z_rescaled)
        plt.title("Stretching Function")
        plt.xlabel("Original z (m)")
        plt.ylabel("Rescaled z (m)")
        plt.grid(True)
        plt.show()


# # Exemple d'utilisation
# if __name__ == "__main__":
#     stretching = Stretching(delta=0.5, h=10)
#     stretching.visualize()
