"use client";

const DEFAULT_WIDTH = 64;
const DEFAULT_HEIGHT = 20;
const DEFAULT_BUFFER_CAPACITY = 120;

type SparklineProps = {
  points: number[];
  width?: number;
  height?: number;
  bufferCapacity?: number;
  className?: string;
};

/**
 * Inline SVG polyline sparkline -- no charting library (01-CONTEXT.md decision:
 * a full charting instance per watchlist row is real overhead for a decorative
 * line). The series is only what this client has observed since page load, so
 * the drawn line is scaled to the fill fraction of the capped history buffer
 * rather than always spanning the full box: a short series reads as short
 * history, never as a complete picture.
 */
export function Sparkline({
  points,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  bufferCapacity = DEFAULT_BUFFER_CAPACITY,
  className,
}: SparklineProps) {
  if (points.length === 0) {
    // No data observed yet must never render as a flat line -- that would
    // suggest a calm market when the truth is "nothing seen since page load".
    return null;
  }

  const title = `${points.length} observation${points.length === 1 ? "" : "s"} since page load`;

  if (points.length === 1) {
    const y = height / 2;
    const markWidth = Math.min(6, width);
    const x1 = (width - markWidth) / 2;
    const x2 = x1 + markWidth;
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        aria-hidden="true"
        className={className}
      >
        <title>{title}</title>
        <line
          x1={x1}
          y1={y}
          x2={x2}
          y2={y}
          stroke="var(--color-terminal-muted)"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min;

  // Denominator is the buffer capacity, not the observed point count, so a
  // partially-filled buffer draws a proportionally short line (left-aligned)
  // rather than stretching every observation to fill the whole box.
  const denominator = Math.max(bufferCapacity - 1, 1);

  const coords = points.map((value, i) => {
    const x = (i / denominator) * width;
    const y = range === 0 ? height / 2 : height - ((value - min) / range) * height;
    return `${x},${y}`;
  });

  const direction = points[points.length - 1] >= points[0] ? "up" : "down";
  const stroke = direction === "up" ? "var(--color-up)" : "var(--color-down)";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      className={className}
    >
      <title>{title}</title>
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke={stroke}
        strokeWidth={1}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
