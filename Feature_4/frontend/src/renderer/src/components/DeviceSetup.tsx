import { useEffect, useState } from "react";
import {
  Camera,
  ScanLine,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  RefreshCcw,
  Circle,
  ListChecks,
  Info,
} from "lucide-react";
import {
  fetchCameraDevice,
  updateCameraDevice,
  fetchAvailableCameras,
  testCameraDevice,
  fetchPipelineStatus,
  AvailableCamera,
} from "../lib/api";

type TestState = "idle" | "testing" | "passed" | "failed";

function formatDeviceLabel(camera: AvailableCamera | undefined, resolution?: string) {
  const name = camera?.name || "Unknown camera";
  return resolution ? `${name} · ${resolution}` : name;
}

function ChecklistRow({ done, label }: { done: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2.5 text-[13px]">
      {done ? <CheckCircle2 size={16} className="text-success flex-shrink-0" /> : <Circle size={16} className="text-line flex-shrink-0" />}
      <span className={done ? "text-ink" : "text-ink-soft"}>{label}</span>
    </div>
  );
}

export default function DeviceSetup({ onTestPassed }: { onTestPassed?: () => void }) {
  const [cameras, setCameras] = useState<AvailableCamera[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const [testState, setTestState] = useState<TestState>("idle");
  const [testError, setTestError] = useState("");
  const [savedDevice, setSavedDevice] = useState<{ camera_index: number; camera_label: string } | null>(null);

  // Revisiting this page (e.g. after navigating to the Live Dashboard and
  // back) should not make an already-tested, still-running camera look
  // untested - testState is local and resets to "idle" on every mount, so
  // without this the checklist and Continue button would demand a pointless
  // re-test of a camera that's actually live. Cross-check the saved device
  // against the CV service's own live camera_active flag rather than just
  // trusting that a saved device implies the camera is still on (it may have
  // been turned off since, e.g. via Downtime Log).
  useEffect(() => {
    (async () => {
      const [current, available, pipeline] = await Promise.all([
        fetchCameraDevice(),
        fetchAvailableCameras(),
        fetchPipelineStatus(),
      ]);

      setCameras(available);

      if (current) {
        setSavedDevice(current);
        setSelectedIndex(current.camera_index);

        if (pipeline?.camera_active) {
          setTestState("passed");
        }
      }
    })();
  }, []);

  const scanCameras = async () => {
    setScanning(true);
    setScanError("");
    try {
      const available = await fetchAvailableCameras();
      setCameras(available);
      if (available.length === 0) {
        setScanError("No cameras found. Check the camera is connected and try again.");
      } else if (selectedIndex === null) {
        setSelectedIndex(available[0].index);
      }
    } catch (error) {
      setScanError(error instanceof Error ? error.message : String(error));
    } finally {
      setScanning(false);
    }
  };

  const testCamera = async () => {
    if (selectedIndex === null) return;
    setTestState("testing");
    setTestError("");

    const result = await testCameraDevice(selectedIndex);

    if (!result.success) {
      setTestState("failed");
      setTestError(result.error || "Could not open this camera.");
      return;
    }

    const camera = cameras.find((c) => c.index === selectedIndex);
    const resolution = result.width && result.height ? `${result.width} × ${result.height}` : undefined;
    const cameraLabel = formatDeviceLabel(camera, resolution);

    await updateCameraDevice({ camera_index: selectedIndex, camera_label: cameraLabel });
    setSavedDevice({ camera_index: selectedIndex, camera_label: cameraLabel });
    setTestState("passed");
  };

  const selectedCamera = cameras.find((c) => c.index === selectedIndex);

  return (
    <div className="w-full">
      <div className="text-accent text-[11px] font-mono font-bold uppercase tracking-widest mb-2">
        Step 1 · Workstation Preparation
      </div>
      <h1 className="text-ink text-2xl font-bold mb-1.5">Prepare your camera</h1>
      <p className="text-ink-secondary text-[13px] mb-7">
        Scan for connected cameras and confirm the right one works before moving on to live capture.
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
        <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
          <div className="flex items-start justify-between gap-4 px-7 py-6 border-b border-line-soft">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-xl bg-accent-soft flex items-center justify-center flex-shrink-0">
                <Camera size={20} className="text-accent" />
              </div>
              <div>
                <h3 className="text-ink font-semibold text-[15px]">Select Camera</h3>
                <p className="text-ink-soft text-[12.5px] mt-0.5">Connect and test the camera before starting capture.</p>
              </div>
            </div>
            {testState === "passed" && (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-success bg-success-soft px-2.5 py-1 rounded-full flex-shrink-0">
                <CheckCircle2 size={12} /> Test passed
              </span>
            )}
          </div>

          <div className="px-7 py-6 flex flex-col gap-5">
            <div>
              <label className="text-ink text-[13px] font-medium mb-1.5 block">Selected camera</label>
              <select
                className="bg-surface border border-line rounded-lg px-3 py-2.5 text-ink text-[13px] w-full focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-shadow disabled:opacity-50"
                value={selectedIndex ?? ""}
                disabled={cameras.length === 0}
                onChange={(e) => {
                  setSelectedIndex(Number(e.target.value));
                  setTestState("idle");
                }}
              >
                {cameras.length === 0 ? (
                  <option value="">Scan for cameras first</option>
                ) : (
                  cameras.map((c) => (
                    <option key={c.index} value={c.index}>
                      {c.name}
                    </option>
                  ))
                )}
              </select>
              {selectedCamera && testState === "idle" && (
                <p className="text-ink-soft text-[11px] mt-1.5">Ready to test "{selectedCamera.name}".</p>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={scanCameras}
                disabled={scanning}
                className="flex items-center gap-2 px-4 py-2.5 bg-surface text-ink hover:bg-surface-muted border border-line rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50"
              >
                {scanning ? <Loader2 size={15} className="animate-spin" /> : <ScanLine size={15} />}
                {scanning ? "Scanning..." : cameras.length > 0 ? "Rescan" : "Scan cameras"}
              </button>

              <button
                onClick={testCamera}
                disabled={selectedIndex === null || testState === "testing"}
                className="flex items-center gap-2 px-4 py-2.5 bg-accent text-white hover:bg-accent/90 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50 shadow-sm"
              >
                {testState === "testing" ? <Loader2 size={15} className="animate-spin" /> : <Camera size={15} />}
                {testState === "testing" ? "Testing..." : "Test camera"}
              </button>
            </div>

            {scanError && (
              <div className="flex items-center gap-2.5 text-[13px] text-error bg-error-soft px-4 py-3 rounded-lg">
                <XCircle size={16} className="flex-shrink-0" /> {scanError}
              </div>
            )}

            {testState === "passed" && (
              <div className="flex items-center gap-2.5 text-[13px] text-success bg-success-soft px-4 py-3 rounded-lg">
                <CheckCircle2 size={16} className="flex-shrink-0" /> Camera is successfully turned on.
              </div>
            )}

            {testState === "failed" && (
              <div className="flex items-center gap-2.5 text-[13px] text-error bg-error-soft px-4 py-3 rounded-lg">
                <XCircle size={16} className="flex-shrink-0" /> {testError}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between px-7 py-5 bg-surface-muted border-t border-line-soft">
            <p className="text-ink-soft text-[12px] flex items-center gap-1.5">
              {savedDevice ? (
                <>
                  <RefreshCcw size={12} /> Active camera: <span className="text-ink font-medium">{savedDevice.camera_label}</span>
                </>
              ) : (
                "No camera saved yet."
              )}
            </p>

            <button
              onClick={() => onTestPassed?.()}
              disabled={testState !== "passed"}
              className={
                testState === "passed"
                  ? "flex items-center gap-2 px-5 py-2.5 bg-accent text-white hover:bg-accent/90 rounded-lg text-[13px] font-semibold transition-colors shadow-sm"
                  : "flex items-center gap-2 px-5 py-2.5 bg-line-soft text-ink-soft rounded-lg text-[13px] font-semibold cursor-not-allowed"
              }
            >
              Continue <ArrowRight size={15} />
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-6">
          <div className="bg-surface border border-line rounded-2xl shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <ListChecks size={16} className="text-accent" />
              <h3 className="text-ink font-semibold text-[13px] uppercase tracking-wide">Setup Checklist</h3>
            </div>
            <div className="flex flex-col gap-3">
              <ChecklistRow done={cameras.length > 0} label="Cameras scanned" />
              <ChecklistRow done={selectedIndex !== null} label="Camera selected" />
              <ChecklistRow done={testState === "passed"} label="Camera tested" />
              <ChecklistRow done={!!savedDevice} label="Ready for live capture" />
            </div>
          </div>

          <div className="bg-surface border border-line rounded-2xl shadow-sm p-6">
            <div className="flex items-center gap-2 mb-3">
              <Info size={16} className="text-accent" />
              <h3 className="text-ink font-semibold text-[13px] uppercase tracking-wide">Tips</h3>
            </div>
            <ul className="flex flex-col gap-2.5 text-ink-secondary text-[12.5px]">
              <li>Both the laptop's built-in camera and any external USB webcam appear in the list - rescan after plugging one in.</li>
              <li>Position the camera to look down on the folding area for the most reliable detection.</li>
              <li>Camera changes take effect immediately - no need to restart the app.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
