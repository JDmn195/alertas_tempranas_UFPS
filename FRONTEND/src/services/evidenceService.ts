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
}

export const evidenceService = {
  /**
   * Obtener lista de evidencias y detalles de la intervención
   */
  async getByIntervencion(intervencionId: number): Promise<{ evidencias: Evidencia[], intervencion: IntervencionDetalle }> {
    const res = await fetch(`${API_BASE}/intervenciones/${intervencionId}/evidencias/`);
    if (!res.ok) throw new Error('Error al obtener evidencias');
    const data = await res.json();
    return {
      evidencias: data.evidencias,
      intervencion: {
        id: data.intervencion_id,
        alerta_estado: data.alerta_estado,
        estudiante_nombre: data.estudiante_nombre,
        estudiante_codigo: data.estudiante_codigo,
        resultado: data.resultado
      }
    };
  },

  /**
   * Subir un archivo como evidencia
   */
  async upload(intervencionId: number, file: File): Promise<Evidencia> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/intervenciones/${intervencionId}/evidencias/upload/`, {
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

  /**
   * Eliminar una evidencia
   */
  async delete(evidenciaId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/evidencias/${evidenciaId}/`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error('Error al eliminar la evidencia');
  },

  /**
   * Obtener lista de anotaciones de una intervención
   */
  async getAnotaciones(intervencionId: number): Promise<Anotacion[]> {
    const res = await fetch(`${API_BASE}/intervenciones/${intervencionId}/anotaciones/`);
    if (!res.ok) throw new Error('Error al obtener anotaciones');
    const data = await res.json();
    return data.anotaciones;
  },

  /**
   * Crear una nueva anotación
   */
  async createAnotacion(intervencionId: number, usuarioId: number, texto: string): Promise<Anotacion> {
    const res = await fetch(`${API_BASE}/intervenciones/${intervencionId}/anotaciones/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario_id: usuarioId, texto })
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'Error al crear la anotación');
    }

    const data = await res.json();
    return data.anotacion;
  },

  /**
   * Eliminar una anotación
   */
  async deleteAnotacion(anotacionId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/anotaciones/${anotacionId}/`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error('Error al eliminar la observación');
  },

  /**
   * Concluir intervención
   */
  async concluirIntervencion(intervencionId: number, resultado: string): Promise<void> {
    const res = await fetch(`${API_BASE}/intervenciones/${intervencionId}/concluir/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resultado })
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'Error al concluir la intervención');
    }
  }
};

