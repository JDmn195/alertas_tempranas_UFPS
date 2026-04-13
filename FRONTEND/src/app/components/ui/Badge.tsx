type BadgeProps = {
  variant: 'low' | 'medium' | 'high' | 'success' | 'error' | 'gray';
  children: React.ReactNode;
  size?: 'sm' | 'md';
};

export function Badge({ variant, children, size = 'md' }: BadgeProps) {
  const variants = {
    low: 'bg-gray-100 text-gray-700 border-gray-300',
    medium: 'bg-amber-100 text-amber-700 border-amber-300',
    high: 'bg-[#C8102E] text-white border-[#C8102E]',
    success: 'bg-green-100 text-green-700 border-green-300',
    error: 'bg-red-100 text-red-700 border-red-300',
    gray: 'bg-gray-100 text-gray-600 border-gray-300',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border ${variants[variant]} ${sizes[size]} font-medium`}
    >
      {children}
    </span>
  );
}
