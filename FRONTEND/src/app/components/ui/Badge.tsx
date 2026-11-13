type BadgeProps = {
  variant: 'low' | 'medium' | 'high' | 'success' | 'error' | 'gray';
  children: React.ReactNode;
  size?: 'xs' | 'sm' | 'md';
  className?: string;
};

/**
 * Etiqueta de estado. Cada variante lleva un punto del color del nivel, así el
 * nivel no depende solo del color de fondo.
 */
export function Badge({ variant, children, size = 'md', className = '' }: BadgeProps) {
  const variants = {
    low: 'bg-green-50 text-green-800 border-green-200',
    medium: 'bg-amber-50 text-amber-800 border-amber-200',
    high: 'bg-red-50 text-red-800 border-red-200',
    success: 'bg-green-50 text-green-800 border-green-200',
    error: 'bg-red-50 text-red-800 border-red-200',
    gray: 'bg-wash text-ink-soft border-line',
  };
  const puntos = {
    low: 'bg-riesgo-bajo',
    medium: 'bg-riesgo-medio',
    high: 'bg-riesgo-critico',
    success: 'bg-riesgo-bajo',
    error: 'bg-riesgo-critico',
    gray: 'bg-ink-faint',
  };

  const sizes = {
    xs: 'px-1.5 py-0.5 text-xs gap-1',
    sm: 'px-2 py-0.5 text-xs gap-1.5',
    md: 'px-2.5 py-1 text-sm gap-1.5',
  };

  return (
    <span className={`inline-flex items-center rounded-md border ${variants[variant]} ${sizes[size]} font-medium ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${puntos[variant]}`} aria-hidden="true" />
      {children}
    </span>
  );
}
