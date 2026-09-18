import { useId, type SelectHTMLAttributes } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
}

export function Select({ label, options, error, className = "", id, ...rest }: Props) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={selectId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <select
        id={selectId}
        {...rest}
        aria-invalid={error ? true : undefined}
        className={`h-10 w-full rounded-lg border bg-white px-3 text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:bg-slate-100 ${
          error ? "border-red-400" : "border-slate-300"
        }`}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
