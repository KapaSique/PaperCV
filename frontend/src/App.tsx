import { useEffect, useMemo, useState } from "react";
import { HistoryChart } from "./components/HistoryChart";
import { MetricCard } from "./components/MetricCard";

type Metrics = {
  timestamp: number;
  status: "AT_SCREEN" | "LOOKING_AWAY" | "NO_FACE";
  attention: number;
  focus_streak: number;
  yaw: number;
  pitch: number;
  roll: number;
  gaze_x: number;
  gaze_y: number;
  fps: number;
};

type SettingsPayload = {
  camera: { index: number; width: number; height: number; fps: number };
  attention: {
    yaw_threshold_deg: number;
    pitch_threshold_deg: number;
    gaze_radius: number;
    smoothing_alpha: number;
    hysteresis_frames: number;
    window_seconds: number;
    min_detection_confidence: number;
    min_tracking_confidence: number;
  };
  calibration: { sample_frames: number };
};

type EventEntry = { timestamp: number; type: string; details: string };

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const WS_URL = API_BASE.replace(/^http/, "ws") + "/api/stream";

const initialMetrics: Metrics = {
  timestamp: Date.now() / 1000,
  status: "NO_FACE",
  attention: 0,
  focus_streak: 0,
  yaw: 0,
  pitch: 0,
  roll: 0,
  gaze_x: 0,
  gaze_y: 0,
  fps: 0,
};

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString();
}

export default function App() {
  const [metrics, setMetrics] = useState<Metrics>(initialMetrics);
  const [history, setHistory] = useState<Metrics[]>([]);
  const [events, setEvents] = useState<EventEntry[]>([]);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let active = true;

    const connect = () => {
      ws = new WebSocket(WS_URL + `?ts=${Date.now()}`);
      ws.onmessage = (ev) => {
        const payload = JSON.parse(ev.data);
        setMetrics(payload);
      };
      ws.onclose = () => {
        if (active) {
          setTimeout(connect, 800);
        }
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      active = false;
      ws?.close();
    };
  }, []);

  useEffect(() => {
    const fetchSettings = async () => {
      const res = await fetch(`${API_BASE}/api/settings`);
      const payload = (await res.json()) as SettingsPayload;
      setSettings(payload);
    };
    fetchSettings();
  }, []);

  useEffect(() => {
    const fetchHistory = async () => {
      const res = await fetch(`${API_BASE}/api/history`);
      const payload = await res.json();
      setHistory(payload.frames || []);
      setEvents((payload.events || []).slice(-20).reverse());
    };
    fetchHistory();
    const id = setInterval(fetchHistory, 10000);
    return () => clearInterval(id);
  }, []);

  const statusTone = useMemo(() => {
    if (metrics.status === "AT_SCREEN") return "ok";
    if (metrics.status === "LOOKING_AWAY") return "warn";
    return "bad";
  }, [metrics.status]);

  const handleSettingChange = (section: string, key: string, value: number) => {
    setSettings((prev) => {
      if (!prev) return prev;
      const next = { ...prev, [section]: { ...prev[section as keyof SettingsPayload] } } as SettingsPayload;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (next as any)[section][key] = value;
      return next;
    });
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    setSaving(true);
    await fetch(`${API_BASE}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    setSaving(false);
  };

  const handleCalibrate = async () => {
    await fetch(`${API_BASE}/api/calibrate`, { method: "POST" });
  };

  const videoSrc = `${API_BASE}/api/video`;

  return (
    <div className="app-shell">
      <div className="header">
        <div>
          <div className="title">attention-guard</div>
          <div style={{ opacity: 0.65 }}>Live gaze & attention guardrail</div>
        </div>
        <span className="badge">{metrics.status}</span>
      </div>

      <div className="grid">
        <div className="card">
          <div className="video-wrapper">
            <img src={videoSrc} alt="Live preview" />
            <div className="overlay-chip">
              {metrics.status} - {metrics.attention.toFixed(1)}% - {metrics.fps.toFixed(1)} fps
            </div>
          </div>
          <div className="metrics" style={{ marginTop: 12 }}>
            <MetricCard label="Attention" value={`${metrics.attention.toFixed(1)} %`} tone={statusTone} />
            <MetricCard label="Focus streak" value={`${metrics.focus_streak.toFixed(1)} s`} />
            <MetricCard label="Yaw/Pitch" value={`${metrics.yaw.toFixed(1)} / ${metrics.pitch.toFixed(1)}`} />
            <MetricCard label="Gaze" value={`${metrics.gaze_x.toFixed(2)}, ${metrics.gaze_y.toFixed(2)}`} />
            <MetricCard label="FPS" value={metrics.fps.toFixed(1)} />
          </div>
        </div>

        <div className="card">
          <div className="section-title">Settings</div>
          {settings ? (
            <div className="settings-grid">
              <label>
                Yaw threshold (deg)
                <input
                  type="number"
                  value={settings.attention.yaw_threshold_deg}
                  onChange={(e) => handleSettingChange("attention", "yaw_threshold_deg", Number(e.target.value))}
                />
              </label>
              <label>
                Pitch threshold (deg)
                <input
                  type="number"
                  value={settings.attention.pitch_threshold_deg}
                  onChange={(e) => handleSettingChange("attention", "pitch_threshold_deg", Number(e.target.value))}
                />
              </label>
              <label>
                Gaze radius
                <input
                  type="number"
                  step="0.01"
                  value={settings.attention.gaze_radius}
                  onChange={(e) => handleSettingChange("attention", "gaze_radius", Number(e.target.value))}
                />
              </label>
              <label>
                Window (s)
                <input
                  type="number"
                  value={settings.attention.window_seconds}
                  onChange={(e) => handleSettingChange("attention", "window_seconds", Number(e.target.value))}
                />
              </label>
              <label>
                Smoothing alpha
                <input
                  type="number"
                  step="0.05"
                  value={settings.attention.smoothing_alpha}
                  onChange={(e) => handleSettingChange("attention", "smoothing_alpha", Number(e.target.value))}
                />
              </label>
              <label>
                Hysteresis frames
                <input
                  type="number"
                  value={settings.attention.hysteresis_frames}
                  onChange={(e) => handleSettingChange("attention", "hysteresis_frames", Number(e.target.value))}
                />
              </label>
            </div>
          ) : (
            <div>Loading settings...</div>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button onClick={handleSaveSettings} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button onClick={handleCalibrate} style={{ background: "linear-gradient(135deg, #22d3ee, #0ea5e9)" }}>
              Calibrate
            </button>
          </div>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 12 }}>
        <div className="card">
          <div className="section-title">Attention history (last ~10m)</div>
          <HistoryChart data={history.map((h) => ({ timestamp: h.timestamp, attention: h.attention }))} />
        </div>

        <div className="card">
          <div className="section-title">Recent events</div>
          <div className="events">
            {events.map((ev) => (
              <div key={`${ev.type}-${ev.timestamp}`} className="event-item">
                <strong>{ev.type}</strong> - {formatTime(ev.timestamp)}
                {ev.details ? <div style={{ opacity: 0.7, marginTop: 4 }}>{ev.details}</div> : null}
              </div>
            ))}
            {!events.length && <div className="event-item">No events yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
