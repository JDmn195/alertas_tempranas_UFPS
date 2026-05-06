type ButtonProps = {
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  disabled?: boolean;
  fullWidth?: boolean;
  className?: string;
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
}: ButtonProps) {
  const variants = {
    primary: 'bg-[#C8102E] text-white hover:bg-[#A00D25] border-transparent',
    secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200 border-gray-300',
    outline: 'bg-white text-[#C8102E] hover:bg-red-50 border-[#C8102E]',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md border font-medium transition-colors ${variants[variant]} ${sizes[size]} ${
        fullWidth ? 'w-full' : ''
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </button>
  );
}
