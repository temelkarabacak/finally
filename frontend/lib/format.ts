// Shared number-formatting helpers for currency values rendered in the UI.

const CURRENCY_FORMATTER = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Formats a bare numeric value with thousands separators and two decimal
 * places, e.g. `10000` -> `"10,000.00"`. Locale is pinned to `en-US` so the
 * output is identical regardless of the viewer's browser language. Does not
 * prepend a currency symbol.
 */
export function formatCurrency(value: number): string {
  return CURRENCY_FORMATTER.format(value);
}
