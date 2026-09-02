import matplotlib.pyplot as plt
import numpy as np


class Spectrum:
    def __init__(self, Hs, Tp, gamma):
        # Initialisation des paramètres
        self.gamma = gamma
        self.Hs2 = Hs**2  # Hs2 correspond à Hs^2
        self.omega0 = 2 * np.pi / Tp  # omega0 = 2*pi/Tp
        self.sigmaA = 0.07
        self.sigmaB = 0.09
        self.coeff = 1 - 0.287 * np.log(gamma)  # Calcul du coefficient

    def evaluate(self, omega):
        # Calcul du spectre en fonction de omega
        sigma = np.where(omega <= self.omega0, self.sigmaA, self.sigmaB)
        ratio = self.omega0 / omega
        alpha = ratio**4
        Awm5 = (5 / 16) * alpha / omega * self.Hs2
        Bwm4 = 1.25 * alpha
        r = np.exp(-0.5 * ((omega - self.omega0) / (sigma * self.omega0)) ** 2)
        S = self.coeff * Awm5 * np.exp(-Bwm4) * self.gamma**r
        return S

    def visualize(self):
        # Visualisation du spectre
        omega = np.arange(0.1, 2.1, 0.1)  # Plage de fréquences angulaires
        S = np.zeros_like(omega)

        for i in range(len(omega)):
            S[i] = self.evaluate(omega[i])

        # Plot avec matplotlib
        plt.figure()
        plt.plot(omega, S)
        plt.title("JONSWAP Spectrum")
        plt.xlabel("Angular Frequency (rad/s)")
        plt.ylabel("Spectral Density (m²s)")
        plt.grid(True)
        plt.show()


# # Exemple d'utilisation
# if __name__ == "__main__":
#     spectrum = Spectrum(Hs=3, Tp=12, gamma=3.3)
#     spectrum.visualize()
