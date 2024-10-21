from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import osmnx as ox
import networkx as nx
import requests
import time
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# URL de l'API JCDecaux
API_URL = 'https://api.jcdecaux.com/vls/v1/stations?contract=nancy&apiKey=3993633e26d5c2fef3ff02b5273e99e26ffed693'

# Seuils pour définir une station surchargée ou sous-alimentée
SEUIL_SURCHARGE = 0.35
SEUIL_SOUS_ALIMENTE = 0.35

# Charger les graphes depuis les fichiers .graphml
G_cyclable = ox.load_graphml(filepath='phase2/graph_cyclable.graphml')
G_drive = ox.load_graphml(filepath='phase2/graph_drive.graphml')

# Configuration de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Rediriger vers la page de login si l'utilisateur n'est pas connecté

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id_, username):
        self.id = id_
        self.username = username

# Fonction pour charger un utilisateur
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('phase2/users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

# Route pour gérer les utilisateurs
@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'danger')
            return redirect(url_for('manage_users'))

        # Hash du mot de passe
        password_hash = generate_password_hash(password)

        try:
            # Ajouter l'utilisateur à la base de données
            conn = sqlite3.connect('phase2/users.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
            conn.commit()
            conn.close()
            flash('Utilisateur ajouté avec succès !', 'success')
        except sqlite3.IntegrityError:
            flash('Le nom d\'utilisateur existe déjà.', 'danger')

    return render_template('users.html')


# Initialisation de la base de données SQLite
def init_db():
    conn = sqlite3.connect('phase2/users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Fonction pour vérifier si le cache des stations est toujours valide
last_fetch_time = 0  # Variable globale pour stocker le dernier moment où les stations ont été récupérées
CACHE_DURATION = 60  # Durée de validité du cache (60 secondes)

def cache_est_valide():
    return time.time() - last_fetch_time < CACHE_DURATION

# Page de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('phase2/users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1])
            login_user(user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

# Page de logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Route principale protégée par login
@app.route('/')
@login_required
def index():
    stations_surcharges, stations_sous_alimentees, stations_normales = recuperer_stations()
    return render_template('index.html',
                           stations_surcharges=stations_surcharges,
                           stations_sous_alimentees=stations_sous_alimentees,
                           stations_normales=stations_normales)

# API pour récupérer les stations de vélos au format JSON
@app.route('/api/stations')
@login_required
def api_stations():
    stations_surcharges, stations_sous_alimentees, stations_normales = recuperer_stations()

    def creer_liste_stations(stations):
        return [{'id': s[0], 'name': s[1], 'lat': s[2], 'lon': s[3], 'available_bikes': s[4], 'available_bike_stands': s[5]} for s in stations]

    data = {
        'surcharges': creer_liste_stations(stations_surcharges),
        'sous_alimentees': creer_liste_stations(stations_sous_alimentees),
        'normales': creer_liste_stations(stations_normales)
    }

    return jsonify(data)

# API pour calculer l'itinéraire
@app.route('/api/itineraire/<float:lat1>/<float:lon1>/<float:lat2>/<float:lon2>', methods=['POST'])
@login_required
def calculer_itineraire(lat1, lon1, lat2, lon2):
    data = request.get_json()
    mode_deplacement = data.get('mode')

    # Sélectionner le graphe en fonction du mode de déplacement
    if mode_deplacement == 'velo':
        G = G_cyclable
    elif mode_deplacement == 'camionette':
        G = G_drive
    else:
        return jsonify({"error": "Mode de déplacement inconnu"}), 400

    # Récupérer les nœuds les plus proches des deux points
    station_surchargee_node = ox.distance.nearest_nodes(G, lon1, lat1)
    station_sous_alimentee_node = ox.distance.nearest_nodes(G, lon2, lat2)

    try:
        # Calculer le plus court chemin
        chemin = nx.shortest_path(G, station_surchargee_node, station_sous_alimentee_node, weight='length')
        distance = nx.shortest_path_length(G, station_surchargee_node, station_sous_alimentee_node, weight='length')

        # Créer des instructions de base pour chaque étape
        instructions = [f"Continuez vers le nœud {node}" for node in chemin]

        # Retourner les coordonnées des points du chemin
        chemin_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in chemin]
        return jsonify({"chemin": chemin_coords, "distance": distance, "instructions": instructions})
    except nx.NetworkXNoPath:
        return jsonify({"error": "Pas de chemin trouvé"}), 400

# Fonction pour récupérer les données de l'API JCDecaux
def recuperer_stations():
    global stations_cache, last_fetch_time

    # Si le cache est encore valide, renvoyer les données en cache
    if cache_est_valide():
        return stations_cache['surcharges'], stations_cache['sous_alimentees'], stations_cache['normales']

    try:
        # Sinon, récupérer de nouvelles données depuis l'API
        response = requests.get(API_URL)
        response.raise_for_status()  # Vérifie que la réponse est valide (200 OK)
        stations = response.json()

        stations_surcharges = []
        stations_sous_alimentees = []
        stations_normales = []

        for station in stations:
            id_ = station['number']
            name = station['name']
            lat = station['position']['lat']
            lon = station['position']['lng']
            available_bikes = station['available_bikes']
            available_bike_stands = station['available_bike_stands']
            bike_stands = station['bike_stands']

            if available_bike_stands / bike_stands < SEUIL_SURCHARGE:
                stations_surcharges.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))
            elif available_bikes / bike_stands < SEUIL_SOUS_ALIMENTE:
                stations_sous_alimentees.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))
            else:
                stations_normales.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))

        # Mettre à jour le cache et l'heure de l'appel
        stations_cache = {
            'surcharges': stations_surcharges,
            'sous_alimentees': stations_sous_alimentees,
            'normales': stations_normales
        }
        last_fetch_time = time.time()

    except (requests.RequestException, ValueError) as e:
        # Si une erreur se produit, renvoyer le cache actuel sans mise à jour
        print(f"Erreur lors de la récupération des données : {e}")

    return stations_cache['surcharges'], stations_cache['sous_alimentees'], stations_cache['normales']


if __name__ == '__main__':
    init_db()  # Créer la table des utilisateurs si elle n'existe pas
    app.run(debug=True)
