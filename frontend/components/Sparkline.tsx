import type { SeriesPoint } from "@/hooks/usePriceStream";

interface SparklineProps {
  points: SeriesPoint[];
  width?: number;
  height?: number;
  color: string;
  className?: string;
}

/**
 * Trend-only mini chart: no axes, no grid. The watchlist row carries the price
 * and change values, so the line never has to be read quantitatively.
 */
export function Sparkline({ points, width = 88, height = 22, color, className = "" }: SparklineProps) {
  if (points.length < 2) {
    return (
      <svg width={width} height={height} className={className} aria-hidden="true">
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeWidth={1}
          strokeDasharray="2 3"
          className="text-edge-strong"
        />
      </svg>
    );
  }

  const values = points.map((point) => point.p);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 2;
  const step = width / (points.length - 1);

  const coords = values.map((value, index) => {
    const x = index * step;
    const y = pad + (1 - (value - min) / span) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg width={width} height={height} className={className} aria-hidden="true">
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
