import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import griddata, interp1d


# Function to import CSV data
def import_csv(filename):
    data = pd.read_csv(filename)
    data.columns = [
        col.lower() for col in data.columns
    ]  # Convert column names to lowercase
    return data


# Import single profile data
single_profile = import_csv("current_06_2024_brest_2.csv")

# Import multi-profile data
multi_profile = import_csv("currents_06_2024_brest_zone.csv")


# 1D Interpolation Function
def interpolate_1d(depth, u0, v0, target_depth, method):
    u0_interp = interp1d(depth, u0, kind=method, fill_value="extrapolate")(target_depth)
    v0_interp = interp1d(depth, v0, kind=method, fill_value="extrapolate")(target_depth)
    return u0_interp, v0_interp


# 3D Interpolation Function
def interpolate_3d(
    lat, lon, depth, u0, v0, target_lat, target_lon, target_depth, method
):
    grid_lat, grid_lon, grid_depth = np.meshgrid(
        target_lat, target_lon, target_depth, indexing="ij"
    )

    u0_interp = griddata(
        (lat, lon, depth), u0, (grid_lat, grid_lon, grid_depth), method=method
    )
    v0_interp = griddata(
        (lat, lon, depth), v0, (grid_lat, grid_lon, grid_depth), method=method
    )

    return u0_interp, v0_interp


# User Input Function
def get_user_input():
    methods = ["linear", "nearest", "cubic"]
    print("Select interpolation method (0=linear, 1=nearest, 2=cubic):")
    method_idx = int(input())
    interp_method = methods[method_idx]

    target_depth = float(input("Enter target depth: "))

    target_lat = input("Enter target latitude (leave empty for 1D interpolation): ")
    if target_lat:
        target_lat = float(target_lat)
        target_lon = float(input("Enter target longitude: "))
    else:
        target_lat = target_lon = None

    return interp_method, target_depth, target_lat, target_lon


# Main Script
interp_method, target_depth, target_lat, target_lon = get_user_input()

if target_lat is None:  # 1D Interpolation
    u0_interp, v0_interp = interpolate_1d(
        single_profile["depth"],
        single_profile["uo"],
        single_profile["vo"],
        target_depth,
        interp_method,
    )
    print(f"Interpolated u0 at depth {target_depth}m: {u0_interp}")
    print(f"Interpolated v0 at depth {target_depth}m: {v0_interp}")

    # Plotting 1D Results
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].plot(single_profile["uo"], single_profile["depth"], "b-", linewidth=2)
    axes[0].plot(u0_interp, target_depth, "ro", markersize=10, markerfacecolor="r")
    axes[0].invert_yaxis()
    axes[0].set_xlabel("u0 (m/s)")
    axes[0].set_ylabel("Depth (m)")
    axes[0].set_title("u0 Profile")
    axes[0].grid(True)

    axes[1].plot(single_profile["vo"], single_profile["depth"], "b-", linewidth=2)
    axes[1].plot(v0_interp, target_depth, "ro", markersize=10, markerfacecolor="r")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("v0 (m/s)")
    axes[1].set_ylabel("Depth (m)")
    axes[1].set_title("v0 Profile")
    axes[1].grid(True)

    fig.suptitle(f"1D Interpolation Results ({interp_method} method)")
    plt.show()
else:  # 3D Interpolation
    u0_interp, v0_interp = interpolate_3d(
        multi_profile["latitude"],
        multi_profile["longitude"],
        multi_profile["depth"],
        multi_profile["uo"],
        multi_profile["vo"],
        target_lat,
        target_lon,
        target_depth,
        interp_method,
    )

    print(
        f"Interpolated u0 at (lat={target_lat}°, lon={target_lon}°, depth={target_depth}m): {u0_interp}"
    )
    print(
        f"Interpolated v0 at (lat={target_lat}°, lon={target_lon}°, depth={target_depth}m): {v0_interp}"
    )

    # Plotting 3D Results
    fig = plt.figure(figsize=(14, 6))

    ax1 = fig.add_subplot(121, projection="3d")
    ax1.scatter(
        multi_profile["longitude"],
        multi_profile["latitude"],
        multi_profile["depth"],
        c=multi_profile["uo"],
        cmap="viridis",
        s=20,
    )
    ax1.scatter(
        target_lon,
        target_lat,
        target_depth,
        c=u0_interp,
        cmap="viridis",
        s=100,
        edgecolors="k",
    )
    ax1.set_xlabel("Longitude (°)")
    ax1.set_ylabel("Latitude (°)")
    ax1.set_zlabel("Depth (m)")
    ax1.set_title("u0 Distribution")
    ax1.invert_zaxis()
    fig.colorbar(ax1.collections[0], ax=ax1, label="u0 (m/s)")

    ax2 = fig.add_subplot(122, projection="3d")
    ax2.scatter(
        multi_profile["longitude"],
        multi_profile["latitude"],
        multi_profile["depth"],
        c=multi_profile["vo"],
        cmap="viridis",
        s=20,
    )
    ax2.scatter(
        target_lon,
        target_lat,
        target_depth,
        c=v0_interp,
        cmap="viridis",
        s=100,
        edgecolors="k",
    )
    ax2.set_xlabel("Longitude (°)")
    ax2.set_ylabel("Latitude (°)")
    ax2.set_zlabel("Depth (m)")
    ax2.set_title("v0 Distribution")
    ax2.invert_zaxis()
    fig.colorbar(ax2.collections[0], ax=ax2, label="v0 (m/s)")

    fig.suptitle(f"3D Interpolation Results ({interp_method} method)")
    plt.show()
