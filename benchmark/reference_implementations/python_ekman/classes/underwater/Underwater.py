from concurrent.futures import ThreadPoolExecutor

import matplotlib.pyplot as plt
import numpy as np
from classes.underwater.CurrentModels import CurrentModels
from classes.underwater.Seabed import Seabed


class Underwater:
    def __init__(
        self, bathy_file, inSituCurrents, current_model_name, surface, aerial, d, f, U10
    ):
        self.U10 = U10
        self.seabed = Seabed(bathy_file, inSituCurrents)
        self.f = f
        self.current_model = CurrentModels(
            current_model_name,
            self.f,
            surface,
            self.seabed,
            aerial,
            d,
            U10,
            inSituCurrents,
        )
        self.Figure = None

    def update_data(self, new_data):
        self.visualize()

    def visualize(self):
        print("Visualize underwater!")

        if self.Figure is None or not plt.fignum_exists(self.Figure):
            self.Figure = plt.figure("Sous l'eau")
        else:
            plt.figure(self.Figure)

        plt.title("Sous l'eau")

        # Add your actual plotting code here
        # This is where you would visualize the surface, currents, etc.

        plt.show()

    def compute_currents(self, X, Y, Z):
        n = len(X)  # Determine the number of iterations
        U = np.zeros(n)
        V = np.zeros(n)
        W = np.zeros(n)

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(self._compute_current, X, Y, Z))

        for i, result in enumerate(results):
            U[i], V[i], W[i] = result

        return U, V, W

    def _compute_current(self, x, y, z):
        # Assuming `currentModel.Vc` is a function that returns U, V, W at the coordinates (x, y, z)
        U, V, W = self.current_model.Vc(x, y, z)
        return U, V, W


# Example usage:
# underwater = Underwater(bathy_file="path_to_bathy.png", current_model_name="some_model", surface=surface_data, aerial=aerial_data, d=d_value, f=f_value, U10=U10_value)
# underwater.visualize()
