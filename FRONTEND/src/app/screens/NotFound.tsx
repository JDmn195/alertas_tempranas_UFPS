import { Link } from "react-router";

export default function NotFound() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 p-6 text-center bg-white">
      <p className="text-sm font-semibold text-slate-500">Error 404</p>
      <h1 className="text-2xl font-bold text-slate-900">Página no encontrada</h1>
      <p className="max-w-md text-slate-600">
        La dirección que escribió no existe o fue movida. Vuelva al inicio para continuar.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Ir al inicio
      </Link>
    </main>
  );
}
