import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCell } from "@/components/PriceCell";

describe("PriceCell flash", () => {
  it("renders a placeholder and no flash before any price arrives", () => {
    render(<PriceCell value={null} />);
    const cell = screen.getByTestId("price-cell");

    expect(cell).toHaveTextContent("—");
    expect(cell.className).not.toMatch(/flash-/);
  });

  it("flashes up on an uptick", () => {
    const { rerender } = render(<PriceCell value={100} />);
    rerender(<PriceCell value={101.5} />);

    const cell = screen.getByTestId("price-cell");
    expect(cell).toHaveTextContent("101.50");
    expect(cell.className).toContain("flash-up");
  });

  it("flashes down on a downtick", () => {
    const { rerender } = render(<PriceCell value={100} />);
    rerender(<PriceCell value={99} />);

    expect(screen.getByTestId("price-cell").className).toContain("flash-down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell value={100} />);
    rerender(<PriceCell value={100} />);

    expect(screen.getByTestId("price-cell").className).not.toMatch(/flash-/);
  });
});
