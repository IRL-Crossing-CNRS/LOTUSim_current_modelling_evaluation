import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from classes.aerial.Aerial import Aerial
from classes.surface.Surface import Surface
from classes.underwater.Underwater import Underwater
from classes.utils.Constants import Constants


class Environment:
    def __init__(self):
        self.U10 = None
        self.Hs = None
        self.gamma = None
        self.waveLength = None
        self.waveHeight = None
        self.Tp = None
        self.surfaceHeight = 0  # Assuming default value
        self.aerialObj = None
        self.aerial = None
        self.surfaceObj = None
        self.surface = None
        self.underwaterObj = None
        self.underwater = None
        self.uStar = None
        self.delta = 0
        self.Figure = None
        self.timeText = None
        self.d = None
        self.mixingParam = None
        self.f = None
        self.currents = None
        self.inSituCurrents = None

        # Lecture du fichier InSitu issu de Copernicus dans le but de recuperer le maillage (x,y,z)
        self.inSituCurrents = pd.read_csv(Constants.inSituCurrentFile)
        self.inSituCurrents["wo"] = (
            0  # on ajoute la composante selon z car cette dernière est calculée dans notre code,
        )
        # notamment lors du calcul des vitesses orbitales
        inSituCurrents_time_array = self.inSituCurrents.time.unique()
        self.inSituCurrents = self.inSituCurrents[
            self.inSituCurrents["time"] == inSituCurrents_time_array[0]
        ]  # on recupere la valeur du courants marins pour une seule date (la premiere arbitrairement)

        print(self.inSituCurrents)
        # Convertir toutes les colonnes numériques en float
        self.inSituCurrents[["x", "y", "depth", "uo", "vo", "wo"]] = (
            self.inSituCurrents[["x", "y", "depth", "uo", "vo", "wo"]].astype(float)
        )

        # on recupere le format des données InSitu pour les courants sous marins
        self.currents = self.inSituCurrents[
            ["x", "y", "depth", "uo", "vo", "wo"]
        ].copy()
        self.currents["uo", "vo", "wo"] = 0

        # Initialisation de la meteo
        self.setupMetocean(
            Constants.BeaufortCode, Constants.swellCode, Constants.seaStateCode
        )

        # Calcul de U10 (vitesse du vent)
        self.U10 = np.sqrt(Constants.v_north**2 + Constants.v_east**2)

        # Création de l'objet aérien
        self.aerialObj = Aerial(self.U10)

        # Création de l'objet surface
        self.surfaceObj = Surface(
            self.Hs, self.Tp, self.gamma, self.delta, self.surfaceHeight
        )
        self.surface = self.surfaceInit()

        # Paramètre de mélange
        self.mixingParam = Constants.mixingParameter

        # Calcul de f et fstar
        self.f, _ = self.compute_f_fstar(Constants.Omega, Constants.Lat)

        # Calcul de l'épaisseur d'Ekman
        self.computeEkmanThickness()

        # Initialisation de l'objet Underwater
        self.underwaterObj = Underwater(
            Constants.bathyFile,
            self.inSituCurrents,
            Constants.currentModelName,
            self.surface,  # Accès aux données de la surface Z
            self.aerialObj,
            self.d,
            self.f,
            self.U10,
        )
        # self.underwaterObj.current_model.dTop = self.d
        # self.underwaterObj.current_model.dBottom = self.d

        print(f"f dans init env: {self.f}")

    def setupMetocean(self, BeaufortCode, swellCode, seaStateCode):

        BeaufortCode = str(BeaufortCode).lower()  # Assure que le code est en minuscule

        # Définir les valeurs de U10 et sSC en fonction du code Beaufort
        if BeaufortCode in ["0", "calm"]:
            self.U10 = 0.1  # 0m/s
            sSC = 0
        elif BeaufortCode in ["1", "light_air"]:
            self.U10 = 0.9  # Valid range : 0.3 - 1.5m/s
            sSC = 1
        elif BeaufortCode in ["2", "light_breeze"]:
            self.U10 = 2.45  # Valid range : 1.6 - 3.3m/s
            sSC = 2
        elif BeaufortCode in ["3", "gentle_breeze"]:
            self.U10 = 4.4  # Valid range : 3.4 - 5.4m/s
            sSC = 3
        elif BeaufortCode in ["4", "moderate_breeze"]:
            self.U10 = 6.7  # Valid range : 5.5 - 7.9m/s
            sSC = 3  # Valid range : 3 - 4
        elif BeaufortCode in ["5", "fresh_breeze"]:
            self.U10 = 9.35  # Valid range : 8 - 10.7m/s
            sSC = 4
        elif BeaufortCode in ["6", "strong_breeze"]:
            self.U10 = 12.3  # Valid range : 10.8 - 13.8m/s
            sSC = 5
        elif BeaufortCode in ["7", "near_gale"]:
            self.U10 = 15.5  # Valid range : 13.9 - 17.1m/s
            sSC = 5  # Valid range : 5 - 6
        elif BeaufortCode in ["8", "gale"]:
            self.U10 = 18.95  # Valid range : 17.2 - 20.7m/s
            sSC = 6  # Valid range : 6 - 7
        elif BeaufortCode in ["9", "strong_gale"]:
            self.U10 = 22.6  # Valid range : 20.8 - 24.4m/s
            sSC = 7
        elif BeaufortCode in ["10", "storm"]:
            self.U10 = 26.45  # Valid range : 24.5 - 28.4m/s
            sSC = 8
        elif BeaufortCode in ["11", "violent_storm"]:
            self.U10 = 30.55  # Valid range : 28.5 - 32.6m/s
            sSC = 8
        elif BeaufortCode in ["12", "hurricane"]:
            self.U10 = 35  # Valid range : >32.7m/s
            sSC = 9
        else:
            raise ValueError(f"Invalid BeaufortCode: {BeaufortCode}")

        if seaStateCode < 9:  # Confused seaStateCode
            sSC = seaStateCode

        # Beaufort Scale (for wind speed)
        sSC = str(sSC).lower()

        # From WMO
        if sSC in ["calm_glassy", "0"]:
            self.Hs = 0  # 0m
            self.gamma = 3.5  # Valid range: 3.3 - 5
        elif sSC in ["calm_rippled", "1"]:
            self.Hs = 0.05  # Valid range: 0 - 0.1m
            self.gamma = 3.5  # Valid range: 3.3 - 5
        elif sSC in ["smooth", "2"]:
            self.Hs = 0.3  # Valid range: 0.1 - 0.5m
            self.gamma = 3.5  # Valid range: 3.3 - 5
        elif sSC in ["slight", "3"]:
            self.Hs = 0.875  # Valid range: 0.5 - 1.25m
            self.gamma = 3.5  # Valid range: 3.3 - 5
        elif sSC in ["moderate", "4"]:
            self.Hs = 1.875  # Valid range: 1.25 - 2.5m
            self.gamma = 2.65  # Valid range: 2 - 3.3
        elif sSC in ["rough", "5"]:
            self.Hs = 3.25  # Valid range: 2.5 - 4m
            self.gamma = 2.65  # Valid range: 2 - 3.3
        elif sSC in ["very_rough", "6"]:
            self.Hs = 5  # Valid range: 4 - 6m
            self.gamma = 2.65  # Valid range: 2 - 3.3
        elif sSC in ["high", "7"]:
            self.Hs = 7.5  # Valid range: 6 - 9m
            self.gamma = 2.65  # Valid range: 2 - 3.3
        elif sSC in ["very_high", "8"]:
            self.Hs = 11.5  # Valid range: 9 - 14m
            self.gamma = 1.5  # Valid range: 1 - 2
        elif sSC in ["phenomenal", "9"]:
            self.Hs = 14  # Valid range: >14m
            self.gamma = 1.5  # Valid range: 1 - 2

        # Swell Codes
        if swellCode == 0:  # No swell
            self.waveLength = 0
            self.waveHeight = 0
        elif swellCode == 1:  # Very Low
            self.waveLength = 50
            self.waveHeight = 1
        elif swellCode == 2:  # Low
            self.waveLength = 250
            self.waveHeight = 1
        elif swellCode == 3:  # Light
            self.waveLength = 50
            self.waveHeight = 3
        elif swellCode == 4:  # Moderate
            self.waveLength = 150
            self.waveHeight = 3
        elif swellCode == 5:  # Moderate rough
            self.waveLength = 250
            self.waveHeight = 3
        elif swellCode == 6:  # Rough
            self.waveLength = 50
            self.waveHeight = 5
        elif swellCode == 7:  # High
            self.waveLength = 150
            self.waveHeight = 5
        elif swellCode == 8:  # Very High
            self.waveLength = 250
            self.waveHeight = 5

        self.Tp = 5.3 * np.sqrt(self.Hs)  # DHI Shoreline management guidelines 2017

    def surfaceInit(self):

        # Créer une nouvelle dataframe surface du meme type que bathy
        self.surface = self.inSituCurrents[["x", "y"]].copy()
        self.surface["elevation"] = 0  # Remplace les valeurs de la colonne bathy par 0

        # Créer la figure et l'axe 3D
        # Vérifier si la figure existe déjà
        if self.Figure is None or not plt.fignum_exists(self.Figure.number):
            self.Figure = plt.figure(num="Surface Visualization")
        else:
            plt.figure(self.Figure.number)
            plt.clf()  # Clear the figure

        ax = self.Figure.add_subplot(111, projection="3d")

        # Tracer la surface
        self.surfacePlot = ax.scatter(
            self.surface["x"],
            self.surface["y"],
            self.surface["elevation"],
            c=self.surface["elevation"],
            cmap="viridis",
        )
        # self.surfacePlot = ax.plot_surface(X, Y, Z)

        # Ajouter des étiquettes
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Elevation")
        ax.set_title("Surface")

        self.ax = ax
        self.timeText = ax.text(
            0.02, 0.98, 0, "", transform=ax.transAxes, verticalalignment="top"
        )

        # Afficher le graphique
        plt.show()

        return self.surface

    def computeEkmanThickness(self):
        print(f"Value of uStar: {self.aerialObj.uStar}")
        print(f"Value of mixingParam: {self.mixingParam}")
        print(f"Value of f: {self.f}")
        self.uStar = self.aerialObj.uStar
        self.d = self.mixingParam * self.uStar / self.f
        print(f"Computed Ekman thickness (d): {self.d}")

    def compute_f_fstar(self, Omega, Lat):
        f = 2.0 * Omega * np.sin(np.radians(Lat)) / (2.0 * np.pi)
        fStar = 2.0 * Omega * np.cos(np.radians(Lat)) / (2.0 * np.pi)
        return f, fStar
