import random


class GaussMarkov:
    def __init__(self):
        self.mean = 0
        self.min = -1
        self.max = 1
        self.mu = 0
        self.noiseAmp = 0
        self.Reset()
        random.seed()  # Initialize random number generator

    def Reset(self):
        self.var = self.mean
        self.lastUpdate = 0

    def SetMean(self, mean):
        if self.min > mean or self.max < mean:
            return False
        self.mean = mean
        self.Reset()
        return True

    def SetModel(self, mean, min_val, max_val, mu, noise):
        if (
            min_val >= max_val
            or min_val > mean
            or max_val < mean
            or noise < 0
            or mu < 0
            or mu > 1
        ):
            return False
        self.mean = mean
        self.min = min_val
        self.max = max_val
        self.mu = mu
        self.noiseAmp = noise
        self.Reset()
        return True

    def Update(self, time):
        step = time - self.lastUpdate
        random_val = (
            random.random() - 0.5
        )  # random() returns a float between [0.0, 1.0]
        self.var = (1 - step * self.mu) * self.var + self.noiseAmp * random_val
        self.var = max(min(self.var, self.max), self.min)
        self.lastUpdate = time
        return self.var

    def Print(self):
        print(f"Mean = {self.mean}")
        print(f"Min. Limit = {self.min}")
        print(f"Max. Limit = {self.max}")
        print(f"Mu = {self.mu}")
        print(f"Noise Amp. = {self.noiseAmp}")


# # Exemple d'utilisation de la classe
# if __name__ == "__main__":
#     gm = GaussMarkov()
#     gm.Print()

#     # Mettre à jour la variable et imprimer à chaque itération
#     for t in range(1, 11):
#         value = gm.Update(t)
#         print(f"At time {t}, the updated value is: {value}")
