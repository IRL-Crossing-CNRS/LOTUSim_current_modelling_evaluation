from scipy.interpolate import interp1d


# Fonction d'interpolation des vitesses de courant
def interpolate_current_velocity(depths, uo, vo, interp_depth, method="cubic"):
    f_uo = interp1d(depths, uo, kind=method, fill_value="extrapolate")
    f_vo = interp1d(depths, vo, kind=method, fill_value="extrapolate")
    return f_uo(interp_depth), f_vo(interp_depth)
