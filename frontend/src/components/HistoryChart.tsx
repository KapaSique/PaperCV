type HistoryChartProps = {
  data: { timestamp: number; attention: number }[];
};

export function HistoryChart({ data }: HistoryChartProps) {
  if (!data.length) {
    return <div className="event-item">History is empty yet.</div>;
  }

  const width = 600;
  const height = 120;
  const minT = Math.min(...data.map((d) => d.timestamp));
  const maxT = Math.max(...data.map((d) => d.timestamp));
  const span = Math.max(maxT - minT, 1);

  const points = data
    .map((d) => {
      const x = ((d.timestamp - minT) / span) * width;
      const y = height - (Math.max(0, Math.min(100, d.attention)) / 100) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="history-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline fill="none" stroke="rgba(34,211,238,0.7)" strokeWidth="3" points={points} />
      <polyline
        fill="rgba(34,211,238,0.12)"
        stroke="none"
        points={`0,${height} ${points} ${width},${height}`}
      />
      <line x1="0" y1={height * 0.2} x2={width} y2={height * 0.2} stroke="rgba(255,255,255,0.08)" />
      <text x="8" y="16" fill="rgba(231,245,255,0.6)" fontSize="12">
        Attention over time
      </text>
    </svg>
  );
}
