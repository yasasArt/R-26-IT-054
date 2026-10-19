import React, { useEffect, useState } from 'react';
import {
  Play,
  Square,
  Camera,
  Video,
  Settings2,
  CheckCircle2,
  XCircle,
  Clock,
  Package,
  Activity,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { reworkRequest, REWORK_STREAM_URL } from '../api';

const CAMERA_INDEXES = [0, 1, 2, 3, 4];

export default function LiveProduction() {
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [sourceType, setSourceType] = useState('webcam');
  const [sourceVal, setSourceVal] = useState('0');
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [reworkTime, setReworkTime] = useState(2.0);
  const [feedError, setFeedError] = useState(false);

  // Advanced settings
  const [confThreshold, setConfThreshold] = useState(0.25);
  const [topPct, setTopPct] = useState(30);
  const [bottomPct, setBottomPct] = useState(70);
  const [centerMinPct, setCenterMinPct] = useState(10);
  const [centerMaxPct, setCenterMaxPct] = useState(90);

  const [goodCount, setGoodCount] = useState(0);
  const [reworkCount, setReworkCount] = useState(0);

  /*
   * IMPORTANT CAMERA FIX
   * --------------------
   * Do NOT call navigator.mediaDevices.getUserMedia() here.
   *
   * FastAPI/OpenCV is the only process that should own the Rework webcam.
   * Opening the same webcam first from Chromium/Electron can make
   * cv2.VideoCapture() fail or produce a black MJPEG stream on Windows.
   *
   * OpenCV camera indexes (0, 1, 2...) also do not reliably map to browser
   * deviceId values, so this UI intentionally uses explicit OpenCV indexes.
   */

  const handleSourceChange = (type) => {
    setSourceType(type);
    setFeedError(false);

    if (type === 'webcam') {
      setSourceVal('0');
    } else {
      setSourceVal('');
    }
  };

  // Poll Rework metrics only while a session is running.
  useEffect(() => {
    if (!isRunning) return undefined;

    const interval = setInterval(async () => {
      try {
        const data = await reworkRequest('GET', '/metrics');
        setGoodCount(data.good ?? 0);
        setReworkCount(data.rework ?? 0);
      } catch (error) {
        console.error('Failed to fetch Rework metrics:', error);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isRunning]);

  // Send advanced-setting changes to the Rework backend while live.
  useEffect(() => {
    if (!isRunning) return undefined;

    const timeoutId = setTimeout(async () => {
      try {
        await reworkRequest('POST', '/update_settings', {
          conf_threshold: confThreshold,
          top_pct: topPct,
          bottom_pct: bottomPct,
          center_min_pct: centerMinPct,
          center_max_pct: centerMaxPct,
        });
      } catch (error) {
        console.error('Failed to update Rework settings live:', error);
      }
    }, 200);

    return () => clearTimeout(timeoutId);
  }, [
    confThreshold,
    topPct,
    bottomPct,
    centerMinPct,
    centerMaxPct,
    isRunning,
  ]);

  const handleStart = async () => {
    if (sourceVal === '') {
      alert('Please enter a valid Camera ID or Video File path.');
      return;
    }

    setFeedError(false);

    try {
      const data = await reworkRequest('POST', '/start', {
        source_type: sourceType,
        source_val: sourceVal,
        conf_threshold: confThreshold,
        top_pct: topPct,
        bottom_pct: bottomPct,
        center_min_pct: centerMinPct,
        center_max_pct: centerMaxPct,
      });

      if (data.status === 'started' || data.status === 'already running') {
        setGoodCount(0);
        setReworkCount(0);
        setSessionId(data.session_id || `SESSION_${Date.now()}`);
        setIsRunning(true);
        return;
      }

      alert(`Error starting Rework backend: ${data.message || 'Unknown error'}`);
    } catch (error) {
      alert('Cannot connect to the Garment Rework Python backend.');
      console.error(error);
    }
  };

  const handleStop = async () => {
    // Unmount the MJPEG <img> immediately so Chromium closes the stream.
    setIsRunning(false);
    setFeedError(false);

    try {
      await reworkRequest('POST', '/stop');
    } catch (error) {
      console.error('Error stopping Rework backend:', error);
    } finally {
      setSessionId(null);
    }
  };

  const totalChecked = goodCount + reworkCount;
  const passRate =
    totalChecked > 0 ? ((goodCount / totalChecked) * 100).toFixed(1) : '0.0';
  const estDelayMins = (reworkCount * reworkTime).toFixed(1);

  // The query string forces Electron/Chromium to make a fresh MJPEG request
  // for every new Rework session instead of reusing a cached stream URL.
  const liveStreamUrl = sessionId
    ? `${REWORK_STREAM_URL}?session=${encodeURIComponent(sessionId)}`
    : REWORK_STREAM_URL;

  return (
    <div className="max-w-[1400px] mx-auto h-full flex flex-col font-sans">
      <div className="mb-4 flex justify-between items-end pb-3 border-b border-line">
        <div>
          <h2 className="text-xl font-bold text-ink flex items-center gap-2">
            <span className="bg-accent-soft p-1.5 rounded-lg text-accent">
              <Camera size={18} />
            </span>
            MAS Automated Garment Quality Assurance
          </h2>
          <p className="text-ink-secondary text-xs mt-0.5">
            Live QC line monitoring with Order Delay Analytics
          </p>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <div
            className={`px-3 py-1 rounded-full text-[11px] font-bold tracking-wider border ${
              isRunning
                ? 'bg-status-success-bg text-status-success border-status-success/30'
                : 'bg-status-error-bg text-status-error border-status-error/30'
            }`}
          >
            {isRunning ? '● LIVE INSPECTION RUNNING' : '● SYSTEM STOPPED'}
          </div>

          {isRunning && sessionId && (
            <div className="text-[10px] font-mono text-ink-secondary bg-surface px-2 py-0.5 rounded border border-line shadow-sm">
              Active: {sessionId}
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-6 h-full pb-4 overflow-hidden">
        <div className="w-[320px] shrink-0 flex flex-col gap-3 overflow-y-auto pr-2 pb-10">
          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm">
            <h3 className="font-bold text-ink text-xs flex items-center gap-2 mb-3">
              <Settings2 size={14} className="text-ink-soft" />
              Controls & Input Source
            </h3>

            <div className="flex bg-canvas p-1 rounded-lg mb-3 border border-line-soft">
              <button
                onClick={() => handleSourceChange('webcam')}
                disabled={isRunning}
                className={`flex-1 text-[11px] font-bold py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-all ${
                  sourceType === 'webcam'
                    ? 'bg-surface shadow-sm text-ink border border-line-soft'
                    : 'text-ink-soft hover:text-ink'
                }`}
              >
                <Camera size={12} /> Webcam
              </button>

              <button
                onClick={() => handleSourceChange('video')}
                disabled={isRunning}
                className={`flex-1 text-[11px] font-bold py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-all ${
                  sourceType === 'video'
                    ? 'bg-surface shadow-sm text-ink border border-line-soft'
                    : 'text-ink-soft hover:text-ink'
                }`}
              >
                <Video size={12} /> Video File
              </button>
            </div>

            <div className="mb-4">
              {sourceType === 'webcam' ? (
                <select
                  value={sourceVal}
                  onChange={(e) => setSourceVal(e.target.value)}
                  disabled={isRunning}
                  className="w-full text-xs p-2 border border-line bg-canvas rounded-lg outline-none focus:border-accent text-ink disabled:opacity-50 cursor-pointer"
                >
                  {CAMERA_INDEXES.map((index) => (
                    <option key={index} value={String(index)}>
                      Camera Index {index}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={sourceVal}
                  onChange={(e) => setSourceVal(e.target.value)}
                  placeholder="e.g. D:\\Videos\\QC\\test.mp4"
                  disabled={isRunning}
                  className="w-full text-xs p-2 border border-line bg-canvas rounded-lg outline-none focus:border-accent text-ink disabled:opacity-50"
                />
              )}
            </div>

            <div className="space-y-2">
              <button
                onClick={handleStart}
                disabled={isRunning}
                className="w-full flex justify-center items-center gap-2 bg-accent text-white py-2 rounded-lg text-xs font-bold hover:bg-accent/90 disabled:opacity-50 transition-colors shadow-sm"
              >
                <Play size={14} /> Start New Session
              </button>

              <button
                onClick={handleStop}
                disabled={!isRunning}
                className="w-full flex justify-center items-center gap-2 bg-surface border border-line text-ink py-2 rounded-lg text-xs font-bold hover:bg-canvas disabled:opacity-50 transition-colors"
              >
                <Square size={14} /> End Session
              </button>
            </div>
          </div>

          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm">
            <h3 className="font-bold text-ink text-xs flex items-center gap-2 mb-2">
              <Clock size={14} className="text-ink-soft" />
              Order Analytics
            </h3>

            <label className="block text-[11px] font-semibold text-ink-secondary mb-1">
              Avg Rework Fix Time (Mins):
            </label>

            <input
              type="number"
              value={reworkTime}
              onChange={(e) => setReworkTime(Number(e.target.value))}
              step="0.5"
              className="w-full text-xs p-2 border border-line bg-canvas rounded-lg outline-none focus:border-accent text-ink"
            />
          </div>

          <div className="bg-surface border border-line rounded-xl shadow-sm mb-4">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between p-3 text-xs font-bold text-ink hover:bg-canvas transition-colors rounded-xl"
            >
              <span className="flex items-center gap-2">
                <Settings2 size={13} className="text-accent" /> Advanced settings
              </span>
              {showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>

            {showAdvanced && (
              <div className="p-4 pt-4 bg-canvas/50 border-t border-line space-y-4 rounded-b-xl">
                <SliderControl
                  label="Detection sensitivity"
                  value={confThreshold}
                  min={0.05}
                  max={0.95}
                  step={0.05}
                  onChange={setConfThreshold}
                />
                <SliderControl
                  label="Top line position (%)"
                  value={topPct}
                  min={5}
                  max={50}
                  step={1}
                  onChange={setTopPct}
                />
                <SliderControl
                  label="Bottom line position (%)"
                  value={bottomPct}
                  min={50}
                  max={95}
                  step={1}
                  onChange={setBottomPct}
                />
                <SliderControl
                  label="Center zone — left edge (%)"
                  value={centerMinPct}
                  min={0}
                  max={40}
                  step={1}
                  onChange={setCenterMinPct}
                />
                <SliderControl
                  label="Center zone — right edge (%)"
                  value={centerMaxPct}
                  min={60}
                  max={100}
                  step={1}
                  onChange={setCenterMaxPct}
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-4 min-w-[500px]">
          <div className="bg-sidebar rounded-xl overflow-hidden border border-line shadow-inner flex flex-col aspect-video relative">
            <div className="absolute top-4 left-4 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 flex items-center gap-2 z-10">
              <div
                className={`w-2 h-2 rounded-full ${
                  isRunning && !feedError
                    ? 'bg-status-success animate-pulse'
                    : 'bg-status-error'
                }`}
              />
              <span className="text-xs font-semibold text-white tracking-wider">
                {!isRunning
                  ? 'CAMERA DISCONNECTED'
                  : feedError
                    ? 'CAMERA STREAM ERROR'
                    : 'LIVE FEED (FASTAPI)'}
              </span>
            </div>

            {isRunning ? (
              <img
                key={sessionId}
                src={liveStreamUrl}
                alt="Live QC Feed"
                className="w-full h-full object-contain"
                draggable={false}
                onLoad={() => setFeedError(false)}
                onError={() => setFeedError(true)}
              />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-[#5B6980]">
                <Video size={48} className="mb-4 opacity-50" />
                <p className="text-xs font-medium">
                  Press Start New Session to connect to the Python camera feed.
                </p>
              </div>
            )}

            {isRunning && feedError && (
              <div className="absolute inset-x-0 bottom-0 bg-black/70 text-white text-[11px] px-4 py-3 text-center">
                The backend session started, but the MJPEG feed could not be displayed.
                End the session and try Camera Index 1, 2, 3, or 4.
              </div>
            )}
          </div>
        </div>

        <div className="w-[240px] shrink-0 flex flex-col gap-3">
          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
              <CheckCircle2 size={32} className="text-status-success" />
            </div>
            <p className="text-[10px] font-bold text-ink-secondary tracking-widest uppercase mb-0.5">
              Good
            </p>
            <p className="text-3xl font-black text-status-success">{goodCount}</p>
          </div>

          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
              <XCircle size={32} className="text-status-error" />
            </div>
            <p className="text-[10px] font-bold text-ink-secondary tracking-widest uppercase mb-0.5">
              Rework
            </p>
            <p className="text-3xl font-black text-status-error">{reworkCount}</p>
          </div>

          <div className="bg-gradient-to-br from-[#FFF5E6] to-surface border border-[#FAD399] rounded-xl p-4 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
              <Clock size={32} className="text-status-warning" />
            </div>
            <p className="text-[10px] font-bold text-status-warning tracking-widest uppercase mb-0.5">
              Est. Order Delay
            </p>
            <p className="text-3xl font-black text-status-warning">
              {estDelayMins}
              <span className="text-lg font-bold text-status-warning/70 ml-0.5">m</span>
            </p>
          </div>

          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-5">
              <Package size={32} className="text-ink" />
            </div>
            <p className="text-[10px] font-bold text-ink-secondary tracking-widest uppercase mb-0.5">
              Total Checked
            </p>
            <p className="text-3xl font-black text-ink">{totalChecked}</p>
          </div>

          <div className="bg-surface border border-line rounded-xl p-4 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
              <Activity size={32} className="text-status-violet" />
            </div>
            <p className="text-[10px] font-bold text-ink-secondary tracking-widest uppercase mb-0.5">
              Pass Rate
            </p>
            <p className="text-3xl font-black text-status-violet">
              {passRate}
              <span className="text-lg font-bold text-status-violet/70 ml-0.5">%</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function SliderControl({ label, value, min, max, step, onChange }) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="text-[11px] font-bold text-ink mb-0.5">{label}</div>
      <div className="text-accent font-bold text-xs text-center mb-0.5">{value}</div>
      <input
        type="range"
        className="w-full accent-accent cursor-pointer"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {(min !== 0 || max !== 1) && (
        <div className="flex justify-between text-[10px] font-semibold text-ink-soft mt-0.5">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      )}
    </div>
  );
}
