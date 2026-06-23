import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { CheckCircle2, XCircle } from "lucide-react";

export interface FieldValidation {
  ok: boolean;
  message: string;
}

interface ValidatedHostInputProps {
  id: string;
  label: string;
  optional?: boolean;
  fromEnvNote?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
  validation: FieldValidation | null;
  helperText?: string;
}

export function ValidatedHostInput({
  id,
  label,
  optional,
  fromEnvNote,
  value,
  onChange,
  placeholder,
  disabled,
  validation,
  helperText,
}: ValidatedHostInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {label}
        {optional && (
          <>
            {" "}
            <span className="font-normal text-muted-foreground">
              (optional)
            </span>
          </>
        )}
      </Label>
      {fromEnvNote && (
        <p className="text-xs text-muted-foreground">{fromEnvNote}</p>
      )}
      <div className="relative">
        <Input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className={validation ? "pr-8" : ""}
        />
        {validation && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
            {validation.ok ? (
              <CheckCircle2
                className="h-4 w-4 text-green-500"
                aria-label={validation.message}
              />
            ) : (
              <XCircle
                className="h-4 w-4 text-destructive"
                aria-label={validation.message}
              />
            )}
          </span>
        )}
      </div>
      <p
        className={`text-xs min-h-[1rem] ${validation && !validation.ok ? "text-destructive" : "text-muted-foreground"}`}
      >
        {validation && !validation.ok ? validation.message : helperText}
      </p>
    </div>
  );
}
