import matplotlib.pyplot as plt
import numpy as np
from classes.aerial.Aerial import Aerial

# Constants and initialization
dTop = 40
listz = np.arange(0, -dTop - 1, -1)  # Depth from 0 to -dTop
RhoWater = 1026  # Density of water
correc = 3
windTauX = 0.66592
windTauY = 1.1088
listU = np.zeros_like(listz)
listV = np.zeros_like(listz)
u_middle = 0
v_middle = 0
f = 1e-4  # Coriolis parameter
U10 = 8.4686  # Wind speed at 10 meters above the surface
listAngle = np.arange(0, 360, 30)  # Wind direction angles from 0 to 330
listwindttauX = np.zeros_like(listAngle)
listwindttauY = np.zeros_like(listAngle)

# Create Aerial object
AerialObj = Aerial(U10)

# Compute wind stress for each angle
for j in range(len(listAngle)):
    AerialObj.computeWindFriction(listAngle[j])
    listwindttauX[j] = AerialObj.windTauX
    listwindttauY[j] = AerialObj.windTauY

# Set up the plot
plt.figure()
plt.xlabel("U")
plt.ylabel("V")
plt.title("Ocean Current Plot")
plt.grid(True)
colors = plt.cm.jet(np.linspace(0, 1, len(listAngle)))  # Generate a color map

# Loop over each angle and compute the U and V components for each depth
legendEntries = []
for j in range(len(listAngle)):
    for i in range(len(listz)):
        z = listz[i]
        listU[i] = u_middle + (np.sqrt(2) / (RhoWater * f * dTop)) * np.exp(
            z * correc / dTop
        ) * (
            (listwindttauX[j] * np.cos(z / dTop - np.pi / 4))
            - (listwindttauY[j] * np.sin(z / dTop - np.pi / 4))
        )
        listV[i] = v_middle + (np.sqrt(2) / (RhoWater * f * dTop)) * np.exp(
            z * correc / dTop
        ) * (
            (listwindttauX[j] * np.sin(z / dTop - np.pi / 4))
            + (listwindttauY[j] * np.cos(z / dTop - np.pi / 4))
        )

    # Plot the
