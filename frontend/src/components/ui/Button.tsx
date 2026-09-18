import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary: "bg-slate-900 text-white hover:bg-slate-700 disabled:bg-slate-400",
  secondary: "bg-white text-slate-800 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400",
  danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300",
  ghost: "bg-transparent text-slate-700 hover:bg-slate-100 disabled:text-slate-400",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export function Button({ variant = "primary", size = "md", loading = false, className = "", disabled, children, ...rest }: Props) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
