import matplotlib.pyplot as plt
import numpy as np


class FigureManager:
    def __init__(self, numFigures):
        # Initialisation des figures et des données associées
        self.Figures = [plt.figure() for _ in range(numFigures)]
        self.Data = [
            np.random.rand(10, 1) for _ in range(numFigures)
        ]  # Données initiales (par exemple)

    def updateData(self, figIndex, newData):
        # Mettre à jour les données d'une figure spécifique
        if figIndex < len(self.Figures):
            self.Data[figIndex] = newData
            self.plotData(
                figIndex
            )  # Mettre à jour le graphique pour la figure spécifiée
        else:
            raise IndexError("Figure index out of range.")

    def updateAllFigures(self):
        # Mettre à jour tous les graphiques
        for i in range(len(self.Figures)):
            self.plotData(i)

    def plotData(self, figIndex):
        # Méthode pour tracer les données d'une figure spécifique
        plt.figure(self.Figures[figIndex].number)
        plt.plot(self.Data[figIndex])
        plt.title(f"Figure {figIndex + 1}")  # Afficher le titre de la figure


# # Exemple d'utilisation de la classe
# if __name__ == "__main__":
#     figure_manager = FigureManager(3)  # Créer un gestionnaire de 3 figures
#     figure_manager.updateAllFigures()  # Mettre à jour tous les graphiques
#     plt.show()  # Afficher les graphiques
