from classes.utils.GaussMarkov import GaussMarkov


# Fonction pour créer une matrice d'objets GaussMarkov
def create_array_of_gauss_markov(m, n):
    return [[GaussMarkov() for _ in range(n)] for _ in range(m)]
