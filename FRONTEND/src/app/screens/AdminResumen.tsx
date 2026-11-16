import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { API_BASE_URL } from '@/services/config';
import { apiFetch } from '../../services/apiFetch';
import { EncabezadoPagina } from '../components/Panel';
import { AvisoError, CargandoBloque } from '../components/Estados';

// SDAT-349 (6.7): pantalla de inicio del administrador

interface Resumen {
  usuarios: { activos: number; inactivos: number; por_rol: Record<string, number> };
  importaciones_recientes: {
    id: number; tipo: string; archivo: string; fecha: string; exitoso: boolean; procesados: number; errores: number;
  }[];
  procesos_recientes: {
    id: number; origen: string; estado: string; fecha: string; alertas_generadas: number; errores: number;
  }[];
}

const ROL_ROTULO: Record<string, string> = {
  ADMINISTRADOR: 'Administradores', DIRECTOR: 'Directores', DOCENTE: 'Docentes', BIENESTAR: 'Bienestar', ESTUDIANTE: 'Estudiantes',
};

export default function AdminResumen() {
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let vigente = true;
    (async () => {
      try {
        const res = await apiFetch(`${API_BASE_URL}/api/usuarios/resumen/`);
        if (!res.ok) throw new Error();
        const json = await res.json();
        if (vigente) setResumen(json);
      } catch {
        if (vigente) setError(true);
      }
    })();
    return () => { vigente = false; };
  }, []);

  return (
    <div className="space-y-5">
      <EncabezadoPagina titulo="Resumen" detalle="Estado general del sistema: usuarios, importaciones recientes y procesos automáticos." />

      {error ? (
        <AvisoError mensaje="No se pudo cargar el resumen." instruccion="Recarga la página. Si sigue fallando, intenta de nuevo en unos minutos." />
      ) : !resumen ? (
        <CargandoBloque texto="Cargando resumen…" filas={4} />
      ) : (
        <>
          <section aria-labelledby="resumen-usuarios" className="bg-white border border-line rounded-[14px] p-5 sm:p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="resumen-usuarios" className="text-base font-semibold text-ink">Usuarios</h2>
              <Link to="/dashboard/admin/users" className="text-sm font-medium text-primary-strong hover:underline">Gestionar usuarios</Link>
            </div>
            <p className="mt-2 text-sm text-ink-muted">
              <span className="text-3xl font-semibold text-ink tabular-nums mr-2">{resumen.usuarios.activos}</span>
              activos · {resumen.usuarios.inactivos} desactivados
            </p>
            <dl className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3">
              {Object.entries(resumen.usuarios.por_rol).map(([rol, total]) => (
                <div key={rol} className="rounded-[10px] bg-paper border border-line px-3 py-2">
                  <dt className="text-xs text-ink-muted">{ROL_ROTULO[rol] ?? rol}</dt>
                  <dd className="text-xl font-semibold text-ink tabular-nums">{total}</dd>
                </div>
              ))}
            </dl>
          </section>

          <div className="grid gap-5 lg:grid-cols-2">
            <section aria-labelledby="resumen-importaciones" className="bg-white border border-line rounded-[14px] overflow-hidden">
              <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 sm:px-6 py-4 border-b border-line">
                <h2 id="resumen-importaciones" className="text-base font-semibold text-ink">Importaciones recientes</h2>
                <Link to="/dashboard/admin/import" className="text-sm font-medium text-primary-strong hover:underline">Importar datos</Link>
              </div>
              {resumen.importaciones_recientes.length === 0 ? (
                <p className="px-6 py-6 text-sm text-ink-muted">Todavía no hay importaciones.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {resumen.importaciones_recientes.map((i) => (
                    <li key={i.id} className="px-5 sm:px-6 py-3 text-sm">
                      <Link to={`/dashboard/admin/import-log/${i.id}`} className="font-semibold text-ink hover:underline">{i.tipo} · {i.archivo}</Link>
                      <p className="text-xs text-ink-muted">
                        {i.fecha} · {i.exitoso ? 'Exitosa' : 'Con errores'} · {i.procesados} filas procesadas
                        {i.errores > 0 ? ` · ${i.errores} errores` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-labelledby="resumen-procesos" className="bg-white border border-line rounded-[14px] overflow-hidden">
              <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 sm:px-6 py-4 border-b border-line">
                <h2 id="resumen-procesos" className="text-base font-semibold text-ink">Procesos automáticos</h2>
                <Link to="/dashboard/admin/automatic-processes" className="text-sm font-medium text-primary-strong hover:underline">Ver procesos</Link>
              </div>
              {resumen.procesos_recientes.length === 0 ? (
                <p className="px-6 py-6 text-sm text-ink-muted">Todavía no hay ejecuciones registradas.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {resumen.procesos_recientes.map((p) => (
                    <li key={p.id} className="px-5 sm:px-6 py-3 text-sm">
                      <p className="font-semibold text-ink">Reevaluación {p.origen.toLowerCase()} · {p.estado}</p>
                      <p className="text-xs text-ink-muted">
                        {p.fecha} · {p.alertas_generadas} alertas generadas{p.errores > 0 ? ` · ${p.errores} errores` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
