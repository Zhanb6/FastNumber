import { useId, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

interface BaseProps {
  label?: string;
  error?: string;
  hint?: string;
}

type InputProps = BaseProps & InputHTMLAttributes<HTMLInputElement>;

const base =
  "w-full rounded-lg border bg-white px-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:bg-slate-100 disabled:text-slate-500";

export function Input({ label, error, hint, className = "", id, ...rest }: InputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...rest}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        className={`${base} h-10 ${error ? "border-red-400" : "border-slate-300"}`}
      />
      {error && (
        <p id={`${inputId}-error`} className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${inputId}-hint`} className="mt-1 text-sm text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}

type TextareaProps = BaseProps & TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ label, error, hint, className = "", id, ...rest }: TextareaProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        {...rest}
        aria-invalid={error ? true : undefined}
        className={`${base} min-h-20 py-2 ${error ? "border-red-400" : "border-slate-300"}`}
      />
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      {!error && hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  hint?: string;
}

export function Checkbox({ label, hint, className = "", id, ...rest }: CheckboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-800">
        <input id={inputId} type="checkbox" {...rest} className="h-4 w-4 rounded border-slate-300 accent-slate-900" />
        {label}
      </label>
      {hint && <p className="mt-1 pl-6 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}
