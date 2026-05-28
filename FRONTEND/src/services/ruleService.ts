import { apiFetch } from './apiFetch';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

export interface Rule {
  id?: number;
  nombre: string;
  tipo: 'PROMEDIO' | 'REPROBACION' | 'ATRASO';
  tipo_display?: string;
  valor_umbral: number;
  operador: '<' | '>' | '<=' | '>=' | '==';
  nivel: 'high' | 'medium' | 'low';
  activo: boolean;
  descripcion: string;
}

export const ruleService = {
  getRules: async () => {
    const response = await apiFetch(`${API_URL}/alertas/reglas/`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Error al obtener las reglas');
    }
    return response.json();
  },

  // El usuario_id ya no es necesario: el backend lo obtiene del JWT
  createRule: async (rule: Rule) => {
    const response = await apiFetch(`${API_URL}/alertas/reglas/`, {
      method: 'POST',
      body: JSON.stringify(rule),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Error al crear la regla');
    }
    return response.json();
  },

  updateRule: async (id: number, rule: Partial<Rule>) => {
    const response = await apiFetch(`${API_URL}/alertas/reglas/${id}/`, {
      method: 'PUT',
      body: JSON.stringify(rule),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Error al actualizar la regla');
    }
    return response.json();
  },

  deleteRule: async (id: number) => {
    const response = await apiFetch(`${API_URL}/alertas/reglas/${id}/`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Error al eliminar la regla');
    }
    return response.json();
  },
};
