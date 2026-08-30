import assert from "node:assert/strict";
import test from "node:test";

import {
  BluetoothControllerApproval,
  CONTROLLER_DEVICE_NAME,
  CONTROLLER_EVENT_CHARACTERISTIC_UUID,
  CONTROLLER_SERVICE_UUID,
  describeDiscoveredBluetoothDevice,
  HARDWARE_BUTTON_EVENTS,
  isSupportedControllerName,
  parseControllerNotification,
  reconnectDelayMilliseconds,
  sortDiscoveredBluetoothDevices,
} from "../src/shared/bluetooth-policy.ts";
import { allowsRendererBackendRequest } from "../src/shared/ipc-policy.ts";

test("Bluetooth integration matches the existing ESP32-C3 firmware exactly", () => {
  assert.equal(CONTROLLER_DEVICE_NAME, "GarmentCounter-IoT");
  assert.equal(CONTROLLER_SERVICE_UUID, "7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e");
  assert.equal(CONTROLLER_EVENT_CHARACTERISTIC_UUID, "8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a");
  assert.deepEqual(HARDWARE_BUTTON_EVENTS, ["REWORK", "DOWNTIME", "RESET"]);
});

test("the advertised name is used as a helpful recognition hint", () => {
  assert.equal(isSupportedControllerName("GarmentCounter-IoT"), true);
  assert.equal(isSupportedControllerName("Unknown controller"), false);
  assert.equal(isSupportedControllerName("GarmentCounter-IoT-copy"), false);
  assert.equal(isSupportedControllerName(undefined), false);
});

test("the device picker prioritizes a named controller but preserves all nearby choices", () => {
  const headphones = describeDiscoveredBluetoothDevice("device-01", "Wireless headphones");
  const controller = describeDiscoveredBluetoothDevice("device-02", "GarmentCounter-IoT");
  const unnamed = describeDiscoveredBluetoothDevice("device-03", "");

  assert.equal(headphones.compatible, false);
  assert.equal(controller.compatible, true);
  assert.equal(unnamed.deviceName, "Unnamed Bluetooth device");
  assert.deepEqual(
    sortDiscoveredBluetoothDevices([headphones, controller, unnamed]).map((device) => device.deviceId),
    ["device-02", "device-03", "device-01"],
  );
});

test("an approved native Bluetooth selection can bind a different macOS Web Bluetooth identifier", () => {
  const approval = new BluetoothControllerApproval();

  assert.equal(approval.bindRuntimeDevice("web-bluetooth-origin-id"), false);
  approval.select("electron-native-device-id");
  assert.equal(approval.isApproved("web-bluetooth-origin-id"), false);
  assert.equal(approval.bindRuntimeDevice("web-bluetooth-origin-id"), true);
  assert.equal(approval.isApproved("web-bluetooth-origin-id"), true);
  assert.equal(approval.isApproved("electron-native-device-id"), false);
  assert.equal(approval.bindRuntimeDevice("different-controller"), false);
});

test("choosing another Bluetooth device clears the previous runtime authorization", () => {
  const approval = new BluetoothControllerApproval();

  approval.select("first-native-device");
  assert.equal(approval.bindRuntimeDevice("first-runtime-device"), true);
  approval.select("second-native-device");
  assert.equal(approval.isApproved("first-runtime-device"), false);
  assert.equal(approval.bindRuntimeDevice("second-runtime-device"), true);
  approval.clear();
  assert.equal(approval.isApproved("second-runtime-device"), false);
  assert.equal(approval.bindRuntimeDevice("unexpected-device"), false);
});

test("real firmware notifications are normalized without inventing unsupported actions", () => {
  assert.equal(parseControllerNotification(" REWORK\0"), "REWORK");
  assert.equal(parseControllerNotification("downtime\n"), "DOWNTIME");
  assert.equal(parseControllerNotification("RESET"), "RESET");
  assert.equal(parseControllerNotification("CONNECT_REQUEST"), "CONNECT_REQUEST");
  assert.equal(parseControllerNotification("SHUTDOWN"), "SHUTDOWN");
  assert.equal(parseControllerNotification("READY"), "READY");
  assert.equal(parseControllerNotification("DELETE_SESSION"), null);
});

test("automatic Bluetooth reconnect uses bounded exponential backoff", () => {
  assert.equal(reconnectDelayMilliseconds(1), 1_000);
  assert.equal(reconnectDelayMilliseconds(2), 2_000);
  assert.equal(reconnectDelayMilliseconds(3), 4_000);
  assert.equal(reconnectDelayMilliseconds(5), 15_000);
  assert.equal(reconnectDelayMilliseconds(100), 15_000);
});

test("the normal renderer bridge cannot forge physical Bluetooth connection or button events", () => {
  assert.equal(
    allowsRendererBackendRequest({ method: "POST", path: "/api/iot/connection", body: { connected: true } }),
    false,
  );
  assert.equal(
    allowsRendererBackendRequest({ method: "POST", path: "/api/iot-events", body: { event_type: "RESET" } }),
    false,
  );
  assert.equal(
    allowsRendererBackendRequest({
      method: "POST", path: "/api/iot-events", body: { event_type: "RESET", event_source: "HARDWARE" },
    }),
    false,
  );
  assert.equal(
    allowsRendererBackendRequest({
      method: "POST", path: "/api/iot-events", body: { event_type: "RESET", event_source: "VALIDATION" },
    }),
    true,
  );
  assert.equal(allowsRendererBackendRequest({ method: "GET", path: "/api/iot-events" }), true);
});
