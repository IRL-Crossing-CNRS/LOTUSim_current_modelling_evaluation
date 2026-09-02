import numpy as np
from scipy.interpolate import griddata


class Interpolation:

    @staticmethod
    def linear(x, x0, y0, x1, y1):
        """Linear interpolation"""
        return y0 + ((x - x0) / (x1 - x0)) * (y1 - y0)

    @staticmethod
    def bilinear(xd, yd, bathy):
        """Bilinear interpolation"""
        hmp = bathy
        if not (np.mod(xd, 1) == 0 and np.mod(yd, 1) == 0):
            xb = np.floor(xd).astype(int)
            yb = np.floor(yd).astype(int)
            xb1 = np.ceil(xd).astype(int)
            yb1 = np.ceil(yd).astype(int)

            firstRatio = (yb1 - yd) / (yb1 - yb)
            secondRatio = (yd - yb) / (yb1 - yb)

            bxdyb = firstRatio * hmp[yb, xb] + secondRatio * hmp[yb1, xb]
            bxdyb1 = firstRatio * hmp[yb, xb1] + secondRatio * hmp[yb1, xb1]

            b = ((xb1 - xd) / (xb1 - xb)) * bxdyb + ((xd - xb) / (xb1 - xb)) * bxdyb1
        elif not np.mod(yd, 1) == 0:
            yb = np.floor(yd).astype(int)
            yb1 = np.ceil(yd).astype(int)
            b = Interpolation.linear(yd, yb, hmp[yd, xb], yb1, hmp[yd, xb1])
        elif not np.mod(xd, 1) == 0:
            xb = np.floor(xd).astype(int)
            xb1 = np.ceil(xd).astype(int)
            b = Interpolation.linear(xd, xb, hmp[xb, yd], xb1, hmp[xb1, yd])
        else:
            b = hmp[xd, yd]
        return b

    @staticmethod
    def bilinear_polynomial(xd, yd, bathy):
        """Bilinear polynomial fit on unit square"""
        hmp = bathy
        xb = np.floor(xd).astype(int)
        xb1 = np.ceil(xd).astype(int)
        yb = np.floor(yd).astype(int)
        yb1 = np.ceil(yd).astype(int)

        a00 = hmp[xb, yb]
        a10 = hmp[xb1, yb] - a00
        a01 = hmp[xb, yb1] - a00
        a11 = hmp[xb1, yb1] - a10 - hmp[xb, yb1]

        b = a00 + a10 * xd + a01 * yd + a11 * xd * yd
        return b

    @staticmethod
    def nearest_neighbour(x, y, bathy):
        """Nearest neighbour interpolation"""
        x = round(x)
        y = round(y)
        return bathy[x, y]

    @staticmethod
    def interpolate_3D_current_velocity(
        lon,
        lat,
        depth,
        uo_matrix,
        vo_matrix,
        target_lon,
        target_lat,
        target_depth,
        wb=None,
        current_iter=None,
        total_iter=None,
    ):
        """3D interpolation for current velocity"""

        # Create meshgrid for the original data points
        LON, LAT, DEPTH = np.meshgrid(lon, lat, depth)

        # Reshape matrices and remove NaN values
        valid_idx = ~np.isnan(uo_matrix) & ~np.isnan(vo_matrix)
        LON_valid = LON[valid_idx]
        LAT_valid = LAT[valid_idx]
        DEPTH_valid = DEPTH[valid_idx]
        UO_valid = uo_matrix[valid_idx]
        VO_valid = vo_matrix[valid_idx]

        # Perform scattered interpolation
        uo_interp = griddata(
            (LON_valid, LAT_valid, DEPTH_valid),
            UO_valid,
            (target_lon, target_lat, target_depth),
            method="linear",
        )
        vo_interp = griddata(
            (LON_valid, LAT_valid, DEPTH_valid),
            VO_valid,
            (target_lon, target_lat, target_depth),
            method="linear",
        )

        # Update waitbar if provided
        if wb and current_iter is not None and total_iter is not None:
            from tqdm import tqdm

            tqdm.write(f"Interpolating point {current_iter} of {total_iter}")
            wb.update(current_iter / total_iter)

        return uo_interp, vo_interp


# # Exemple d'utilisation

# if __name__ == "__main__":
#     # Définir un bathy (exemple)
#     bathy = np.random.rand(10, 10)
#     xd, yd = 2.5, 3.7
#     print("Bilinear interpolation:", Interpolation.bilinear(xd, yd, bathy))

#     # Définir des coordonnées pour interpolation 3D
#     lon = np.linspace(0, 10, 10)
#     lat = np.linspace(0, 10, 10)
#     depth = np.linspace(0, 100, 10)

#     uo_matrix = np.random.rand(10, 10, 10)
#     vo_matrix = np.random.rand(10, 10, 10)

#     target_lon = 5.5
#     target_lat = 5.5
#     target_depth = 50

#     uo_interp, vo_interp = Interpolation.interpolate_3D_current_velocity(lon, lat, depth, uo_matrix, vo_matrix, target_lon, target_lat, target_depth)

#     print(f"Interpolated Uo: {uo_interp}")
#     print(f"Interpolated Vo: {vo_interp}")
