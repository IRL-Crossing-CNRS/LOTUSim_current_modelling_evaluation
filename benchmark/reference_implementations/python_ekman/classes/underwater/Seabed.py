import pandas as pd
from scipy.interpolate import griddata


class Seabed:
    def __init__(self, bathy_file, inSituCurrents):
        self.bathy = None
        self.generate_bottom_floor(bathy_file, inSituCurrents)

    def generate_bottom_floor(self, bathy_file, inSituCurrents):
        # Read csv file from extract copernicus data
        bathyCopernicus = pd.read_csv(rf"{bathy_file}")
        self.bathy = self.interpolateBathy(bathyCopernicus, inSituCurrents)

    def get_bathy(self):
        return self.bathy

    def interpolateBathy(self, bathy, inSituCurrents):
        pointsBathy = bathy[["x", "y"]].values  # coordonnées (x1, y1) de dataframe1
        valuesBathy = bathy["deptho"].values  # valeurs d1 à interpole

        # Les nouvelles coordonnées où interpoler (x2, y2) de dataframe2
        pointsInSituCurrents = inSituCurrents[["x", "y"]].values

        # Effectuer l'interpolation avec griddata
        bathy_interp = griddata(
            pointsBathy, valuesBathy, pointsInSituCurrents, method="linear"
        )

        # Créer dataframe avec les coordonnées InSitu et les valeurs interpolées de bathy
        dataframe = inSituCurrents[["x", "y"]].copy()  # Copier x,y de inSituCurrents
        dataframe["deptho"] = bathy_interp  # Ajouter les valeurs interpolées de bathy

        return dataframe
