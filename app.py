from flask import Flask, request, jsonify

app = Flask(__name__)

# Liste des utilisateurs avec des personnages des Simpson
users = [
    {"id": 1, "name": "Homer Simpson", "email": "homer.simpson@springfield.com"},
    {"id": 2, "name": "Marge Simpson", "email": "marge.simpson@springfield.com"},
    {"id": 3, "name": "Bart Simpson", "email": "bart.simpson@springfield.com"},
    {"id": 4, "name": "Lisa Simpson", "email": "lisa.simpson@springfield.com"},
    {"id": 5, "name": "Maggie Simpson", "email": "maggie.simpson@springfield.com"}
]

# Route GET pour récupérer la liste des utilisateurs (personnages Simpson)
@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(users)

# Route POST pour ajouter un utilisateur (personnage Simpson)
@app.route('/users', methods=['POST'])
def add_user():
    new_user = request.get_json()  # Récupérer les données envoyées dans le corps de la requête
    new_user['id'] = len(users) + 1  # Assigner un ID unique
    users.append(new_user)  # Ajouter le nouvel utilisateur à la liste
    return jsonify(new_user), 201  # Retourner l'utilisateur ajouté avec un code 201 (Created)

if __name__ == '__main__':
    app.run(debug=True)
