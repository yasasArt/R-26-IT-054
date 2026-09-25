import { useCallback, useEffect, useRef, useState } from "react";

import type { InferenceStatus, ProductionSession } from "../../shared/types";
import { allowsRecordedWorkstationVideo, describeSewingActivity } from "../../shared/vision-policy";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";
import { Icon } from "./Icon";
import { InlineNotice } from "./OperatorUi";

interface Props {
  session: ProductionSession;
  inference: InferenceStatus | null;
  refresh: () => Promise<void>;
}

export function VisionMonitor({ session, inference, refresh }: Props) {
  const [busy, setBusy] = useState<"camera" | "video" | "stop" | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [previewPainted, setPreviewPainted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedSession = useRef<number | null>(null);
  const switchingSource = useRef(false);
  const running = inference?.running ?? false;
  const modelsReady = inference?.models.ready ?? false;

  const attachStream = useCallback(async () => {
    const url = await window.garmentDesktop.getLiveStreamUrl(session.id);
    setPreviewPainted(false);
    setStreamUrl(`${url}?connection=${Date.now()}`);
  }, [session.id]);

  useEffect(() => {
    let cancelled = false;

    if (switchingSource.current) return;

    if (!running) {
      if (busy !== "camera" && busy !== "video") {
        setStreamUrl(null);
        setPreviewPainted(false);
      }
      return;
    }

    if (!streamUrl) {
      void window.garmentDesktop.getLiveStreamUrl(session.id).then((url) => {
        if (!cancelled) {
          setPreviewPainted(false);
          setStreamUrl(`${url}?connection=${Date.now()}`);
        }
      });
    }

    return () => {
      cancelled = true;
    };
  }, [busy, running, session.id, streamUrl]);

  const startCamera = useCallback(async () => {
    setBusy("camera");
    setError(null);
    setStreamUrl(null);
    setPreviewPainted(false);
    try {
      await api.startVision(session.id, "camera");
      await attachStream();
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The live sewing camera could not start.");
    } finally {
      setBusy(null);
    }
  }, [attachStream, refresh, session.id]);

  useEffect(() => {
    if (!modelsReady || running || startedSession.current === session.id) return;
    startedSession.current = session.id;
    void startCamera();
  }, [modelsReady, running, session.id, startCamera]);

  const startVideo = async () => {
    setBusy("video");
    setError(null);

    try {
      const selected = await window.garmentDesktop.selectValidationVideo();
      if (selected.canceled || !selected.filePath) return;

      switchingSource.current = true;
      setStreamUrl(null);
      setPreviewPainted(false);
      const currentStatus = await api.inferenceStatus(session.id);
      if (currentStatus.running) await api.stopVision(session.id);
      await api.startVision(session.id, "video", selected.filePath);
      // Mount the authenticated MJPEG preview before refreshing the wider
      // dashboard. The backend waits for this connection and publishes the
      // first video frame before it performs any model inference.
      await attachStream();
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The workstation video could not start.");
    } finally {
      switchingSource.current = false;
      setBusy(null);
    }
  };

  const stopMonitoring = async () => {
    setBusy("stop");
    setError(null);

    try {
      await api.stopVision(session.id);
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The camera could not be stopped safely.");
    } finally {
      setBusy(null);
    }
  };

  const tone = !running || inference?.phase === "PAUSED" || !inference?.workstation_visible
    ? "attention"
    : inference?.sewing_state === "SEWING"
      ? "sewing"
      : "ready";

  return (
    <section className="panel vision-monitor-panel">
      <header className="vision-monitor-heading">
        <div><span className="eyebrow">LIVE AI WORKSTATION</span><h2>Sewing camera and garment recognition</h2></div>
        <span className={`vision-live-pill ${running ? "is-live" : "is-offline"}`}>
          <span /> {running ? "LIVE" : "OFFLINE"}
        </span>
      </header>

      {error || inference?.last_error ? (
        <InlineNotice tone="warning">{error || inference?.last_error}</InlineNotice>
      ) : null}
      {inference?.phase === "VIDEO_COMPLETE" ? (
        <InlineNotice tone="info">
          {inference.test_workflow
            ? "The production test workflow has finished. No production counts were changed."
            : "The recorded workstation video has finished. Its confirmed garment events remain saved in this validation session."}
        </InlineNotice>
      ) : null}
      {running && inference?.test_workflow ? (
        <InlineNotice tone="info">
          Production test mode is active. The AI workflow is running, but test garments will not change production records.
        </InlineNotice>
      ) : null}

      <div className="vision-monitor-grid">
        <div className="vision-camera-stage">
          {(running || busy === "camera" || busy === "video") && streamUrl ? (
            <img
              className="vision-camera-frame"
              src={streamUrl}
              onLoad={() => setPreviewPainted(true)}
              alt={inference?.source_type === "video"
                ? "Recorded sewing-workstation test with synchronized AI overlay"
                : "Live sewing-workstation camera with AI detection overlay"}
            />
          ) : (
            <div className="vision-camera-placeholder">
              <Icon name="camera" size={33} />
              <strong>{modelsReady ? "Sewing camera is ready" : "Preparing your trained AI models"}</strong>
              <span>{modelsReady ? "Start monitoring to see the verified workstation." : "The workstation detector and garment classifier are being verified."}</span>
            </div>
          )}
          {streamUrl && !previewPainted ? (
            <span className="vision-preview-status">Preparing the first visible frame…</span>
          ) : null}
          {running && inference?.source_label ? (
            <span className="vision-source-badge">
              {inference.source_type === "video" ? `Test workflow · ${inference.source_label}` : inference.source_label}
            </span>
          ) : null}
        </div>

        <div className="vision-facts">
          <article className={`vision-state-card is-${tone}`}>
            <span>Current sewing activity</span>
            <strong>{describeSewingActivity(inference)}</strong>
            <small>{inference?.counting_message ?? "Waiting for the workstation pipeline."}</small>
          </article>
          <article className="vision-fact-row">
            <span>Workstation view</span>
            <strong>{inference?.workstation_visible ? "Verified and visible" : "Not yet verified"}</strong>
            <small>{inference?.workstation_visible ? `${formatNumber(inference.workstation_confidence * 100, 0)}% detector confidence` : "Point the camera at the sewing station."}</small>
          </article>
          <article className="vision-fact-row">
            <span>Activity confidence</span>
            <strong>{inference?.classification_confidence ? `${formatNumber(inference.classification_confidence * 100, 0)}%` : "—"}</strong>
            <small>{running ? `${formatNumber(inference?.processing_fps ?? 0, 1)} camera frames per second` : "Live camera processing is stopped."}</small>
          </article>
          <article className="vision-fact-row">
            <span>Automatic garment counting</span>
            <strong>{inference?.test_workflow ? "Test only" : inference?.counting_permitted ? "Active" : "Safely paused"}</strong>
            <small>{inference?.test_workflow ? "Test results do not change production records." : "Counts only after a completed sewing cycle."}</small>
          </article>
        </div>
      </div>

      <footer className="vision-monitor-actions">
        <button
          type="button"
          className="action-button action-primary"
          disabled={busy !== null || running || !modelsReady}
          onClick={() => void startCamera()}
        >
          <Icon name="camera" size={16} /> {busy === "camera" ? "Starting camera…" : "Start live camera"}
        </button>
        {allowsRecordedWorkstationVideo(session.session_mode) ? (
          <button
            type="button"
            className="action-button action-secondary"
            disabled={busy !== null || !modelsReady}
            onClick={() => void startVideo()}
          >
            <Icon name="folder" size={16} /> {busy === "video" ? "Preparing preview…" : "Test workflow video"}
          </button>
        ) : null}
        <button
          type="button"
          className="action-button action-secondary"
          disabled={busy !== null || !running}
          onClick={() => void stopMonitoring()}
        >
          <Icon name="pause" size={16} /> {busy === "stop" ? "Stopping…" : "Stop monitoring"}
        </button>
      </footer>
    </section>
  );
}
