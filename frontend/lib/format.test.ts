import { describe, it, expect } from "vitest";
import { formatCurrency } from "@/lib/format";

describe("formatCurrency", () => {
  it("formats a bare numeric value with thousands separators and two decimals", () => {
    expect(formatCurrency(10000)).toBe("10,000.00");
  });
});
