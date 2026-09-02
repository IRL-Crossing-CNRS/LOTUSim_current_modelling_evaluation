import numpy as np


class Airy:
    def __init__(self, spectrum, stretching, constant_random_phase):
        self.spectrum = spectrum
        self.stretching = stretching
        self.flat_spectrum = self.flatten(spectrum, constant_random_phase)

    def elevation(self, surface, t):
        """
        Calcule l'élévation à un moment donné (t) pour les coordonnées (x, y).
        """
        newSurface = surface.copy()
        newSurface["elevation"] = 0  # initialisation de la colonne elevation
        # Parcours des spectres
        for i in range(len(self.flat_spectrum["psi"])):
            a = self.flat_spectrum["a"][i]
            omega_t = (
                self.flat_spectrum["omega"][i] * t
            )  # Assurez-vous que omega_t est en float
            k_xCosPsi_ySinPsi = self.flat_spectrum["k"][i] * (
                surface["x"].values * self.flat_spectrum["cos_psi"][i]
                + surface["y"].values * self.flat_spectrum["sin_psi"][i]
            )
            theta = self.flat_spectrum["phase"][i]

            # S'assurer que a, omega_t, k_xCosPsi_ySinPsi et theta sont bien des float64
            a = float(a)
            omega_t = float(omega_t)
            theta = float(theta)
            k_xCosPsi_ySinPsi = np.asarray(k_xCosPsi_ySinPsi, dtype=np.float64)

            # Mise à jour de zeta avec la formule sinusoïdale
            newSurface["elevation"] -= a * np.sin(-omega_t + k_xCosPsi_ySinPsi + theta)

        return newSurface

    def orbital_velocity(self, g, t, inSituCurrents, surface, bathy):
        """
        Calcule les vitesses orbitales u, v, w en fonction du temps (t), des positions (x, y, z),
        de la surface de l'eau eta et de la profondeur h.
        """
        orbVelocity = inSituCurrents[["x", "y", "depth", "uo", "vo"]].copy()
        orbVelocity["uo"] = 0
        orbVelocity["vo"] = 0
        orbVelocity["wo"] = 0

        # masque pour les points en dessous de la surface l'eau

        belowSurface = orbVelocity["depth"] >= surface["elevation"]

        for i in range(len(self.flat_spectrum["psi"])):
            omega = self.flat_spectrum["omega"][i]
            k = self.flat_spectrum["k"][i]

            # Calcul des facteurs uniquement pour les points sous la surface
            pdyn_factor = np.zeros_like(orbVelocity["depth"].values)
            pdyn_factor_sh = np.zeros_like(orbVelocity["depth"].values)

            # if k * h > 3:
            #     pdyn_factor[belowSurface] = np.exp(-k * orbVelocity['depth'][belowSurface])
            #     pdyn_factor_sh[belowSurface] = np.exp(-k * orbVelocity['depth'][belowSurface])
            # else:
            #     pdyn_factor[belowSurface] = np.cosh(k * (bathy['deptho'][belowSurface] - orbVelocity['depth'][belowSurface])) / np.cosh(k * bathy['deptho'][belowSurface])
            #     pdyn_factor_sh[belowSurface] = np.sinh(k * (bathy['deptho'][belowSurface] - orbVelocity['depth'][belowSurface])) / np.cosh(k * bathy['deptho'][belowSurface])

            # Calculs des facteurs dynamiques sous la surface de l'eau sans masque 'upperKH'
            pdyn_factor[belowSurface] = np.where(
                k * bathy["deptho"][belowSurface] > 3,
                np.exp(-k * orbVelocity["depth"][belowSurface]),
                np.cosh(
                    k
                    * (
                        bathy["deptho"][belowSurface]
                        - orbVelocity["depth"][belowSurface]
                    )
                )
                / np.cosh(k * bathy["deptho"][belowSurface]),
            )

            pdyn_factor_sh[belowSurface] = np.where(
                k * bathy["deptho"][belowSurface] > 3,
                np.exp(-k * orbVelocity["depth"][belowSurface]),
                np.sinh(
                    k
                    * (
                        bathy["deptho"][belowSurface]
                        - orbVelocity["depth"][belowSurface]
                    )
                )
                / np.cosh(k * bathy["deptho"][belowSurface]),
            )

            # upperKH = k * bathy['deptho'][belowSurface] > 3
            # pdyn_factor[belowSurface] = upperKH * np.exp(-k * orbVelocity['depth'][belowSurface])\
            #     + (1-upperKH) * np.cosh(k * (bathy['deptho'][belowSurface] - orbVelocity['depth'][belowSurface])) / np.cosh(k * bathy['deptho'][belowSurface])
            # pdyn_factor_sh[belowSurface] = upperKH * np.exp(-k * orbVelocity['depth'][belowSurface])\
            #     + (1-upperKH) * np.sinh(k * (bathy['deptho'][belowSurface] - orbVelocity['depth'][belowSurface])) / np.cosh(k * bathy['deptho'][belowSurface])

            # print('tt')
            # print(bathy['deptho'][belowSurface])
            # print('tot')
            # print(orbVelocity['depth'][belowSurface])
            # time.sleep(1)

            k_xCosPsi_ySinPsi = k * (
                orbVelocity["x"] * self.flat_spectrum["cos_psi"][i]
                + orbVelocity["y"] * self.flat_spectrum["sin_psi"][i]
            )
            theta = omega * t - k_xCosPsi_ySinPsi - self.flat_spectrum["phase"][i]
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            a_k_omega = self.flat_spectrum["a"][i] * k / omega

            orbVelocity["uo"] += (
                a_k_omega
                * pdyn_factor
                * np.cos(self.flat_spectrum["psi"][i])
                * sin_theta
            )
            orbVelocity["vo"] += (
                a_k_omega
                * pdyn_factor
                * np.sin(self.flat_spectrum["psi"][i])
                * sin_theta
            )
            orbVelocity["wo"] += a_k_omega * pdyn_factor_sh * cos_theta

        orbVelocity["uo"] *= g
        orbVelocity["vo"] *= g
        orbVelocity["wo"] *= g

        # Set velocities to zero above the water surface
        orbVelocity.loc[~belowSurface, "uo"] = 0
        orbVelocity.loc[~belowSurface, "vo"] = 0
        orbVelocity.loc[~belowSurface, "wo"] = 0

        return orbVelocity

    def flatten(self, spectrum, constant_random_phase):
        """
        Aplatir le spectre pour obtenir une version à phase plate.
        """
        omega_grid, psi_grid = np.meshgrid(spectrum["omega"], spectrum["psi"])
        Si_grid = np.tile(spectrum["Si"], (len(spectrum["psi"]), 1)).T
        Dj_grid = np.tile(spectrum["Dj"], (len(spectrum["omega"]), 1))

        flat_spectrum = {}
        flat_spectrum["omega"] = omega_grid.flatten()
        flat_spectrum["psi"] = psi_grid.flatten()
        flat_spectrum["cos_psi"] = np.cos(psi_grid.flatten())
        flat_spectrum["sin_psi"] = np.sin(psi_grid.flatten())
        flat_spectrum["k"] = np.tile(spectrum["k"], len(spectrum["psi"]))
        flat_spectrum["a"] = np.sqrt(
            2
            * Si_grid.flatten()
            * Dj_grid.flatten()
            * np.diff(spectrum["omega"][:2])
            * np.diff(spectrum["psi"][:2])
        )

        if constant_random_phase:
            flat_spectrum["phase"] = (
                2 * np.pi * np.random.rand(len(flat_spectrum["omega"]))
            )
            print("Phase random")
        else:
            flat_spectrum["phase"] = np.zeros_like(flat_spectrum["omega"])

        return flat_spectrum

    def visualize(self):
        # Cette fonction peut être implémentée pour afficher les résultats (par exemple, les vitesses orbitales)
        pass


# # Exemple d'utilisation de la classe Airy
# if __name__ == "__main__":
#     # Définir un spectre d'exemple et un étirement fictif
#     spectrum = {
#         'omega': np.linspace(0.1, 1, 10),  # Exemple de fréquence angulaire
#         'psi': np.linspace(-np.pi, np.pi, 20),  # Angles directionnels
#         'Si': np.ones(10),  # Spectre de puissance
#         'Dj': np.ones(20),  # Spectre de direction
#         'k': np.linspace(0.1, 1, 10)  # Valeurs de vecteurs d'onde
#     }
#     stretching = None  # À définir selon votre logique d'étirement
#     constant_random_phase = True

#     airy = Airy(spectrum, stretching, constant_random_phase)

#     # Exemple de calcul de l'élévation à t=0 pour des points (x, y)
#     x = np.array([1, 2, 3])
#     y = np.array([1, 2, 3])
#     t = 0
#     zeta = airy.elevation(x, y, t)
#     print("Elevations:", zeta)

#     # Exemple de calcul des vitesses orbitales à t=0
#     g = 9.81  # Gravité
#     z = np.array([1, 2, 3])
#     eta = np.array([0, 0, 0])
#     h = 10  # Profondeur
#     u, v, w = airy.orbital_velocity(g, x, y, z, t, eta, h)
#     print("Orbital velocities (u, v, w):", u, v, w)
