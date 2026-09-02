import numpy as np
import pandas as pd
from classes.utils.Constants import Constants
from scipy.interpolate import griddata


class CurrentModels:
    def __init__(self, currentModelName, f, surface, seabed, aerial, d, U10, uwCurrent):
        self.U10 = U10
        self.surface = surface
        self.bathy = seabed.bathy
        self.f = f
        self.windTauY = aerial.windTauY
        self.windTauX = aerial.windTauX
        self.selectModelFunction(currentModelName)
        self.d = d
        self.dTop = self.d
        self.dBottom = self.d
        self.surfaceHeight = Constants.SurfaceHeight
        self.RhoWater = Constants.RhoWater
        self.currentMeanVelocity = np.linalg.norm(
            [Constants.currentMeanU, Constants.currentMeanV]
        )
        self.uwCurrent = uwCurrent.copy()

    def Vc(self):
        # initialisation des courants sous marins a zero
        self.uwCurrent["uo"] = 0
        self.uwCurrent["vo"] = 0
        self.uwCurrent["wo"] = 0
        # Appel direct à la fonction du modèle sélectionné
        return self.modelFunction()

    def selectModelFunction(self, currentModelName):
        if currentModelName == "ekman":
            self.modelFunction = self.Vc_ekman
        elif currentModelName == "issc":
            self.modelFunction = self.Vc_ISSC
        elif currentModelName == "dnvrp":
            self.modelFunction = self.Vc_DNVRP
        elif currentModelName == "noc":
            self.modelFunction = self.Vc_NOC
        else:
            raise ValueError("Unknown current model")

    def Vc_ISSC(self):
        Vt0 = Constants.Vt0
        windAngle = Constants.windAngle
        Vm = self.currentMeanVelocity

        # Tidal component V_t(z)
        Vt = np.zeros_like(self.uwCurrent["depth"].value)
        maskVt = self.uwCurrent["depth"] < (self.bathy["deptho"] - 10)
        Vt[maskVt] = Vt0
        Vt[~maskVt] = Vt0 * np.log10(
            1
            + (
                9
                * (self.bathy["deptho"][~maskVt] - 10)
                / self.uwCurrent["depth"][~maskVt]
            )
        )

        # Local wave component V_{lw}(z)
        d0 = Constants.d0
        Vlw = np.zeros_like(self.uwCurrent["depth"].value)
        maskVlw = self.uwCurrent["depth"] < d0
        Vt[maskVlw] = 0.02 * self.U10 * ((d0 - self.uwCurrent["depth"][~maskVlw]) / d0)
        Vt[~maskVlw] = 0

        V = Vt + Vlw + Vm
        self.uwCurrent["uo"] = V * np.cos(np.radians(windAngle))
        self.uwCurrent["vo"] = V * np.sin(np.radians(windAngle))
        self.uwCurrent["wo"] = 0

        return self.uwCurrent

    def Vc_DNVRP(self):
        Vt0 = Constants.Vt0
        Vw0 = Constants.Wt0
        powLawAlpha = 1 / 7
        d0 = Constants.d0
        windAngle = Constants.windAngle

        # Tidal component V_t(z)
        Vt = np.zeros_like(self.uwCurrent["depth"].value)
        Vt = (
            Vt0
            * ((self.bathy["deptho"] + self.uwCurrent["depth"]) / self.bathy["deptho"])
            ** powLawAlpha
        )

        # Wind-driven component V_w(z)
        Vw = np.zeros_like(self.uwCurrent["depth"].value)
        maskVw = self.uwCurrent["depth"] < -d0
        Vw[maskVw] = Vw0 * ((d0 + self.uwCurrent["depth"][maskVw]) / d0)
        Vw[~maskVw] = 0

        V = Vt + Vw
        self.uwCurrent["uo"] = V * np.cos(np.radians(windAngle))
        self.uwCurrent["vo"] = V * np.sin(np.radians(windAngle))
        self.uwCurrent["wo"] = 0
        return self.uwCurrent

    def Vc_NOC(self):
        z_ob = Constants.z_ob
        nocDelta = Constants.nocDelta
        u_bar = self.currentMeanVelocity

        u_tz = np.zeros_like(self.uwCurrent["depth"].value)
        maskUtz_1 = (z_ob <= self.uwCurrent["depth"]) & (
            self.uwCurrent["depth"] <= 0.5 * nocDelta
        )
        maskUtz_2 = (0.5 * nocDelta <= self.uwCurrent["depth"]) & (
            self.uwCurrent["depth"] <= self.bathy["deptho"]
        )
        maskUtz_3 = (z_ob > self.uwCurrent["depth"]) & (
            self.uwCurrent["depth"] > 0.5 * nocDelta
        )
        u_tz[maskUtz_1] = (
            u_bar * np.log(self.uwCurrent["depth"][maskUtz_1] / z_ob)
        ) / (np.log(nocDelta / (2 * z_ob)) - nocDelta / (2 * self.bathy["deptho"]))
        u_tz[maskUtz_2] = (u_bar * np.log(nocDelta / (2 * z_ob))) / (
            np.log(nocDelta / (2 * z_ob)) - nocDelta / (2 * self.bathy["deptho"])
        )
        if np.any(maskUtz_3):
            raise ValueError("z value out of bounds")

        self.uwCurrent["uo"] = u_tz
        self.uwCurrent["vo"] = 0
        self.uwCurrent["wo"] = 0

        return self.uwCurrent

    def Vc_ekman(self):
        surfaceEstim = self.surface["elevation"]
        self.uwCurrent["uo"], self.uwCurrent["vo"], self.uwCurrent["wo"] = (
            self.Vc_middleLayer(self.uwCurrent[["x", "y", "depth"]])
        )
        # if self.uwCurrent['depth'] > surfaceEstim + 5:
        maskOver = self.uwCurrent["depth"] <= surfaceEstim - 5
        if np.any(maskOver):
            self.uwCurrent.loc[maskOver, "uo"] = 0
            self.uwCurrent.loc[maskOver, "vo"] = 0
            self.uwCurrent.loc[maskOver, "wo"] = 0
        # elif self.uwCurrent['depth'] > (surfaceEstim - self.dTop):
        maskTopLayer = (self.uwCurrent["depth"] < (self.dTop + surfaceEstim)) & (
            self.uwCurrent["depth"] > surfaceEstim - 5
        )
        if np.any(maskTopLayer):
            (
                self.uwCurrent.loc[maskTopLayer, "uo"],
                self.uwCurrent.loc[maskTopLayer, "vo"],
                self.uwCurrent.loc[maskTopLayer, "wo"],
            ) = self.Vc_topLayer(
                pd.DataFrame(
                    {
                        "x": self.uwCurrent["x"][maskTopLayer],
                        "y": self.uwCurrent["y"][maskTopLayer],
                        "depth": self.uwCurrent["depth"][maskTopLayer]
                        + surfaceEstim[maskTopLayer],
                    }
                )
            )
        # self.uwCurrent['uo'][maskTopLayer], self.uwCurrent['vo'][maskTopLayer], self.uwCurrent['wo'][maskTopLayer] = self.Vc_topLayer(pd.DataFrame({"x": self.uwCurrent['x'][maskTopLayer],"y": self.uwCurrent['y'][maskTopLayer],"depth": self.uwCurrent['depth'][maskTopLayer]-surfaceEstim[maskTopLayer]}))
        # elif self.uwCurrent['depth'] < self.bathy['deptho']:
        maskUnder = self.uwCurrent["depth"] >= self.bathy["deptho"]
        if np.any(maskUnder):
            self.uwCurrent.loc[maskUnder, "uo"] = 0
            self.uwCurrent.loc[maskUnder, "vo"] = 0
            self.uwCurrent.loc[maskUnder, "wo"] = 0
        # elif self.uwCurrent['depth'] < (self.bathy['deptho'] + self.dBottom):
        maskBottomLayer = self.uwCurrent["depth"] > (
            self.bathy["deptho"] - self.dBottom
        )
        if np.any(maskBottomLayer):
            (
                self.uwCurrent.loc[maskBottomLayer, "uo"],
                self.uwCurrent.loc[maskBottomLayer, "vo"],
                self.uwCurrent.loc[maskBottomLayer, "wo"],
            ) = self.Vc_bottomLayer(
                pd.DataFrame(
                    {
                        "x": self.uwCurrent["x"][maskBottomLayer],
                        "y": self.uwCurrent["y"][maskBottomLayer],
                        "depth": self.uwCurrent["depth"][maskBottomLayer],
                    }
                ),
                self.bathy[maskBottomLayer],
            )
        # self.uwCurrent['uo'][maskBottomLayer], self.uwCurrent['vo'][maskBottomLayer], self.uwCurrent['wo'][maskBottomLayer] = self.Vc_bottomLayer(pd.DataFrame({"x": self.uwCurrent['x'][maskBottomLayer],"y": self.uwCurrent['y'][maskBottomLayer],"depth": self.uwCurrent['depth'][maskBottomLayer]}))

        return self.uwCurrent

    def Vc_topLayer(self, uwCurrent_coord):
        u_middle, v_middle, _ = self.Vc_middleLayer(uwCurrent_coord)
        dtauyfdx = 0  # todo
        dtauxfdy = 0  # todo
        correc = 1
        u = u_middle + (np.sqrt(2) / (self.RhoWater * self.f * self.dTop)) * np.exp(
            2.0 * np.pi * (-uwCurrent_coord["depth"]) * correc / self.dTop
        ) * (
            (
                self.windTauX
                * np.cos(
                    2.0 * np.pi * (-uwCurrent_coord["depth"]) / self.dTop - np.pi / 4
                )
            )
            - self.windTauY
            * np.sin(2.0 * np.pi * (-uwCurrent_coord["depth"]) / self.dTop - np.pi / 4)
        )
        v = v_middle + (np.sqrt(2) / (self.RhoWater * self.f * self.dTop)) * np.exp(
            2.0 * np.pi * (-uwCurrent_coord["depth"]) * correc / self.dTop
        ) * (
            (
                self.windTauX
                * np.sin(
                    2.0 * np.pi * (-uwCurrent_coord["depth"]) / self.dTop - np.pi / 4
                )
            )
            + self.windTauY
            * np.cos(2.0 * np.pi * (-uwCurrent_coord["depth"]) / self.dTop - np.pi / 4)
        )
        # u = u_middle + (np.sqrt(2) / (self.RhoWater * self.f * self.dTop)) * np.exp(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) * correc / self.dTop) * (
        #     (self.windTauX * np.cos(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) / self.dTop - np.pi / 4)) - self.windTauY * np.sin(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) / self.dTop - np.pi / 4))
        # v = v_middle + (np.sqrt(2) / (self.RhoWater * self.f * self.dTop)) * np.exp(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) * correc / self.dTop) * (
        #     (self.windTauX * np.sin(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) / self.dTop - np.pi / 4)) + self.windTauY * np.cos(2.0*np.pi *(self.dTop-uwCurrent_coord['depth']) / self.dTop - np.pi / 4))

        w = (1 / self.RhoWater) * (
            dtauyfdx - dtauxfdy
        )  # Placeholder for dtauyfdx - dtauxfdy, which needs to be computed

        return u, v, w

    def Vc_middleLayer(self, uwCurrent_coord):
        u_middle = Constants.currentMeanU
        v_middle = Constants.currentMeanV
        w_middle = 0
        return u_middle, v_middle, w_middle

    def Vc_bottomLayer(self, uwCurrent_coord, bathy):
        u_middle, v_middle, _ = self.Vc_middleLayer(uwCurrent_coord)

        correctb = 1

        df1 = pd.DataFrame(
            {
                "x": np.ceil(uwCurrent_coord["x"]),
                "y": uwCurrent_coord["y"],
                "depth": uwCurrent_coord["depth"],
            }
        )
        df2 = pd.DataFrame(
            {
                "x": np.floor(uwCurrent_coord["x"]),
                "y": uwCurrent_coord["y"],
                "depth": uwCurrent_coord["depth"],
            }
        )
        df3 = pd.DataFrame(
            {
                "x": uwCurrent_coord["x"],
                "y": np.ceil(uwCurrent_coord["y"]),
                "depth": uwCurrent_coord["depth"],
            }
        )
        df4 = pd.DataFrame(
            {
                "x": uwCurrent_coord["x"],
                "y": np.floor(uwCurrent_coord["y"]),
                "depth": uwCurrent_coord["depth"],
            }
        )

        # Compute gradients in x and y directions
        smallest_float64 = np.finfo(np.float64).tiny
        dbdx = (
            self.get_bathy_at_position(df1, bathy)["deptho"]
            - self.get_bathy_at_position(df2, bathy)["deptho"]
        ) / (
            abs(np.ceil(uwCurrent_coord["x"]) - np.floor(uwCurrent_coord["x"]))
            + smallest_float64
        )
        dbdy = (
            self.get_bathy_at_position(df3, bathy)["deptho"]
            - self.get_bathy_at_position(df4, bathy)["deptho"]
        ) / (
            abs(np.ceil(uwCurrent_coord["y"]) - np.floor(uwCurrent_coord["y"]))
            + smallest_float64
        )

        # Middle layer velocities at shifted grid positions
        _, vcmlxpdx, _ = self.Vc_middleLayer(df1)
        _, vcmlxmdx, _ = self.Vc_middleLayer(df2)
        ucmlypdy, _, _ = self.Vc_middleLayer(df3)
        ucmlymdy, _, _ = self.Vc_middleLayer(df4)

        # Compute velocity gradients in x and y directions
        dvmiddx = (vcmlxpdx - vcmlxmdx) / (
            abs(np.ceil(uwCurrent_coord["x"]) - np.floor(uwCurrent_coord["x"]))
            + smallest_float64
        )
        dumiddy = (ucmlypdy - ucmlymdy) / (
            abs(np.ceil(uwCurrent_coord["y"]) - np.floor(uwCurrent_coord["y"]))
            + smallest_float64
        )

        # Compute velocity gradients in x and y directions
        dvmiddx = (vcmlxpdx - vcmlxmdx) / (
            abs(np.ceil(uwCurrent_coord["x"]) - np.floor(uwCurrent_coord["x"]))
            + smallest_float64
        )
        dumiddy = (ucmlypdy - ucmlymdy) / (
            abs(np.ceil(uwCurrent_coord["y"]) - np.floor(uwCurrent_coord["y"]))
            + smallest_float64
        )

        # Compute u, v, w velocities for the bottom layer
        u = u_middle * (
            1
            - np.exp(
                correctb
                * 2.0
                * np.pi
                * (uwCurrent_coord["depth"] - bathy["deptho"])
                / self.dBottom
            )
            * np.cos(
                2.0
                * np.pi
                * (bathy["deptho"] - uwCurrent_coord["depth"])
                / self.dBottom
            )
        ) - v_middle * np.exp(
            correctb
            * 2.0
            * np.pi
            * (uwCurrent_coord["depth"] - bathy["deptho"])
            / self.dBottom
        ) * np.sin(
            2.0 * np.pi * (bathy["deptho"] - uwCurrent_coord["depth"]) / self.dBottom
        )
        v = u_middle * np.exp(
            correctb
            * 2.0
            * np.pi
            * (uwCurrent_coord["depth"] - bathy["deptho"])
            / self.dBottom
        ) * np.sin(
            2.0 * np.pi * (bathy["deptho"] - uwCurrent_coord["depth"]) / self.dBottom
        ) + v_middle * (
            1
            - np.exp(
                correctb
                * 2.0
                * np.pi
                * (uwCurrent_coord["depth"] - bathy["deptho"])
                / self.dBottom
            )
            * np.cos(
                2.0
                * np.pi
                * (bathy["deptho"] - uwCurrent_coord["depth"])
                / self.dBottom
            )
        )

        # u = u_middle * (1 - np.exp(correctb * (uwCurrent_coord['depth'] - bathy['deptho']) / self.dBottom) * np.cos((bathy['deptho'] - uwCurrent_coord['depth']) / self.dBottom)) \
        #     - v_middle * np.exp(correctb * (uwCurrent_coord['depth'] - bathy['deptho']) / self.dBottom) * np.sin((bathy['deptho'] - uwCurrent_coord['depth']) / self.dBottom)
        # v = u_middle * np.exp(correctb * (uwCurrent_coord['depth'] - bathy['deptho']) / self.dBottom) * np.sin((bathy['deptho'] - uwCurrent_coord['depth']) / self.dBottom) \
        #     + v_middle * (1 - np.exp(correctb * (uwCurrent_coord['depth'] - bathy['deptho']) / self.dBottom) * np.cos((bathy['deptho'] - uwCurrent_coord['depth']) / self.dBottom))

        # w = (u_middle * dbdx + v_middle * dbdy) + (self.dBottom / 2) * (dvmiddx - dumiddy)
        w = 0

        return u, v, w

    # Function to get the bathy at a given position (x, y)
    def get_bathy_at_position(
        self, df_interpol, df_original, method=Constants.BottomMethod.lower()
    ):
        """
        Returns the bathy at a given position (x, y).

        Parameters:
        - x : x-coordinate where you want to interpolate
        - y : y-coordinate where you want to interpolate
        - df : DataFrame containing ['x', 'y', 'deptho'] (the original data)

        Returns:
        - depth : value of deptho at position (x, y)
        """
        points = df_original[["x", "y"]].values  # Coordonnées (x1, y1) de df1
        values = df_original["deptho"].values  # Valeurs de z associées
        query_points = df_interpol[["x", "y"]].values  # Coordonnées (x2, y2) de df2

        # Effectuer l'interpolation
        depth_interp = griddata(points, values, query_points, method="linear")

        # Ajouter les valeurs interpolées à df2
        df_interpol["deptho"] = depth_interp

        return df_interpol

    # Function to get the elevation at a given position (x, y)
    def get_surface_at_position(
        self, df_interpol, df_original, method=Constants.BottomMethod.lower()
    ):
        """
        Returns the elevation at a given position (x, y).

        Parameters:
        - x : x-coordinate where you want to interpolate
        - y : y-coordinate where you want to interpolate
        - df : DataFrame containing ['x', 'y', 'elevation'] (the original data)

        Returns:
        - elevation : value of elevation at position (x, y)
        """
        points = df_original[["x", "y"]].values  # Coordonnées (x1, y1) de df1
        values = df_original["elevation"].values  # Valeurs de z associées
        query_points = df_interpol[["x", "y"]].values  # Coordonnées (x2, y2) de df2

        # Effectuer l'interpolation
        elevation_interp = griddata(points, values, query_points, method="linear")

        # Ajouter les valeurs interpolées à df2
        df_interpol["elevation"] = elevation_interp

        return df_interpol

    # Function to get the interpolated bathy at a given position (x, y)
    def get_bathy_at_position_old(
        self, x, y, df, method=Constants.BottomMethod.lower()
    ):
        """
        Returns the interpolated bathy at a given position (x, y).

        Parameters:
        - x : x-coordinate where you want to interpolate
        - y : y-coordinate where you want to interpolate
        - df : DataFrame containing ['x', 'y', 'deptho'] (the original data)
        - method : interpolation method (default is 'linear')  {'linear', 'nearest', 'cubic'}

        Returns:
        - depth_interpolated : interpolated value of deptho at position (x, y)
        """
        # Using griddata to interpolate depth values at (x, y)
        depth_interpolated = griddata(
            (df["x"], df["y"]), df["deptho"], (x, y), method=method
        )

        return depth_interpolated

    # Function to get the interpolated elevation at a given position (x, y)
    def get_surface_at_position_old(
        self, x, y, df, method=Constants.BottomMethod.lower()
    ):
        """
        Returns the interpolated elevation at a given position (x, y).

        Parameters:
        - x : x-coordinate where you want to interpolate
        - y : y-coordinate where you want to interpolate
        - df : DataFrame containing ['x', 'y', 'elevation'] (the original data)
        - method : interpolation method (default is 'linear')  {'linear', 'nearest', 'cubic'}

        Returns:
        - elevation_interpolated : interpolated value of elevation at position (x, y)
        """
        print(df.columns)
        # Using griddata to interpolate elevation values at (x, y)
        elevation_interpolated = griddata(
            (df["x"], df["y"]), df["elevation"], (x, y), method=method
        )

        return elevation_interpolated
