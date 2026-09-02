import matplotlib.pyplot as plt
import numpy as np


# Define the rescaled_z function
def rescaled_z(z, eta, h, Sdelta):
    if h == 0:
        return z
    else:
        mask = z > h
        z_scaled = np.copy(z)
        z_scaled[~mask] = (z[~mask] - h) * (Sdelta * eta[~mask] - h) / (
            eta[~mask] - h
        ) + h
        return z_scaled


# Define the depth range and stretching parameter
listZ = np.arange(-2, 4.01, 0.01)
listZStretching = np.zeros_like(listZ)

# Calculate the stretched depth values
for i in range(len(listZ)):
    listZStretching[i] = rescaled_z(listZ[i], 0.1, 20, 0)

# Calculate the coefficients
k = 2
h = 20
list_coeff2 = np.cosh(2 * (h - listZ)) / np.cosh(2 * h)
list_coeff3 = np.cosh(3 * (h - listZ)) / np.cosh(3 * h)
list_coeff22 = np.cosh(2 * (h - listZStretching)) / np.cosh(2 * h)

# Plotting the results
plt.figure()
plt.plot(listZ, list_coeff2, label="$k=2$")
# plt.plot(listZ, list_coeff3, label='$k=3$')  # Uncomment if you want to plot k=3
plt.plot(listZ, list_coeff22, label="$k=2$, Stretching")
plt.xlabel("Depth z [m]")
plt.ylabel("Coefficient value")
plt.grid(True)
plt.legend(fontsize=14)
plt.show()
