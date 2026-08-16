"use client";

import { useEffect, useRef, useState } from "react";

export interface Flash {
  /** `flash-up`, `flash-down`, or empty once the animation has decayed. */
  className: string;
  /** Increments per flash; use as a React key to restart the animation. */
  seq: number;
}

const DECAY_MS = 500;

/** Emits a directional flash class whenever `value` changes. */
export function useFlash(value: number | null | undefined): Flash {
  const previous = useRef(value);
  const [flash, setFlash] = useState<Flash>({ className: "", seq: 0 });

  useEffect(() => {
    const before = previous.current;
    previous.current = value;
    if (value == null || before == null || value === before) return;

    setFlash((f) => ({ className: value > before ? "flash-up" : "flash-down", seq: f.seq + 1 }));
    const timer = setTimeout(() => setFlash((f) => ({ ...f, className: "" })), DECAY_MS);
    return () => clearTimeout(timer);
  }, [value]);

  return flash;
}
