import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

# Load the CSV file
filename = "data_lat_long_01_june_2024.csv"
data = pd.read_csv(filename)

# Extract the variables
latitude = data["latitude"]
longitude = data["longitude"]
depth = data["depth"]
uo = data["uo"]
vo = data["vo"]
X = np.column_stack((uo, vo))

# Center the data
X_mean = np.mean(X, axis=0)
X_centered = X - X_mean

# Perform PCA
pca = PCA()
pca.fit(X_centered)
explained = np.cumsum(pca.explained_variance_ratio_)
num_components = np.argmax(explained >= 0.95) + 1
Z = pca.transform(X_centered)[:, :num_components]
X_reconstructed = np.dot(Z, pca.components_[:num_components, :]) + X_mean

uo_afterPCA = X_reconstructed[:, 0]
vo_afterPCA = X_reconstructed[:, 1]

# Reshape the data for EOF analysis
unique_lat = np.unique(latitude)
unique_lon = np.unique(longitude)
unique_depth = np.unique(depth)

nlat = len(unique_lat)
nlon = len(unique_lon)
ndepth = len(unique_depth)

# Initialize matrices for uo and vo
uo_matrix = np.full((nlat, nlon, ndepth), np.nan)
vo_matrix = np.full((nlat, nlon, ndepth), np.nan)

# Fill the matrices with data
for i in range(len(data)):
    lat_idx = np.where(unique_lat == latitude.iloc[i])[0][0]
    lon_idx = np.where(unique_lon == longitude.iloc[i])[0][0]
    depth_idx = np.where(unique_depth == depth.iloc[i])[0][0]

    uo_matrix[lat_idx, lon_idx, depth_idx] = uo.iloc[i]
    vo_matrix[lat_idx, lon_idx, depth_idx] = vo.iloc[i]

# Flatten the matrices for EOF analysis
uo_flat = uo_matrix.reshape(-1, ndepth)
vo_flat = vo_matrix.reshape(-1, ndepth)

# Remove rows with NaNs
valid_rows_uo = ~np.any(np.isnan(uo_flat), axis=1)
valid_rows_vo = ~np.any(np.isnan(vo_flat), axis=1)

uo_flat_valid = uo_flat[valid_rows_uo, :]
vo_flat_valid = vo_flat[valid_rows_vo, :]

# Perform EOF analysis (PCA) on uo and vo
pca_uo = PCA()
pca_uo.fit(uo_flat_valid)
pca_vo = PCA()
pca_vo.fit(vo_flat_valid)

# Choose the number of modes to keep
n_modes = 17  # Adjust this number as needed

# Reconstruct uo and vo using the specified number of modes
uo_reconstructed = reconstruct_data(
    pca_uo.transform(uo_flat_valid), pca_uo.components_, n_modes
)
vo_reconstructed = reconstruct_data(
    pca_vo.transform(vo_flat_valid), pca_vo.components_, n_modes
)

# Initialize full-size reconstructed matrices
uo_reconstructed_full = np.full_like(uo_flat, np.nan)
vo_reconstructed_full = np.full_like(vo_flat, np.nan)

# Fill valid rows with reconstructed data
uo_reconstructed_full[valid_rows_uo, :] = uo_reconstructed
vo_reconstructed_full[valid_rows_vo, :] = vo_reconstructed

# Reshape the reconstructed data back to the original matrix form
uo_reconstructed_matrix = uo_reconstructed_full.reshape(nlat, nlon, ndepth)
vo_reconstructed_matrix = vo_reconstructed_full.reshape(nlat, nlon, ndepth)

# Compute the mean profile across latitude and longitude for each depth
uo_profile = np.mean(np.nanmean(uo_reconstructed_matrix, axis=1), axis=1) + np.mean(
    uo_flat_valid, axis=0
)
vo_profile = np.mean(np.nanmean(vo_reconstructed_matrix, axis=1), axis=1) + np.mean(
    vo_flat_valid, axis=0
)

# Load the second CSV file
filename2 = "data_lat_long_01_june_2024_2.csv"
data2 = pd.read_csv(filename2)

# Extract the variables
latitude2 = data2["latitude"]
longitude2 = data2["longitude"]
depth2 = data2["depth"]
uo2 = data2["uo"]
vo2 = data2["vo"]

# Plot uo profile
plt.figure()
plt.plot(uo_profile, unique_depth, "b-", linewidth=2, label="EOF uo profile")
plt.gca().invert_yaxis()
plt.plot(uo2, unique_depth, "r-", label="Real data uo profile")
plt.xlabel("u_0 [m/s]")
plt.ylabel("Depth [m]")
plt.grid(True)
plt.legend(fontsize=14, title="uo profiles")

# Plot vo profile
plt.figure()
plt.plot(vo_profile, unique_depth, "b-", linewidth=2, label="EOF vo profile")
plt.gca().invert_yaxis()
plt.plot(vo2, unique_depth, "r-", label="Real data vo profile")
plt.xlabel("v_0 [m/s]")
plt.ylabel("Depth [m]")
plt.grid(True)
plt.legend(fontsize=14, title="vo profiles")

# Create a 3D quiver plot
listX = np.full_like(unique_depth, 100)
listY = np.full_like(unique_depth, 100)
uo_profile_transposed = uo_profile.T
vo_profile_transposed = vo_profile.T
listW = np.zeros_like(uo_profile_transposed)

fig = plt.figure()
ax = fig.add_subplot(111, projection="3d")
ax.quiver(
    listX,
    listY,
    unique_depth,
    uo_profile_transposed,
    vo_profile_transposed,
    listW,
    color="red",
    label="Real data profile",
)
ax.set_xlabel("U [m/s]")
ax.set_ylabel("V [m/s]")
ax.set_zlabel("Depth [m]")
ax.invert_zaxis()  # Set Z-axis direction to reverse to increase depth downwards
ax.set_xlim([-400, 400])
ax.set_ylim([-500, 500])
plt.grid(True)
plt.legend(fontsize=14, title="Velocity profiles")

plt.show()


# Function to reconstruct data using specified number of modes
def reconstruct_data(score, coeff, n_modes):
    return np.dot(score[:, :n_modes], coeff[:n_modes, :])
