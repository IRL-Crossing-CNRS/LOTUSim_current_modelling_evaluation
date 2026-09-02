import numpy as np
from scipy.integrate import cumtrapz
from scipy.interpolate import PchipInterpolator


def depth_weighted_mean_cumtrapz(depth, velocity):
    # Trier depth et velocity par ordre croissant de depth
    sorted_depth = np.sort(depth)
    sort_idx = np.argsort(depth)
    sorted_velocity = np.array(velocity)[sort_idx]

    # Calculer l'intégrale cumulative
    cumulative_integral = cumtrapz(sorted_velocity, sorted_depth, initial=0)

    # Créer une grille de profondeur uniforme pour l'interpolation
    uniform_depth = np.linspace(np.min(sorted_depth), np.max(sorted_depth), 1000)

    # Interpoler l'intégrale cumulative sur la grille uniforme
    interpolator = PchipInterpolator(sorted_depth, cumulative_integral)
    interpolated_integral = interpolator(uniform_depth)

    # Calculer la moyenne pondérée en profondeur
    mean_velocity = np.diff(interpolated_integral[-2:]) / np.diff(uniform_depth[-2:])

    return mean_velocity[0]
