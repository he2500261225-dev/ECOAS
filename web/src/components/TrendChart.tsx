import { useEffect, useMemo, useRef, useState } from 'react';

export interface TrendDatum {
  date: string;
  value: number;
}

interface Props {
  data: TrendDatum[];
  height?: number;
  color?: string;
  valuePrefix?: string;
  name?: string;
}

function niceMax(value: number) {
  if (value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  const f = value / exp;
  const nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nf * exp;
}

function formatValue(v: number, prefix = '¥') {
  if (v >= 10000) return `${prefix}${(v / 10000).toFixed(1)}万`;
  if (v >= 1000) return `${prefix}${(v / 1000).toFixed(1)}k`;
  return `${prefix}${Math.round(v)}`;
}

export function TrendChart({
  data,
  height = 260,
  color = '#0f766e',
  valuePrefix = '¥',
  name = 'GMV',
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(Math.max(320, w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const max = useMemo(() => niceMax(Math.max(...data.map((d) => d.value), 0)), [data]);
  const margin = { top: 18, right: 18, bottom: 30, left: 58 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const n = data.length;
  const x = (i: number) => (n <= 1 ? margin.left + plotW / 2 : margin.left + (i / (n - 1)) * plotW);
  const y = (v: number) => margin.top + plotH - (v / max) * plotH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((r) => r * max);

  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(d.value)}`).join(' ');
  const areaPath =
    n > 0
      ? `${linePath} L${x(n - 1)},${margin.top + plotH} L${x(0)},${margin.top + plotH} Z`
      : '';
  const labelStep = Math.max(1, Math.ceil(n / 7));
  const hovered = hover !== null ? data[hover] : null;

  return (
    <div ref={wrapRef} className="trend-chart">
      {n === 0 || Math.max(...data.map((d) => d.value)) === 0 ? (
        <div className="trend-empty" style={{ height }}>
          暂无经营数据，回填后自动生成走势
        </div>
      ) : (
        <>
          <svg width={width} height={height} role="img" aria-label={`${name}走势图`}>
            <defs>
              <linearGradient id="trend-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.26} />
                <stop offset="100%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>

            {ticks.map((t, i) => (
              <g key={i}>
                <line
                  x1={margin.left}
                  x2={margin.left + plotW}
                  y1={y(t)}
                  y2={y(t)}
                  stroke="#eef2f6"
                  strokeWidth={1}
                />
                {i > 0 && (
                  <text
                    x={margin.left - 10}
                    y={y(t) + 4}
                    textAnchor="end"
                    fontSize={11}
                    fill="#94a3b8"
                  >
                    {formatValue(t, valuePrefix)}
                  </text>
                )}
                {i === 0 && (
                  <text
                    x={margin.left - 10}
                    y={y(0) + 4}
                    textAnchor="end"
                    fontSize={11}
                    fill="#94a3b8"
                  >
                    ¥0
                  </text>
                )}
              </g>
            ))}

            {areaPath && <path d={areaPath} fill="url(#trend-area)" />}
            {linePath && (
              <path
                d={linePath}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}

            {data.map((d, i) => (
              <g key={d.date}>
                {(i % labelStep === 0 || i === n - 1) && (
                  <text
                    x={x(i)}
                    y={height - 8}
                    textAnchor="middle"
                    fontSize={11}
                    fill="#94a3b8"
                  >
                    {d.date.slice(5)}
                  </text>
                )}
                <rect
                  x={i === 0 ? margin.left : (x(i - 1) + x(i)) / 2}
                  y={margin.top}
                  width={
                    n > 1
                      ? Math.max(
                          6,
                          (i === n - 1 ? x(i) : (x(i) + x(i + 1)) / 2) -
                            (i === 0 ? x(i) : (x(i - 1) + x(i)) / 2),
                        )
                      : plotW
                  }
                  height={plotH}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                />
              </g>
            ))}

            {hover !== null && (
              <g pointerEvents="none">
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1={margin.top}
                  y2={margin.top + plotH}
                  stroke={color}
                  strokeWidth={1}
                  strokeDasharray="3 4"
                  opacity={0.45}
                />
                <circle
                  cx={x(hover)}
                  cy={y(data[hover].value)}
                  r={4.5}
                  fill="#ffffff"
                  stroke={color}
                  strokeWidth={2.5}
                />
              </g>
            )}
          </svg>

          {hovered && (
            <div
              className="trend-tooltip"
              style={{
                left: Math.min(Math.max(x(hover as number), 70), width - 70),
                top: Math.max(6, y(hovered.value) - 64),
              }}
            >
              <div className="trend-tooltip-date">{hovered.date}</div>
              <div className="trend-tooltip-value">
                <span className="dot" style={{ background: color }} />
                {name} {valuePrefix}
                {hovered.value.toLocaleString()}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
