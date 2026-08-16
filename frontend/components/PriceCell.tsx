"use client";

import { useFlash } from "@/hooks/useFlash";
import { price as formatPrice } from "@/lib/format";

interface PriceCellProps {
  value: number | null;
  className?: string;
}

/** Price readout that flashes green on an uptick and red on a downtick. */
export function PriceCell({ value, className = "" }: PriceCellProps) {
  const flash = useFlash(value);

  return (
    <span
      key={flash.seq}
      data-testid="price-cell"
      className={`num inline-block rounded-xs px-1 tabular-nums ${flash.className} ${className}`}
    >
      {value == null ? "—" : formatPrice(value)}
    </span>
  );
}
