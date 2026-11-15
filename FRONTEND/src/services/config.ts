// SDAT-319: origen único de la API; conserva la variable y el valor local existentes.
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
