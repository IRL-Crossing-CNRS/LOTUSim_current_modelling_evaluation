import matplotlib.pyplot as plt
import numpy as np


# Define the Cos2s directional spreading function (assuming it follows a cosine-based model)
def Cos2sDirectionalSpreading(psi0, s, psi):
    # Implement the Cos^2 directional spreading model
    return np.cos(np.radians(psi - psi0)) ** (2 * s)


# Create a figure
plt.figure()

# Define the range for psi (wave direction)
psi = np.arange(-np.pi, np.pi, 0.01)

# Define the list of spreading parameters
listS = [2, 5, 10, 30]

# Loop over each value of s in listS
for s in listS:
    D = np.zeros_like(psi)

    # Loop over each psi value
    for i in range(len(psi)):
        psi0 = 0  # Primary wave direction is along the x-axis
        D[i] = Cos2sDirectionalSpreading(psi0, s, psi[i])

    # Plot the directional spreading function on a polar plot
    plt.polar(psi, D, label=f"s={s}")

# Show the legend
plt.legend()

# Display the plot
plt.show()
