import type { HTMLAttributes } from "react";

import { cx } from "../../utils/cx";
import styles from "./ChoiceGroup.module.css";

export type ChoiceGroupMode = "single" | "multi";
export type ChoiceGroupLayout = "chips" | "rows" | "segmented";
export type ChoiceOptionTone = "neutral" | "primary" | "danger";

export type ChoiceOption = {
  value: string;
  label: string;
  description?: string | null;
  disabled?: boolean;
  recommended?: boolean;
  tone?: ChoiceOptionTone;
};

export type ChoiceGroupProps = Omit<
  HTMLAttributes<HTMLFieldSetElement>,
  "onChange"
> & {
  description?: string;
  disabled?: boolean;
  error?: string | null;
  label?: string;
  layout?: ChoiceGroupLayout;
  loading?: boolean;
  mode?: ChoiceGroupMode;
  onChange: (selectedValues: string[]) => void;
  options: ChoiceOption[];
  selectedValues: string[];
};

export function ChoiceGroup({
  className,
  description,
  disabled = false,
  error,
  label,
  layout = "chips",
  loading = false,
  mode = "single",
  onChange,
  options,
  selectedValues,
  ...props
}: ChoiceGroupProps) {
  const selected = new Set(selectedValues);
  const groupDisabled = disabled || loading;

  return (
    <fieldset
      aria-busy={loading || undefined}
      className={cx(styles.root, className)}
      disabled={groupDisabled}
      {...props}
    >
      {label && <legend className={styles.legend}>{label}</legend>}
      {description && <p className={styles.description}>{description}</p>}
      <div className={cx(styles.options, styles[layout])}>
        {options.map((option) => {
          const isSelected = selected.has(option.value);
          const optionDisabled = groupDisabled || option.disabled === true;

          return (
            <button
              aria-pressed={isSelected}
              className={cx(
                styles.option,
                styles[option.tone ?? "neutral"],
                isSelected && styles.selected,
                option.recommended && styles.recommended,
              )}
              disabled={optionDisabled}
              key={option.value}
              onClick={() =>
                onChange(
                  nextSelectedValues({
                    mode,
                    optionValue: option.value,
                    selectedValues,
                  }),
                )
              }
              type="button"
            >
              <span className={styles.optionLabel}>{option.label}</span>
              {option.description && (
                <span className={styles.optionDescription}>
                  {option.description}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}

function nextSelectedValues({
  mode,
  optionValue,
  selectedValues,
}: {
  mode: ChoiceGroupMode;
  optionValue: string;
  selectedValues: string[];
}): string[] {
  if (mode === "single") {
    return selectedValues.includes(optionValue) ? [] : [optionValue];
  }

  if (selectedValues.includes(optionValue)) {
    return selectedValues.filter((value) => value !== optionValue);
  }

  return [...selectedValues, optionValue];
}
