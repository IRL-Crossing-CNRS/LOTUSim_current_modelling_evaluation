import math

from classes.aerial.windModels.LogWindVelocityProfile import LogWindVelocityProfile
from classes.utils.Constants import Constants


class Aerial:
    def __init__(self, U10):
        self.U10 = U10
        self.windProfile = None
        self.windTauX = None
        self.windTauY = None
        self.uStar = None
        self.Figure = None
        self.windAngle = None
        self.U10 = U10
        self.compute_wind_parameters(Constants.v_north, Constants.v_east)
        self.computeWindFriction(self.windAngle)
        self.computeWindFrictionVelocity(Constants.Rb)
        self.windProfile = LogWindVelocityProfile(self.U10, Constants.WindZ0, 10)

    def computeWindDragCoefficient(self):
        print(f"In computeWindDrag: {self.U10}")
        if self.U10 < 20.228:
            CdWind = 7.88e-4 + 8.08e-5 * self.U10
        else:
            CdWind = 2.423e-3
        print(f"Cd value: {CdWind}")
        return CdWind

    def compute_wind_parameters(self, v_north, v_east):
        # Calculate wind angle
        self.windAngle = math.atan2(v_north, v_east)

        # Convert wind_angle from radians to degrees
        self.windAngle = math.degrees(self.windAngle)
        print(f"Wind angle before modulo: {self.windAngle}")

        # Adjust wind_angle to meteorological convention (0 to 360 degrees)
        self.windAngle = self.windAngle % 360
        print(f"Wind angle after modulo: {self.windAngle}")

    def computeStability(self, Rb):
        if Rb < 0:
            hRb = (1 - 60 * Rb) ** 0.1
        else:
            hRb = (1 + 60 * Rb) ** (-0.2)
        return hRb

    def computeWindFrictionVelocity(self, Rb):
        hRb = self.computeStability(Rb)
        self.uStar = (
            0.17 - 0.019 * self.U10 + 0.0042 * self.U10**2 - 8.4e-5 * self.U10**3
        ) * hRb

    def computeWindFriction(self, windAngle):
        print(f"In computeWindFriction: {self.U10}")
        CD = self.computeWindDragCoefficient()
        self.windTauX = (
            CD * Constants.RhoAir * self.U10**2 * math.cos(math.radians(windAngle))
        )
        self.windTauY = (
            CD * Constants.RhoAir * self.U10**2 * math.sin(math.radians(windAngle))
        )
        print(f"WindTauX: {self.windTauX}")
        print(f"WindTauY: {self.windTauY}")
