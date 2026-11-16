import { useEffect, useState } from 'react';
import { formatearFechaHora } from '@/utils/formato';
import { Link } from 'react-router';
import { API_BASE_URL } from '@/services/config';
import { apiFetch } from '../../services/apiFetch';
import { sesionVerificada } from '../../services/session';

type Ejecucion = { estado: string; fecha_inicio: string };

const nombres: Record<string, string> = {
  ADMINISTRADOR: 'Administración', DIRECTOR: 'Dirección', DOCENTE: 'Docencia',
  BIENESTAR: 'Bienestar Universitario', ESTUDIANTE: 'Estudiantes',
};

export default function Ayuda() {
  const sesion = sesionVerificada();
  const rol = sesion?.estado === 'ok' ? sesion.usuario.rol.split(',')[0] : '';
  const estudiante = rol === 'ESTUDIANTE';
  const veProcesos = rol === 'ADMINISTRADOR' || rol === 'DIRECTOR';
  const [ultima, setUltima] = useState<Ejecucion | null>(null);
  const [estadoConsulta, setEstadoConsulta] = useState<'cargando' | 'lista' | 'error'>('cargando');

  useEffect(() => {
    if (!veProcesos) return;
    let activa = true;
    apiFetch(`${API_BASE_URL}/api/alertas/reevaluacion/ejecuciones/?limite=1`)
      .then(async respuesta => {
        if (!respuesta.ok) throw new Error('No se pudo consultar la última ejecución.');
        return respuesta.json();
      })
      .then(datos => { if (activa) { setUltima(datos.ejecuciones?.[0] ?? null); setEstadoConsulta('lista'); } })
      .catch(() => { if (activa) setEstadoConsulta('error'); });
    return () => { activa = false; };
  }, [veProcesos]);

  const enlaces = estudiante
    ? [['Mis alertas', '/dashboard/portal/alertas'], ['Mi asistencia', '/dashboard/portal/asistencia'], ['Mi acompañamiento', '/dashboard/portal/acompanamiento']]
    : rol === 'DOCENTE'
      ? [['Mis cursos', '/dashboard/courses'], ['Gestión de alertas', '/dashboard/alerts']]
      : rol === 'BIENESTAR'
        ? [['Gestión de alertas', '/dashboard/alerts'], ['Solicitudes', '/dashboard/solicitudes']]
        : rol === 'DIRECTOR'
          ? [['Panel estratégico', '/dashboard/director'], ['Procesos automáticos', '/dashboard/admin/automatic-processes']]
          : [['Importar datos', '/dashboard/admin/import'], ['Reglas de riesgo', '/dashboard/admin/risk-rules'], ['Procesos automáticos', '/dashboard/admin/automatic-processes']];

  return (
    <div className="mx-auto max-w-4xl space-y-6 text-gray-800">
      <header>
        <p className="text-sm font-semibold text-[#9B0C24]">Guía del SAT · {nombres[rol] || 'Ayuda'}</p>
        <h1 className="mt-1 text-3xl font-bold">¿Cómo funciona?</h1>
        <p className="mt-2 text-gray-600">Consulta el significado de los indicadores y las acciones disponibles para tu rol.</p>
      </header>

      <nav aria-label="Accesos relacionados" className="flex flex-wrap gap-2">
        {enlaces.map(([texto, ruta]) => <Link key={ruta} to={ruta} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-[#9B0C24] hover:bg-red-50">{texto}</Link>)}
      </nav>

      <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-3" aria-labelledby="riesgo-ayuda">
        <h2 id="riesgo-ayuda" className="text-xl font-semibold">Niveles de riesgo</h2>
        <p>El nivel bajo, medio o alto resume factores académicos como promedio, materias perdidas, atraso y faltas sin justificar. Las alertas por notas de corte avisan sobre una materia, pero no cambian por sí solas el nivel de riesgo general.</p>
        {estudiante && <p>En tu portal solo ves tus propios datos académicos, alertas y acompañamiento. Las anotaciones internas del personal no aparecen allí.</p>}
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-3" aria-labelledby="asistencia-ayuda">
        <h2 id="asistencia-ayuda" className="text-xl font-semibold">Asistencia</h2>
        <p>Porcentaje de inasistencia = faltas sin justificar ÷ clases registradas × 100. Una falta justificada cuenta como clase, pero no como falta.</p>
        <p>El umbral general es 20 % y se evalúa desde 4 clases por defecto. Un curso puede tener un umbral propio; si existe, prevalece sobre el general.</p>
      </section>

      {!estudiante && <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-3" aria-labelledby="notas-ayuda">
        <h2 id="notas-ayuda" className="text-xl font-semibold">Notas y alertas de corte</h2>
        <p>Definitiva = promedio de los tres cortes × 0,7 + examen final × 0,3. Solo se calcula cuando existen las cuatro notas. Se aprueba desde 3,0.</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>C1: primer corte menor que 2,0.</li>
          <li>C2A: segundo corte menor que 3,0 y primero menor que 3,0.</li>
          <li>C2B: segundo corte menor que 3,0 y primero de 3,0 o más.</li>
          <li>C3: con tres cortes, necesita más de 4,0 en el examen para aprobar.</li>
          <li>C4: con tres cortes, necesitaría más de 5,0; tiene prioridad sobre C3.</li>
        </ul>
        <p>Nota necesaria en el examen = (3,0 − promedio de cortes × 0,7) ÷ 0,3.</p>
      </section>}

      {veProcesos && <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-3" aria-labelledby="procesos-ayuda">
        <h2 id="procesos-ayuda" className="text-xl font-semibold">Procesos automáticos</h2>
        <p>La revaluación programada se solicita cada día a las 2:00 a. m. de Colombia. Los recordatorios se solicitan cada 6 horas (1:00 a. m., 7:00 a. m., 1:00 p. m. y 7:00 p. m. de Colombia). GitHub puede demorar el inicio de cada ejecución; las horas del historial son las reales. Su envío depende de la configuración y de los casos pendientes.</p>
        <p role="status">
          {estadoConsulta === 'cargando' ? 'Consultando última revaluación…' : estadoConsulta === 'error'
            ? 'No se pudo consultar la última revaluación.'
            : ultima ? `Última revaluación: ${formatearFechaHora(ultima.fecha_inicio)} · ${ultima.estado}.`
              : 'Todavía no hay revaluaciones registradas.'}
        </p>
      </section>}

      <footer className="pb-6 text-sm text-gray-600">Revisión de esta interfaz: {__REVISION_INTERFAZ__}. Esta revisión identifica la compilación actual; no certifica por sí sola el despliegue del backend.</footer>
    </div>
  );
}
