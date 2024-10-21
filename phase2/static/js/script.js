// Initialiser la carte Leaflet
var map = L.map('map').setView([48.692054, 6.184417], 13);

// Ajouter une couche de base (tiles)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Variable globale pour stocker le contrôle d'itinéraire et le conteneur du panneau d'instructions
var currentRouteControl = null;
var currentSurchargeLat = null;
var currentSurchargeLon = null;
var stationMarkers = {};  // Stocke les marqueurs des stations par ID

// Charger les stations de l'API et mettre à jour la date de mise à jour
function loadStationsAndUpdateTime() {
    fetch('/api/stations')
        .then(response => response.json())
        .then(data => {
            // Supprimer tous les anciens marqueurs
            Object.values(stationMarkers).forEach(marker => map.removeLayer(marker));
            stationMarkers = {};  // Réinitialiser la liste des marqueurs

            // Vider la liste des stations dans le menu
            document.getElementById('stations-list').innerHTML = '';

            // Ajouter les stations sur la carte et dans le menu interactif
            addStationsToMap(data.surcharges, 'red', 'Station surchargée');
            addStationsToMap(data.sous_alimentees, 'blue', 'Station sous-alimentée');
            addStationsToMap(data.normales, 'green', 'Station normale');

            // Mettre à jour la date de la dernière mise à jour
            const currentDate = new Date();
            const formattedDate = currentDate.toLocaleString();
            document.getElementById('last-updated').textContent = `Dernière mise à jour : ${formattedDate}`;

            // Vérifier les mises à jour des stations et ajouter un clignotement si un vélo est retiré ou ajouté
            data.surcharges.concat(data.sous_alimentees, data.normales).forEach(station => {
                if (stationMarkers[station.id]) {
                    var previousAvailableBikes = stationMarkers[station.id].available_bikes;
                    if (previousAvailableBikes !== station.available_bikes) {
                        const bikeChange = station.available_bikes - previousAvailableBikes;
                        flashStationMarker(stationMarkers[station.id]);
                        displayStationUpdateMessage(station.name, station.available_bikes, previousAvailableBikes);
                        displayBikeChangeAnimation(stationMarkers[station.id], bikeChange);  // Appeler l'animation
                    }
                }
            });
        });
}


// Fonction pour ajouter des stations sur la carte
function addStationsToMap(stations, color, type) {
    stations.forEach(station => {
        var marker = L.marker([station.lat, station.lon], {
            icon: L.icon({
                iconUrl: `https://maps.google.com/mapfiles/ms/icons/${color}-dot.png`,
                iconSize: [32, 32]
            })
        }).addTo(map);

        // Ajouter chaque marqueur dans la liste des marqueurs par ID
        stationMarkers[station.id] = marker;
        stationMarkers[station.id].available_bikes = station.available_bikes;

        marker.bindPopup(`<b>${station.name}</b><br>${type}<br>Vélos disponibles : ${station.available_bikes}<br>Places disponibles : ${station.available_bike_stands}`);

        // Ajouter la station au menu interactif
        var li = document.createElement('li');
        li.classList.add('list-group-item');
        li.style.cursor = "pointer";

        if (type === 'Station surchargée') {
            li.innerHTML = `<i class="fas fa-exclamation-triangle text-danger"></i> ${station.name}`;
            li.style.backgroundColor = "#ffe6e6";  // Couleur de fond pour les stations surchargées
        } else if (type === 'Station sous-alimentée') {
            li.innerHTML = `<i class="fas fa-bicycle text-primary"></i> ${station.name}`;
        } else {
            li.innerHTML = `<i class="fas fa-check-circle text-success"></i> ${station.name}`;
        }

        li.addEventListener('click', function () {
            if (currentRouteControl !== null) {
                map.removeLayer(currentRouteControl);
                currentRouteControl = null;
            }
            map.flyTo([station.lat, station.lon], 16);
            marker.openPopup();

            if (type === 'Station surchargée') {
                currentSurchargeLat = station.lat;
                currentSurchargeLon = station.lon;
                updateRoute(); // Mettre à jour l'itinéraire
            }
        });

        document.getElementById('stations-list').appendChild(li);
    });
}

// Fonction pour faire clignoter un marqueur sur la carte
function flashStationMarker(marker) {
    let originalIcon = marker.options.icon;
    let flashIcon = L.icon({
        iconUrl: 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png',
        iconSize: [32, 32]
    });

    let flashCount = 0;
    let interval = setInterval(() => {
        marker.setIcon(flashCount % 2 === 0 ? flashIcon : originalIcon);
        flashCount++;
        if (flashCount > 5) {
            clearInterval(interval);
            marker.setIcon(originalIcon);
        }
    }, 500);
}

// Fonction pour afficher un message lorsqu'un vélo est retiré ou ajouté
function displayStationUpdateMessage(stationName, newCount, previousCount) {
    let message = `La station "${stationName}" a été mise à jour : ${Math.abs(newCount - previousCount)} vélo(s) ${newCount > previousCount ? 'ajouté(s)' : 'retiré(s)'}.`;
    alert(message);
}

// Fonction pour afficher une animation lorsqu'un vélo est ajouté ou retiré
function displayBikeChangeAnimation(marker, bikeChange) {
    const latLng = marker.getLatLng();
    const offsetLatLng = L.latLng(latLng.lat + 0.0003, latLng.lng);  // Position légèrement au-dessus du marqueur
    const changeText = bikeChange > 0 ? `+${bikeChange}` : `${bikeChange}`;
    const color = bikeChange > 0 ? 'green' : 'red';

    // Créer un divIcon pour l'animation du changement
    const changeIcon = L.divIcon({
        className: 'bike-change-label',
        html: `<div style="color: ${color}; font-weight: bold; font-size: 16px; background-color: white; padding: 5px; border-radius: 5px; width:10px; height:10px;">${changeText}</div>`
    });

    // Ajouter le label temporaire sur la carte
    const changeMarker = L.marker(offsetLatLng, { icon: changeIcon }).addTo(map);

    // Supprimer le label après quelques secondes
    setTimeout(() => {
        if (map.hasLayer(changeMarker)) {
            map.removeLayer(changeMarker);
        }
    }, 3000);  // Durée prolongée à 3 secondes
}


// Fonction pour trouver l'itinéraire vers la station sous-alimentée la plus proche
function updateRoute() {
    let mode = document.querySelector('input[name="mode"]:checked')?.value;
    if (currentSurchargeLat && currentSurchargeLon) {
        fetch('/api/stations')
            .then(response => response.json())
            .then(data => {
                let nearestStation = null;
                let minDistance = Infinity;

                data.sous_alimentees.forEach(station => {
                    const latSousAlimentee = station.lat;
                    const lonSousAlimentee = station.lon;
                    const distance = calculateDistance(currentSurchargeLat, currentSurchargeLon, latSousAlimentee, lonSousAlimentee);

                    if (distance < minDistance) {
                        minDistance = distance;
                        nearestStation = station;
                    }
                });

                if (nearestStation) {
                    afficherItineraire(currentSurchargeLat, currentSurchargeLon, nearestStation.lat, nearestStation.lon, mode);
                }
            });
    }
}

// Fonction pour afficher l'itinéraire
function afficherItineraire(lat1, lon1, lat2, lon2, mode) {
    // Envoyer une requête à Flask pour calculer l'itinéraire en fonction du mode sélectionné
    fetch(`/api/itineraire/${lat1}/${lon1}/${lat2}/${lon2}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: mode })  // Envoie du mode de déplacement
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            console.log("Itinéraire reçu :", data.chemin);

            // Créer une polyline (ligne reliant les points de l'itinéraire)
            const routeLatLngs = data.chemin.map(coord => [coord[0], coord[1]]);
            if (currentRouteControl !== null) {
                map.removeLayer(currentRouteControl);
            }
            currentRouteControl = L.polyline(routeLatLngs, { color: 'blue' }).addTo(map);

            // Zoomer sur l'itinéraire
            map.fitBounds(currentRouteControl.getBounds());
        }
    })
    .catch(error => console.error('Erreur lors de la récupération de l\'itinéraire :', error));
}

// Fonction pour calculer la distance entre deux points
function calculateDistance(lat1, lon1, lat2, lon2) {
    var R = 6371; // Rayon de la Terre en km
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLon = (lon2 - lon1) * Math.PI / 180;
    var a = 0.5 - Math.cos(dLat) / 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * (1 - Math.cos(dLon)) / 2;
    return R * 2 * Math.asin(Math.sqrt(a));
}

document.addEventListener("DOMContentLoaded", function () {
    loadStationsAndUpdateTime();  // Charger les stations initialement

    // Ajouter l'événement "change" pour mettre à jour l'itinéraire quand on change le mode
    document.querySelectorAll('input[name="mode"]').forEach(function (input) {
        input.addEventListener('change', function () {
            updateRoute();  // Mettre à jour l'itinéraire
        });
    });

    // Recharger les stations et l'heure de mise à jour toutes les minutes
    setInterval(loadStationsAndUpdateTime, 60000);
});