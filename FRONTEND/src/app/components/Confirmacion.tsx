import { useState, useEffect } from 'react';
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from './ui/alert-dialog';

type Solicitud = { mensaje: string; resolver: (aceptada: boolean) => void };
let presentar: ((solicitud: Solicitud) => void) | undefined;

// SDAT-307: espera una decisión explícita sin bloquear el navegador.
export function confirmarAccion(mensaje: string): Promise<boolean> {
  return new Promise(resolver => {
    if (presentar) presentar({ mensaje, resolver });
    else resolver(false);
  });
}

export function Confirmacion() {
  const [cola, setCola] = useState<Solicitud[]>([]);
  useEffect(() => {
    presentar = solicitud => setCola(actual => [...actual, solicitud]);
    return () => { presentar = undefined; };
  }, []);
  const solicitud = cola[0];
  function resolver(aceptada: boolean) {
    solicitud?.resolver(aceptada);
    setCola(actual => actual.slice(1));
  }
  return (
    <AlertDialog open={!!solicitud} onOpenChange={abierto => { if (!abierto) resolver(false); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Confirmar acción</AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-line">{solicitud?.mensaje}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={evento => { evento.preventDefault(); resolver(false); }}>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={evento => { evento.preventDefault(); resolver(true); }}>Confirmar</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
