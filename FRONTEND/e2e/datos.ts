// Escenario que carga `manage.py preparar_e2e` (BACKEND/.../alertas/management/commands/preparar_e2e.py)

export const CONTRASENA = 'Clave-Segura-2026';

export const USUARIOS = {
  admin: { correo: 'admin@ufps.edu.co', nombre: 'Admin E2E', rol: 'ADMINISTRADOR' },
  director: { correo: 'director@ufps.edu.co', nombre: 'Directora E2E', rol: 'DIRECTOR' },
  bienestar: { correo: 'bienestar@ufps.edu.co', nombre: 'Bienestar E2E', rol: 'BIENESTAR' },
  docente: { correo: 'docente@ufps.edu.co', nombre: 'Docente Curso', rol: 'DOCENTE' },
} as const;

export type Rol = keyof typeof USUARIOS;

export const sesion = (rol: Rol) => `e2e/.auth/${rol}.json`;

export const ESTUDIANTES = {
  // Riesgo alto: alerta PROMEDIO y tres alertas de corte en Cálculo I (2026-1)
  enRiesgo: { codigo: '1152001', nombre: 'Ana Pérez' },
  // Sin notas: se le importa el historial desde la pantalla
  sinNotas: { codigo: '1152002', nombre: 'Bruno Gómez' },
  // Riesgo bajo, matriculada en Cálculo I del periodo actual
  regular: { codigo: '1152003', nombre: 'Carla Ruiz' },
} as const;
