import { Link } from "react-router";

export default function NotFound() {
  return (
    <main className="min-h-screen grid place-items-center p-6 bg-paper">
      <div className="w-full max-w-md text-center bg-white rounded-[14px] border border-line p-10 animate-in fade-in zoom-in-95 duration-200">
        <img src="/logo-ufps.svg" alt="Universidad Francisco de Paula Santander" className="h-20 w-auto mx-auto mb-6" />
        <p className="text-sm font-semibold text-primary">Error 404</p>
        <h1 className="mt-1 text-3xl font-semibold text-ink">Página no encontrada</h1>
        <p className="mt-3 text-ink-muted">
          La dirección que escribió no existe o fue movida. Vuelva al inicio para continuar.
        </p>
        <Link
          to="/"
          className="mt-7 inline-flex rounded-[10px] bg-primary px-5 py-2.5 text-sm font-semibold text-white transition-all hover:bg-primary-strong"
        >
          Ir al inicio
        </Link>
      </div>
    </main>
  );
}
