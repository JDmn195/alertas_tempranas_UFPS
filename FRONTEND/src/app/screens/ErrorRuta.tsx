import { isRouteErrorResponse, Link, useRouteError } from "react-router";

export default function ErrorRuta() {
  const error = useRouteError();
  const noEncontrada = isRouteErrorResponse(error) && error.status === 404;

  return (
    <main className="min-h-screen grid place-items-center p-6 bg-paper">
      <div className="w-full max-w-md text-center bg-white rounded-[14px] border border-line p-10">
        <img src="/logo-ufps.svg" alt="Universidad Francisco de Paula Santander" className="h-20 w-auto mx-auto mb-6" />
        <p className="text-sm font-semibold text-primary">{noEncontrada ? "Error 404" : "Ocurrió un error"}</p>
        <h1 className="mt-1 text-3xl font-semibold text-ink">
          {noEncontrada ? "Página no encontrada" : "No pudimos mostrar esta página"}
        </h1>
        <p className="mt-3 text-ink-muted">
          {noEncontrada
            ? "La dirección que escribió no existe o fue movida."
            : "Intente cargarla de nuevo. Si el problema continúa, vuelva al inicio."}
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          {!noEncontrada && (
            <button type="button" onClick={() => window.location.reload()} className="rounded-[10px] border border-line px-5 py-2.5 text-sm font-semibold text-ink">
              Reintentar
            </button>
          )}
          <Link to="/" className="inline-flex rounded-[10px] bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-strong">
            Ir al inicio
          </Link>
        </div>
      </div>
    </main>
  );
}
