import type { InputHTMLAttributes } from "react";

type AmountInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
};

/**
 * A money field in whole units, shown with comma separators as the user types
 * ("4,000,000"). Anything that is not a digit is dropped, so there are no decimals.
 */
export function AmountInput({ value, onChange, ...rest }: AmountInputProps) {
  return (
    <input
      {...rest}
      inputMode="numeric"
      value={value === undefined || Number.isNaN(value) ? "" : value.toLocaleString("en-US")}
      onChange={(event) => {
        // Cents are cut off rather than merged, so "4000000.75" stays 4,000,000.
        const digits = event.target.value.split(".")[0].replace(/\D/g, "");
        onChange(digits === "" ? undefined : Number(digits));
      }}
    />
  );
}
