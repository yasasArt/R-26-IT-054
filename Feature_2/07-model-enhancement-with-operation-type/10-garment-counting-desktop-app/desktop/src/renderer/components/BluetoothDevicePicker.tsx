import type { DiscoveredBluetoothDevice } from "../../shared/types";
import { Icon } from "./Icon";

interface Props {
  devices: DiscoveredBluetoothDevice[];
  selectingDeviceId: string | null;
  onSelect: (deviceId: string) => void;
  onCancel: () => void;
}

export function BluetoothDevicePicker({ devices, selectingDeviceId, onSelect, onCancel }: Props) {
  const recognizedCount = devices.filter((device) => device.compatible).length;

  return (
    <div className="bluetooth-picker-backdrop" role="presentation">
      <section
        className="bluetooth-picker-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bluetooth-picker-title"
      >
        <header className="bluetooth-picker-heading">
          <span className="bluetooth-picker-icon"><Icon name="bluetooth" size={23} /></span>
          <div>
            <span className="eyebrow">OPERATOR CONTROLLER</span>
            <h2 id="bluetooth-picker-title">Choose a Bluetooth device</h2>
          </div>
          <button type="button" className="icon-action" aria-label="Close Bluetooth device selection" onClick={onCancel}>
            <Icon name="close" size={17} />
          </button>
        </header>

        <p className="bluetooth-picker-description">
          Select your sewing controller from nearby Bluetooth devices. If it does not appear, press Button A on the ESP32-C3.
        </p>

        <div className="bluetooth-picker-status">
          <span className="bluetooth-picker-pulse" />
          <span>
            {devices.length
              ? `${devices.length} device${devices.length === 1 ? "" : "s"} found${recognizedCount ? ` · ${recognizedCount} named controller${recognizedCount === 1 ? "" : "s"}` : ""}`
              : "Searching for nearby Bluetooth devices…"}
          </span>
        </div>

        <div className="bluetooth-picker-list" aria-live="polite">
          {devices.length ? (
            devices.map((device) => (
              <button
                type="button"
                key={device.deviceId}
                className={`bluetooth-picker-device${device.compatible ? " is-compatible" : " is-incompatible"}`}
                onClick={() => onSelect(device.deviceId)}
                disabled={selectingDeviceId !== null}
              >
                <span className="bluetooth-device-icon"><Icon name="bluetooth" size={18} /></span>
                <span className="bluetooth-device-copy">
                  <strong>{device.deviceName}</strong>
                  <small>
                    {device.compatible
                      ? selectingDeviceId === device.deviceId
                        ? "Connecting to sewing controller…"
                        : "Recognized sewing controller"
                      : selectingDeviceId === device.deviceId
                        ? "Checking controller service…"
                        : "Select to verify controller compatibility"}
                  </small>
                </span>
                <Icon name={selectingDeviceId === device.deviceId ? "refresh" : "arrow-right"} size={17} className={selectingDeviceId === device.deviceId ? "spin" : undefined} />
              </button>
            ))
          ) : (
            <div className="bluetooth-picker-empty">
              <Icon name="bluetooth" size={28} />
              <strong>Looking for your controller</strong>
              <span>Make sure Bluetooth is enabled and the device is awake.</span>
            </div>
          )}
        </div>

        <footer className="bluetooth-picker-footer">
          <span>The app verifies the controller service after you select a device.</span>
          <button type="button" className="action-button action-secondary" onClick={onCancel}>
            Cancel
          </button>
        </footer>
      </section>
    </div>
  );
}
