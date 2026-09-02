import pandas as pd
from classes.Environment import Environment
from classes.utils.Constants import Constants

####################################
## Calcul sur un intervalle de temps
####################################
# Generer l'environnement
env = Environment()

# Paramètres de l'intervalle de temps
t_start = 0
t_end = 86400

# Nombre d'itérations
num_steps = 4

################ Partie Pierig ################

# Générer des temps aléatoires entre t_start et t_end
# random_times = np.random.uniform(t_start, t_end, num_steps)

###############################################

################ Partie Juliette ################

# Fixed times at 6h, 12h, 18h, and 24h (in seconds)
fixed_times = [21600, 43200, 64800, 86400]

#################################################

# Liste pour stocker les DataFrames à chaque étape
dataframes_list = []

# Boucle temporelle sur les temps aléatoires
# for iteration, time_step in enumerate(random_times, start=1):
for iteration, time_step in enumerate(fixed_times, start=1):
    # Afficher le numéro d'itération
    print(f"Iteration {iteration}/{num_steps} - Time step: {time_step}")
    ## Mettre à jour uwCurrents à chaque itération
    # Calcul de la surface
    env.underwaterObj.current_model.surface = env.surfaceObj.wave_model.elevation(
        env.surface, time_step
    )
    # calcul de la vitesse orbitale selon le modèle d'Airy
    OrbVelocity = env.surfaceObj.wave_model.orbital_velocity(
        Constants.G,
        time_step,
        env.underwaterObj.current_model.uwCurrent,
        env.underwaterObj.current_model.surface,
        env.underwaterObj.current_model.bathy,
    )
    # Calcul des UnderWater currents
    uwCurrents = env.underwaterObj.current_model.Vc()

    uwCurrents["uo"] = uwCurrents["uo"] + OrbVelocity["uo"]
    uwCurrents["vo"] = uwCurrents["vo"] + OrbVelocity["vo"]
    uwCurrents["wo"] = uwCurrents["wo"] + OrbVelocity["wo"]

    uwCurrents["time"] = time_step

    ## Stocker l'état de uwCurrents à cette étape
    dataframes_list.append(uwCurrents.copy())

# Concatenation des DataFrames et calcul de la moyenne pour 'uo', 'vo', et 'wo' pour chaque (x, y, depth)
concatenated_df = pd.concat(dataframes_list, axis=0)

####
####
# Tri des données par profondeur (depth) croissante
concatenated_df = concatenated_df.sort_values(by="depth")

concatenated_df.to_csv(Constants.outputFile, index=True)

# Calcul de la moyenne sur le temps pour chaque profondeur (depth) pour les trois composantes 'uo', 'vo', 'wo'
uwCurrents_mean = (
    concatenated_df.groupby("depth")[["uo", "vo", "wo"]].mean().reset_index()
)
####
####


# Calcul de la moyenne sur le temps pour chaque (x, y, depth) pour les trois composantes 'uo', 'vo', et 'wo'
uwCurrents_mean = (
    concatenated_df.groupby(["x", "y", "depth"])[["uo", "vo", "wo"]]
    .mean()
    .reset_index()
)

uwCurrents_mean.to_csv(Constants.outputMeanFile, index=True)


# #################################
# # Calcul pour un temps specifique
# #################################
# t=12
# # Generer l'environnement
# env = Environment()
# # Calcul de la surface
# env.underwaterObj.current_model.surface = env.surfaceObj.wave_model.elevation(env.surface, t)
# # calcul de la vitesse orbitale selon le modèle d'Airy
# OrbVelocity = env.surfaceObj.wave_model.orbital_velocity(Constants.G,t,env.underwaterObj.current_model.uwCurrent,\
#                                                         env.underwaterObj.current_model.surface, env.underwaterObj.current_model.bathy)
# # Calcul des UnderWater currents
# uwCurrents = env.underwaterObj.current_model.Vc()
# print(np.mean(OrbVelocity['uo'].values))
# print(np.mean(OrbVelocity['vo'].values))
# print(np.mean(uwCurrents['uo'].values))
# print(np.mean(uwCurrents['vo'].values))
# print(np.mean(env.inSituCurrents['uo'].values))
# print(np.mean(env.inSituCurrents['vo'].values))


# # Coordonnées (x, y) données pour lesquelles on souhaite extraire les valeurs des courants
# index_xy_given = 500


# # Filtrer le dataframe pour obtenir les lignes correspondant à ces coordonnées x et y
# # filtered_data = uwCurrents[(uwCurrents['x'] == uwCurrents['x'][index_xy_given]) & (uwCurrents['y'] == uwCurrents['y'][index_xy_given])]
# filtered_data = OrbVelocity[(OrbVelocity['x'] == OrbVelocity['x'][index_xy_given]) & (OrbVelocity['y'] == OrbVelocity['y'][index_xy_given])]

# # Extraire les valeurs des courants (uo, vo, wo) et de la profondeur (depth)
# currents_at_given_coordinates = filtered_data[['depth', 'uo', 'vo', 'wo']]

# # Extraire les valeurs de uo, vo et depth
# depth = filtered_data['depth'][0:20]
# uo = filtered_data['uo'][0:20]
# vo = filtered_data['vo'][0:20]
# print(depth)
# print(uo)
# print(vo)

# import matplotlib.pyplot as plt
# # Créer un graphique pour afficher uo et vo en fonction de depth
# plt.figure(figsize=(10, 6))

# # Tracer uo en fonction de depth
# plt.scatter(depth, uo)

# # Tracer vo en fonction de depth
# plt.scatter(depth, vo)

# plt.scatter(depth, np.sqrt(vo**2+uo**2))

# # Ajouter des labels et un titre
# plt.xlabel('Depth')
# plt.ylabel('Current (uo, vo)')
# plt.title('Courants uo et vo en fonction de la profondeur')

# # Ajouter une légende
# plt.legend()

# # Afficher le graphique
# plt.grid(True)
# plt.show()
