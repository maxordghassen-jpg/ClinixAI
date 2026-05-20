import React, { useState, useEffect } from 'react';
import { MapPin, Search, Star, Phone, Navigation, Clock } from 'lucide-react';

export default function ProximitySearch() {
  const [userLocation, setUserLocation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('doctors');
  const [radius, setRadius] = useState(5);
  const [error, setError] = useState('');

  // Obtenir la position de l'utilisateur
  const getUserLocation = () => {
    setLoading(true);
    setError('');

    if (!navigator.geolocation) {
      setError('La géolocalisation n\'est pas supportée par votre navigateur');
      setLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        };
        setUserLocation(location);
        searchNearby(location);
      },
      (error) => {
        setError('Impossible d\'obtenir votre position. Veuillez autoriser la géolocalisation.');
        setLoading(false);
      }
    );
  };

  // Rechercher les établissements à proximité
  const searchNearby = async (location) => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5000/api/nearby', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          latitude: location.latitude,
          longitude: location.longitude,
          category: selectedCategory,
          radius: radius,
          limit: 20
        })
      });

      const data = await response.json();
      
      if (data.success) {
        setResults(data.results);
      } else {
        setError('Erreur lors de la recherche');
      }
    } catch (err) {
      setError('Erreur de connexion au serveur');
    } finally {
      setLoading(false);
    }
  };

  // Charger la position au démarrage
  useEffect(() => {
    getUserLocation();
  }, []);

  // Rechercher quand la catégorie ou le rayon change
  useEffect(() => {
    if (userLocation) {
      searchNearby(userLocation);
    }
  }, [selectedCategory, radius]);

  const categories = [
    { id: 'doctors', name: 'Médecins', icon: '👨‍⚕️' },
    { id: 'pharmacies', name: 'Pharmacies', icon: '💊' },
    { id: 'clinics', name: 'Cliniques', icon: '🏥' },
    { id: 'analysis_labs', name: 'Laboratoires', icon: '🔬' },
    { id: 'physiotherapists', name: 'Kinés', icon: '💆' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-2 flex items-center gap-3">
            <MapPin className="text-blue-600" size={32} />
            Établissements Médicaux à Proximité
          </h1>
          <p className="text-gray-600">
            {userLocation 
              ? `📍 Position : ${userLocation.latitude.toFixed(4)}, ${userLocation.longitude.toFixed(4)}`
              : 'Localisation en cours...'}
          </p>
        </div>

        {/* Contrôles */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          {/* Catégories */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Catégorie
            </label>
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${
                    selectedCategory === cat.id
                      ? 'bg-blue-600 text-white shadow-lg scale-105'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {cat.icon} {cat.name}
                </button>
              ))}
            </div>
          </div>

          {/* Rayon de recherche */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Rayon de recherche : {radius} km
            </label>
            <input
              type="range"
              min="1"
              max="20"
              value={radius}
              onChange={(e) => setRadius(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1 km</span>
              <span>20 km</span>
            </div>
          </div>

          {/* Bouton Actualiser */}
          <button
            onClick={getUserLocation}
            disabled={loading}
            className="mt-4 w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 flex items-center justify-center gap-2 transition-all"
          >
            <Navigation size={20} />
            {loading ? 'Recherche en cours...' : 'Actualiser ma position'}
          </button>
        </div>

        {/* Erreur */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Résultats */}
        <div className="space-y-4">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
              <p className="mt-4 text-gray-600">Recherche en cours...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
              <Search size={48} className="mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600 text-lg">
                Aucun établissement trouvé dans un rayon de {radius} km
              </p>
              <p className="text-gray-500 text-sm mt-2">
                Essayez d'augmenter le rayon de recherche
              </p>
            </div>
          ) : (
            <>
              <div className="text-center text-gray-600 font-medium mb-4">
                {results.length} établissement{results.length > 1 ? 's' : ''} trouvé{results.length > 1 ? 's' : ''}
              </div>
              
              {results.map((place, index) => (
                <div
                  key={place.id || index}
                  className="bg-white rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden"
                >
                  <div className="p-6">
                    {/* En-tête */}
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex-1">
                        <h3 className="text-xl font-bold text-gray-800 mb-1">
                          {place.name}
                        </h3>
                        {place.specialty && (
                          <span className="inline-block bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm font-medium">
                            {place.specialty}
                          </span>
                        )}
                      </div>
                      <div className="bg-blue-600 text-white px-4 py-2 rounded-lg font-bold text-lg shadow-lg">
                        {place.distance_text}
                      </div>
                    </div>

                    {/* Informations */}
                    <div className="space-y-3">
                      <div className="flex items-start gap-2 text-gray-600">
                        <MapPin size={18} className="mt-1 flex-shrink-0 text-red-500" />
                        <span>{place.address}</span>
                      </div>

                      {place.phone_number && (
                        <div className="flex items-center gap-2 text-gray-600">
                          <Phone size={18} className="text-green-500" />
                          <a href={`tel:${place.phone_number}`} className="hover:text-blue-600 font-medium">
                            {place.phone_number}
                          </a>
                        </div>
                      )}

                      {place.rating && (
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1">
                            <Star size={18} className="text-yellow-400 fill-yellow-400" />
                            <span className="font-semibold">{place.rating}</span>
                          </div>
                          {place.is_open_now !== null && (
                            <span className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${
                              place.is_open_now 
                                ? 'bg-green-100 text-green-700' 
                                : 'bg-red-100 text-red-700'
                            }`}>
                              <Clock size={14} />
                              {place.is_open_now ? 'Ouvert' : 'Fermé'}
                            </span>
                          )}
                        </div>
                      )}

                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <span className="bg-gray-100 px-2 py-1 rounded">
                          {place.governorate}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3 mt-4">
                      {place.google_maps_url && (
                        <a
                          href={place.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 bg-blue-600 text-white py-2 rounded-lg font-medium hover:bg-blue-700 text-center transition-all"
                        >
                          Voir sur Maps
                        </a>
                      )}
                      {place.phone_number && (
                        <a
                          href={`tel:${place.phone_number}`}
                          className="flex-1 bg-green-600 text-white py-2 rounded-lg font-medium hover:bg-green-700 text-center transition-all"
                        >
                          Appeler
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}