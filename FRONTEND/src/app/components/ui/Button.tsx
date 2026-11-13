type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
};

export function Button({
  variant = 'primary',
  size = 'md',
  children,
  onClick,
  type = 'button',
  disabled = false,
  fullWidth = false,
  className = '',
  ...rest
}: ButtonProps) {
  const variants = {
    primary: 'bg-primary text-white hover:bg-primary-strong border-primary hover:border-primary-strong',
    secondary: 'bg-wash text-ink hover:bg-line border-transparent',
    outline: 'bg-white text-ink hover:bg-paper border-line-strong hover:border-ink-faint',
    ghost: 'bg-transparent text-ink-soft hover:bg-wash hover:text-ink border-transparent',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-[10px] border font-semibold transition-colors ${variants[variant]} ${sizes[size]} ${
        fullWidth ? 'w-full' : ''
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
