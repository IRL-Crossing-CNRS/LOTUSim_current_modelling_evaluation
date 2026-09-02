import numpy as np


# Interpolation (juste un exemple, ajustez selon vos données et besoins)
def interpolate_3d_velocity(
    lat, lon, depth, uo_matrix, vo_matrix, target_lat, target_lon, target_depth
):
    # Exemple d'interpolation 3D (fonction à adapter)
    # Ce qui suit est un modèle simplifié, remplacez-le par votre méthode d'interpolation spécifique.
    return np.interp(target_depth, depth, uo_matrix), np.interp(
        target_depth, depth, vo_matrix
    )
