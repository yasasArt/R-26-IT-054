import { useEffect, useState } from "react";

import type {
  DeviceConfiguration,
  DeviceConfigurationInput,
  DiscoveredBluetoothDevice,
  ProductionSession,
  SystemReadiness,
} from "../../shared/types";
import { api } from "../lib/api";
import { bluetoothController, useBluetoothController } from "../lib/bluetooth-controller";
import { Icon } from "../components/Icon";
import { BluetoothDevicePicker } from "../components/BluetoothDevicePicker";
import { InlineNotice, PageHeading } from "../components/OperatorUi";
import { ReadinessPanel } from "../components/ReadinessPanel";

interface CameraOption {
  deviceId: string;
  label: string;
}

interface Props {
  configuration: DeviceConfiguration | null;
  readiness: SystemReadiness | null;
  activeSession: ProductionSession | null;
  onUpdated: () => Promise<void>;
  onContinue?: () => void;
  embedded?: boolean;
}

function createDraft(configuration: DeviceConfiguration | null): DeviceConfigurationInput {
  return {
    camera_id: configuration?.camera_id ?? null,
    camera_label: configuration?.camera_label ?? null,
    camera_tested: configuration?.camera_tested ?? false,
    iot_mode: configuration?.iot_mode ?? "NOT_CONFIGURED",
    iot_device_name: configuration?.iot_device_name ?? null,
    iot_device_id: configuration?.iot_device_id ?? null,
    simulation_approved: configuration?.simulation_approved ?? false,
  };
}

export function DeviceSetupScreen({
  configuration,
  readiness,
  activeSession,
  onUpdated,
  onContinue,
  embedded = false,
}: Props) {
  const [draft, setDraft] = useState<DeviceConfigurationInput>(() => createDraft(configuration));
  const [cameras, setCameras] = useState<CameraOption[]>([]);
  const [busy, setBusy] = useState<"scan" | "test" | "save" | "controller" | "models" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [bluetoothDevices, setBluetoothDevices] = useState<DiscoveredBluetoothDevice[]>([]);
  const [selectingDeviceId, setSelectingDeviceId] = useState<string | null>(null);
  const controller = useBluetoothController();

  useEffect(() => {
    setDraft(createDraft(configuration));
  }, [configuration]);

  useEffect(() =>
    window.garmentDesktop.onBluetoothDevices((devices) => {
      setBluetoothDevices(devices);
      setPickerOpen(true);
    }),
  []);

  const saveConfiguration = async (nextDraft: DeviceConfigurationInput, successMessage: string) => {
    setError(null);

    try {
      await api.saveDeviceConfiguration(nextDraft);
      await onUpdated();
      setMessage(successMessage);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The device settings could not be saved.");
    } finally {
      setBusy(null);
    }
  };

  const scanCameras = async () => {
    setBusy("scan");
    setError(null);
    setMessage(null);

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera access is unavailable in this desktop environment.");
      }

      const permissionStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      const devices = await navigator.mediaDevices.enumerateDevices();
      permissionStream.getTracks().forEach((track) => track.stop());
      // macOS releases AVFoundation camera ownership asynchronously after the
      // browser permission stream stops; give the Python sidecar a clean handoff.
      await new Promise<void>((resolve) => window.setTimeout(resolve, 450));
      const browserVideoDevices = devices.filter((device) => device.kind === "videoinput");
      const pythonCameras = await api.scanVisionCameras(browserVideoDevices.length);

      const videoDevices = pythonCameras.map((camera) => {
        const browserLabel = browserVideoDevices[Number(camera.camera_id)]?.label;
        return {
          deviceId: camera.camera_id,
          label: browserLabel
            ? `${browserLabel} · ${camera.width} × ${camera.height}`
            : camera.label,
        };
      });

      setCameras(videoDevices);

      if (!videoDevices.length) {
        throw new Error("No camera was detected. Connect a camera and scan again.");
      }

      const existingCamera = videoDevices.find((device) => device.deviceId === draft.camera_id);
      const selected = existingCamera || videoDevices[0];
      setDraft((current) => ({
        ...current,
        camera_id: selected.deviceId,
        camera_label: selected.label,
        camera_tested: existingCamera ? current.camera_tested : false,
      }));
      setMessage(
        `${videoDevices.length} camera${videoDevices.length === 1 ? "" : "s"} verified for real-time AI inference.`,
      );
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Camera scanning failed.");
    } finally {
      setBusy(null);
    }
  };

  const testCamera = async () => {
    if (!draft.camera_id) {
      setError("Select a camera before running the camera test.");
      return;
    }

    setBusy("test");
    setError(null);

    try {
      const result = await api.testVisionCamera(draft.camera_id);
      const testedDraft = { ...draft, camera_tested: true };
      setDraft(testedDraft);
      await saveConfiguration(
        testedDraft,
        result.workstation_visible
          ? "Camera test passed. The sewing workstation is already visible."
          : "Camera test passed. Workstation visibility will be checked automatically during live production.",
      );
    } catch (caughtError) {
      setBusy(null);
      setError(caughtError instanceof Error ? caughtError.message : "The selected camera could not be opened.");
    }
  };

  const saveIotConfiguration = async () => {
    setBusy("save");

    if (draft.iot_mode !== "REAL" && controller.phase === "CONNECTED") {
      await bluetoothController.disconnect("The physical controller was replaced by validation mode.");
    }

    await saveConfiguration(
      draft,
      draft.iot_mode === "SIMULATED"
        ? "Validation controller configuration saved. Production remains locked."
        : "Controller configuration saved.",
    );
  };

  const connectController = async () => {
    setBusy("controller");
    setError(null);
    setMessage(null);
    setBluetoothDevices([]);
    setSelectingDeviceId(null);
    setPickerOpen(true);

    try {
      await bluetoothController.connect(async ({ deviceId, deviceName }) => {
        const physicalDraft: DeviceConfigurationInput = {
          ...draft,
          iot_mode: "REAL",
          iot_device_id: deviceId,
          iot_device_name: deviceName,
          simulation_approved: false,
        };
        setDraft(physicalDraft);
        await api.saveDeviceConfiguration(physicalDraft);
      });

      setPickerOpen(false);
      await onUpdated();
      setMessage("Physical controller connected. Button notifications are active and production is available once all checks pass.");
    } catch (caughtError) {
      setPickerOpen(false);
      setError(caughtError instanceof Error ? caughtError.message : "The physical operator controller could not connect.");
      await onUpdated();
    } finally {
      setSelectingDeviceId(null);
      setBusy(null);
    }
  };

  const selectBluetoothDevice = async (deviceId: string) => {
    setSelectingDeviceId(deviceId);

    try {
      await window.garmentDesktop.selectBluetoothDevice(deviceId);
    } catch (caughtError) {
      setSelectingDeviceId(null);
      setError(caughtError instanceof Error ? caughtError.message : "The selected Bluetooth device could not be used.");
    }
  };

  const cancelBluetoothPicker = async () => {
    setPickerOpen(false);
    setSelectingDeviceId(null);

    try {
      await window.garmentDesktop.cancelBluetoothSelection();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Bluetooth device selection could not be canceled.");
    }
  };

  const disconnectController = async () => {
    setBusy("controller");
    setError(null);

    try {
      await bluetoothController.disconnect();
      await onUpdated();
      setMessage("The physical controller was disconnected. Production counting remains safely paused.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The controller could not be disconnected.");
    } finally {
      setBusy(null);
    }
  };

  const testController = async () => {
    setBusy("controller");
    setError(null);

    try {
      await api.testValidationController();
      setMessage("Validation controller test passed. The test press was stored without changing any session.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The controller test failed.");
    } finally {
      setBusy(null);
    }
  };

  const retryModels = async () => {
    setBusy("models");
    setError(null);

    try {
      await api.reloadVisionModels();
      await onUpdated();
      setMessage("The trained garment and workstation models are being checked again.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The trained models could not be reloaded.");
    } finally {
      setBusy(null);
    }
  };

  const canContinue = readiness?.productionReady || readiness?.validationReady || Boolean(activeSession);
  const modelFailure = Boolean(
    readiness?.vision_models?.classifier.state === "FAILED" ||
      readiness?.vision_models?.detector.state === "FAILED",
  );
  const physicalControllerReady =
    configuration?.iot_mode === "REAL" &&
    configuration.iot_connected &&
    configuration.iot_notifications_active &&
    controller.phase === "CONNECTED";

  return (
    <div className={embedded ? "embedded-device-setup" : "screen-stack"}>
      {pickerOpen ? (
        <BluetoothDevicePicker
          devices={bluetoothDevices}
          selectingDeviceId={selectingDeviceId}
          onSelect={(deviceId) => void selectBluetoothDevice(deviceId)}
          onCancel={() => void cancelBluetoothPicker()}
        />
      ) : null}
      {!embedded ? (
        <PageHeading
          eyebrow="STEP 01 · WORKSTATION PREPARATION"
          title="Prepare your workstation"
          description="Check the sewing camera and operator controller before creating or resuming a session."
        />
      ) : null}

      {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
      {message ? <InlineNotice tone="success">{message}</InlineNotice> : null}
      {modelFailure ? (
        <InlineNotice tone="warning">
          One of the trained AI models needs attention. Follow the Phase 3 setup guide, then{" "}
          <button type="button" className="notice-inline-button" disabled={busy !== null} onClick={() => void retryModels()}>
            {busy === "models" ? "checking models…" : "retry model loading"}
          </button>.
        </InlineNotice>
      ) : null}

      <div className="device-card-grid">
        <section className="panel device-card">
          <div className="device-card-heading">
            <span className="device-feature-icon icon-camera"><Icon name="camera" size={21} /></span>
            <div>
              <h2>Sewing camera</h2>
              <p>Connect and test the camera before starting production.</p>
            </div>
            <span className={`connection-pill ${configuration?.camera_tested ? "is-connected" : "is-pending"}`}>
              {configuration?.camera_tested ? "Test passed" : "Not tested"}
            </span>
          </div>

          <label className="field-label" htmlFor="camera-select">Selected camera</label>
          <select
            id="camera-select"
            className="form-select"
            value={draft.camera_id ?? ""}
            onChange={(event) => {
              const selected = cameras.find((camera) => camera.deviceId === event.target.value);
              setDraft((current) => ({
                ...current,
                camera_id: selected?.deviceId ?? null,
                camera_label: selected?.label ?? null,
                camera_tested: false,
              }));
            }}
          >
            {!cameras.length && draft.camera_id ? (
              <option value={draft.camera_id}>{draft.camera_label}</option>
            ) : null}
            {!draft.camera_id ? <option value="">Scan to discover cameras</option> : null}
            {cameras.map((camera) => (
              <option key={camera.deviceId} value={camera.deviceId}>{camera.label}</option>
            ))}
          </select>

          <div className="button-row">
            <button type="button" className="action-button action-secondary" onClick={() => void scanCameras()} disabled={busy !== null}>
              <Icon name="refresh" size={16} /> {busy === "scan" ? "Scanning…" : "Scan cameras"}
            </button>
            <button type="button" className="action-button action-primary" onClick={() => void testCamera()} disabled={!draft.camera_id || busy !== null}>
              <Icon name="camera" size={16} /> {busy === "test" ? "Testing…" : "Test camera"}
            </button>
          </div>
        </section>

        <section className="panel device-card">
          <div className="device-card-heading">
            <span className="device-feature-icon icon-controller"><Icon name="bluetooth" size={21} /></span>
            <div>
              <h2>Operator controller</h2>
              <p>Connect the rework and downtime control device.</p>
            </div>
            <span className={`connection-pill ${configuration?.iot_connected ? "is-connected" : "is-pending"}`}>
              {controller.phase === "RECONNECTING"
                ? "Reconnecting"
                : configuration?.iot_connected
                  ? configuration.iot_mode === "SIMULATED" ? "Validation" : "Connected"
                  : "Not connected"}
            </span>
          </div>

          <label className="field-label" htmlFor="iot-mode">Controller mode</label>
          <select
            id="iot-mode"
            className="form-select"
            value={draft.iot_mode}
            onChange={(event) => {
              const mode = event.target.value as DeviceConfigurationInput["iot_mode"];
              setDraft((current) => ({
                ...current,
                iot_mode: mode,
                iot_device_name: mode === "SIMULATED" ? "Validation controller" : "GarmentCounter-IoT",
                iot_device_id: mode === "REAL" ? configuration?.iot_device_id ?? null : null,
                simulation_approved: false,
              }));
            }}
          >
            <option value="NOT_CONFIGURED">Choose a controller mode</option>
            <option value="REAL">Physical ESP32-C3 controller</option>
            <option value="SIMULATED">Validation-only simulation</option>
          </select>

          {draft.iot_mode === "SIMULATED" ? (
            <label className="approval-checkbox">
              <input
                type="checkbox"
                checked={draft.simulation_approved}
                onChange={(event) => setDraft((current) => ({ ...current, simulation_approved: event.target.checked }))}
              />
              <span>I understand simulated controller events can be used only for validation.</span>
            </label>
          ) : draft.iot_mode === "REAL" ? (
            <div className="controller-live-status">
              <p className="field-help">{controller.deviceId ? controller.message : "Switch on Bluetooth and press Button A on your ESP32-C3 to start advertising."}</p>
              {physicalControllerReady ? (
                <div className="controller-status-grid">
                  <span><strong>Device</strong>{configuration.iot_device_name}</span>
                  <span><strong>Button feed</strong>Live notifications</span>
                  <span><strong>Last button</strong>{controller.lastButton ?? "Waiting for a press"}</span>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="field-help">Choose the physical controller for production or clearly labelled simulation for validation.</p>
          )}

          <div className="button-row">
            {draft.iot_mode === "REAL" ? (
              <>
                <button
                  type="button"
                  className="action-button action-primary"
                  onClick={() => void (physicalControllerReady ? disconnectController() : connectController())}
                  disabled={busy !== null || controller.phase === "SCANNING" || controller.phase === "CONNECTING"}
                >
                  <Icon name="bluetooth" size={16} />
                  {busy === "controller" || controller.phase === "SCANNING" || controller.phase === "CONNECTING"
                    ? "Connecting…"
                    : physicalControllerReady ? "Disconnect controller" : "Connect controller"}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="action-button action-primary"
                onClick={() => void saveIotConfiguration()}
                disabled={busy !== null || draft.iot_mode === "NOT_CONFIGURED" || (draft.iot_mode === "SIMULATED" && !draft.simulation_approved)}
              >
                <Icon name="check" size={16} /> {busy === "save" ? "Saving…" : "Save controller setup"}
              </button>
            )}
            {configuration?.iot_mode === "SIMULATED" && configuration.simulation_approved ? (
              <button type="button" className="action-button action-secondary" onClick={() => void testController()} disabled={busy !== null}>
                <Icon name="bluetooth" size={16} /> {busy === "controller" ? "Testing…" : "Test controller"}
              </button>
            ) : null}
          </div>
        </section>
      </div>

      {!embedded ? (
        <>
          <ReadinessPanel readiness={readiness} />
          <div className="workflow-footer">
            <div>
              <strong>{canContinue ? "Your workstation setup can continue." : "Complete the camera and controller checks."}</strong>
              <span>Production requires a tested camera, verified AI models, and the connected physical controller.</span>
            </div>
            <button type="button" className="action-button action-primary action-large" onClick={onContinue} disabled={!canContinue}>
              {activeSession ? "Resume active session" : "Continue to session"} <Icon name="arrow-right" size={17} />
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
