import { RouterProvider } from 'react-router';
import { Toaster } from 'sonner';
import { router } from './routes';
import { Confirmacion } from './components/Confirmacion';

export default function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Confirmacion />
      {/* Avisos de toast() (p. ej. al guardar la asistencia) */}
      <Toaster richColors position="top-right" />
    </>
  );
}
