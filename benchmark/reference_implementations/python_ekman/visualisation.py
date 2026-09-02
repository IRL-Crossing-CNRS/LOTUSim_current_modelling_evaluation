import concurrent.futures
import gc

import matplotlib.pyplot as plt
from classes.Environment import Environment

# Fermeture de toutes les fenêtres de graphiques
plt.close("all")

# Nettoyage de la mémoire (similaire à "clear")
gc.collect()


# Exemple d'initialisation de futures sans création automatique de pool
executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=None
)  # Pas de pool automatique


env = Environment()
env.visualiseAll()
