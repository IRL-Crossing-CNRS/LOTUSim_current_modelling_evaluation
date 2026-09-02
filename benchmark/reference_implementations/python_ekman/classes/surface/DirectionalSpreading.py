import matplotlib.pyplot as plt
import numpy as np
from classes.utils.Constants import Constants
from scipy.special import gamma


class DirectionalSpreading:
    def __init__(self):
        # Constantes provenant d'un module utils
        self.psi0 = Constants.Psi0
        self.s = Constants.S

        # Calcul de Fs en fonction de `s`
        self.Fs = (
            (2 ** (2 * self.s - 1) / np.pi)
            * (gamma(self.s + 1) ** 2)
            / gamma(2 * self.s + 1)
        )

    def evaluate(self, psi):
        # Fonction d'évaluation D(psi)
        return self.Fs * np.cos((psi - self.psi0) / 2) ** (2 * self.s)

    def visualize(self):
        # Visualisation de la fonction Directional Spreading
        psi = np.arange(-np.pi, np.pi, 0.1)
        D = np.zeros_like(psi)

        for i in range(len(psi)):
            D[i] = self.evaluate(psi[i])

        # Plot utilisant matplotlib
        plt.figure()
        ax = plt.subplot(111, projection="polar")
        ax.plot(psi, D)
        ax.set_title("Cos2s Directional Spreading")
        plt.show()


# # Exemple d'utilisation
# if __name__ == "__main__":
#     directional_spreading = DirectionalSpreading()
#     directional_spreading.visualize()
