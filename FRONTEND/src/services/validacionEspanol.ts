// SDAT-346: mensajes de validación nativa del navegador en español (el navegador usa su propio idioma).
type Campo = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

function mensaje(campo: Campo): string {
  const v = campo.validity;
  const el = campo as HTMLInputElement;
  const tipo = el.type;
  if (v.valueMissing) {
    if (tipo === 'checkbox') return 'Marca esta casilla para continuar.';
    if (campo.tagName === 'SELECT' || tipo === 'radio') return 'Selecciona una opción.';
    if (tipo === 'file') return 'Selecciona un archivo.';
    return 'Completa este campo.';
  }
  if (v.typeMismatch) {
    if (tipo === 'email') return 'Escribe un correo electrónico válido.';
    if (tipo === 'url') return 'Escribe una dirección web válida.';
    return 'El valor no tiene el formato esperado.';
  }
  if (v.rangeUnderflow) return `El valor debe ser mayor o igual que ${el.min}.`;
  if (v.rangeOverflow) return `El valor debe ser menor o igual que ${el.max}.`;
  if (v.stepMismatch) return 'Escribe un valor válido.';
  if (v.badInput) return 'Escribe un número válido.';
  if (v.tooShort) return `Escribe al menos ${el.minLength} caracteres.`;
  if (v.tooLong) return `Escribe como máximo ${el.maxLength} caracteres.`;
  if (v.patternMismatch) return 'El valor no tiene el formato esperado.';
  return '';
}

export function instalarValidacionEnEspanol() {
  document.addEventListener('invalid', (evento) => {
    const campo = evento.target as Campo;
    if (!campo || typeof campo.setCustomValidity !== 'function') return;
    campo.setCustomValidity('');
    campo.setCustomValidity(mensaje(campo));
  }, true);
  const limpiar = (evento: Event) => {
    const campo = evento.target as Campo;
    if (campo && typeof campo.setCustomValidity === 'function') campo.setCustomValidity('');
  };
  document.addEventListener('input', limpiar, true);
  document.addEventListener('change', limpiar, true);
}
