type MetricCardProps = {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad";
};

const toneColor: Record<string, string> = {
  ok: "#22d3ee",
  warn: "#f1a751",
  bad: "#ef4444",
  default: "#e7f5ff",
};

export function MetricCard({ label, value, tone = "default" }: MetricCardProps) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: toneColor[tone] || toneColor.default }}>
        {value}
      </div>
    </div>
  );
}
