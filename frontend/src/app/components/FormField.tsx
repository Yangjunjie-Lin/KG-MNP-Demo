import { useId } from "react";
import { cn } from "../utils/cn";

export function FormField({
  label,
  placeholder,
  required,
  mono,
  type,
  options,
  value,
  onChange,
  optional,
}: {
  label: string;
  placeholder?: string;
  required?: boolean;
  mono?: boolean;
  type?: "text" | "datetime" | "date" | "select" | "number";
  options?: Array<{ value: string; label: string } | string>;
  value?: string;
  onChange?: (value: string) => void;
  optional?: boolean;
}) {
  const id = useId();
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-[10px] font-semibold text-slate-500 tracking-wide mb-1">
        {label}
        {required && <span aria-hidden="true" className="text-red-500 ml-0.5">*</span>}
      </label>
      {type === "select" ? (
        <select
          id={id}
          className="w-full text-xs border border-slate-200 rounded px-2.5 py-1.5 bg-white text-slate-700 outline-none focus:border-blue-400"
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          required={required && !optional}
        >
          {options?.map((o) => {
            const opt = typeof o === "string" ? { value: o, label: o } : o;
            return (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            );
          })}
        </select>
      ) : (
        <input
          id={id}
          type={
            type === "datetime"
              ? "datetime-local"
              : type === "date"
                ? "date"
                : type === "number"
                  ? "number"
                  : "text"
          }
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          step={type === "datetime" ? 1 : undefined}
          required={required && !optional}
          className={cn(
            "w-full text-xs border border-slate-200 rounded px-2.5 py-1.5 bg-white text-slate-700 outline-none focus:border-blue-400",
            mono && "font-mono",
          )}
        />
      )}
    </div>
  );
}
