import numpy as np
from classes.surface.Airy import Airy
from classes.surface.DirectionalSpreading import DirectionalSpreading
from classes.surface.Spectrum import Spectrum
from classes.surface.Stretching import Stretching
from classes.utils.Constants import Constants
from scipy.optimize import fsolve


class Surface:
    def __init__(self, Hs, Tp, gamma, delta, surface_height):
        self.delta = delta
        self.h = surface_height
        self.spectrum = Spectrum(Hs, Tp, gamma)
        self.directional_spreading = DirectionalSpreading()
        self.stretching = Stretching(delta, self.h)
        self.spectrum_disc = self.discretize(
            self.directional_spreading,
            self.h,
            self.stretching,
            Constants.EqualEnergyBins,
        )
        self.wave_model = Airy(
            self.spectrum_disc, self.stretching, Constants.ConstantRandomPhase
        )
        self.Figure = None
        self.debugFigure = None
        self.debugSurfaceLine = None

    def discretize(self, D, h, stretching, equal_energy_bins):

        # Créer la gamme de omega et psi
        omega = np.linspace(Constants.OmegaMin, Constants.OmegaMax, Constants.NFreq)
        psi = np.linspace(-np.pi, np.pi, Constants.NDir + 1)
        psi = psi[:-1]  # Equivalent à 'psi(1:end-1)' en MATLAB

        # Calculer Si et Dj en utilisant des compréhensions de liste (équivalent à arrayfun)
        Si = np.array([self.spectrum.evaluate(w) for w in omega])
        Dj = np.array([D.evaluate(p) for p in psi])

        # Initialiser k avec la même forme que omega
        k = np.zeros_like(omega)

        # Remplir k en utilisant une boucle
        for i in range(len(omega)):
            k[i] = self.wave_number_functor(h, omega[i])

        spectrum_disc = {"omega": omega, "psi": psi, "Si": Si, "Dj": Dj, "k": k}

        return spectrum_disc

    def wave_number_functor(self, h, omega):
        g = 9.81
        f = lambda k: g * k * np.tanh(k * h) - omega**2
        k0 = omega**2 / g
        k = fsolve(f, k0)
        return k

    def rk4_step(self, x, z, t, dt, h):
        k1x, k1z = self.velocity(x, z, t, h)
        k2x, k2z = self.velocity(
            x + 0.5 * dt * k1x, z + 0.5 * dt * k1z, t + 0.5 * dt, h
        )
        k3x, k3z = self.velocity(
            x + 0.5 * dt * k2x, z + 0.5 * dt * k2z, t + 0.5 * dt, h
        )
        k4x, k4z = self.velocity(x + dt * k3x, z + dt * k3z, t + dt, h)

        x_next = x + (dt / 6) * (k1x + 2 * k2x + 2 * k3x + k4x)
        z_next = z + (dt / 6) * (k1z + 2 * k2z + 2 * k3z + k4z)

        return x_next, z_next

    def velocity(self, surface, t, inSituCurrents, bathy):
        eta = self.wave_model.elevation(self, surface, t)
        OrbVelocity = self.wave_model.orbital_velocity(
            self, Constants.G, t, inSituCurrents, eta, bathy
        )

        return OrbVelocity
