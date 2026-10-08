import { RouterProvider } from 'react-router';
import { Toaster } from 'sonner';
import { router } from './routes';

export default function App() {
  return (
    <>
      <RouterProvider router={router} />
      {/* Avisos de toast() (p. ej. al guardar la asistencia) */}
      <Toaster richColors position="top-right" />
    </>
  );
}
