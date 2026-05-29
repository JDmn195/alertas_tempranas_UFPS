import { apiFetch } from './apiFetch';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/alertas';

export interface Evidencia {
  id: number;
  url: string;
  nombre: string;
  tipo: string;
  fecha: string;
}

export interface Anotacion {
  id: number;
  texto: string;
  fecha: string;
  usuario: string;
  usuario_rol: string;
}

export interface IntervencionDetalle {
  id: number;
  alerta_estado: string;
  estudiante_nombre: string;
  estudiante_codigo: string;
  resultado: string | null;
  concluida: boolean;
}

export const evidenceService = {
  async getByIntervencion(intervencionId: number): Promise<{ evidencias: Evidencia[], intervencion: IntervencionDetalle }> {
    const res = await apiFetch(`${API_BASE}/intervenciones/${intervencionId}/evidencias/`);
    if (!res.ok) throw new Error('Error al obtener evidencias');
    const data = await res.json();
    return {
      evidencias: data.evidencias,
      intervencion: {
        id: data.intervencion_id,
        alerta_estado: data.alerta_estado,
        estudiante_nombre: data.estudiante_nombre,
        estudiante_codigo: data.estudiante_codigo,
        resultado: data.resultado,
        concluida: data.concluida ?? false,
      }
    };
  },

  async upload(intervencionId: number, file: File): Promise<Evidencia> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiFetch(`${API_BASE}/intervenciones/${intervencionId}/evidencias/upload/`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'Error al subir el archivo');
    }
    const data = await res.json();
    return data.evidencia;
  },

  async delete(evidenciaId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/evidencias/${evidenciaId}/`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al eliminar la evidencia');
  },

  async getAnotaciones(intervencionId: number): Promise<Anotacion[]> {
    const res = await apiFetch(`${API_BASE}/intervenciones/${intervencionId}/anotaciones/`);
    if (!res.ok) throw new Error('Error al obtener anotaciones');
    const data = await res.json();
    return data.anotaciones;
  },

  // usuario_id ya no es necesario: el backend lo extrae del JWT
  async createAnotacion(intervencionId: number, texto: string): Promise<Anotacion> {
    const res = await apiFetch(`${API_BASE}/intervenciones/${intervencionId}/anotaciones/`, {
      method: 'POST',
      body: JSON.stringify({ texto })
    });
    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'Error al crear la anotación');
    }
    const data = await res.json();
    return data.anotacion;
  },

  async deleteAnotacion(anotacionId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/anotaciones/${anotacionId}/`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al eliminar la observación');
  },

  async concluirIntervencion(intervencionId: number, resultado: string): Promise<void> {
    const res = await apiFetch(`${API_BASE}/intervenciones/${intervencionId}/concluir/`, {
      method: 'POST',
      body: JSON.stringify({ resultado })
    });
    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'Error al concluir la intervención');
    }
  }
};
