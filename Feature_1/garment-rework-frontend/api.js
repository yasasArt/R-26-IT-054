export async function reworkRequest(method, path, body) {
  return globalThis.window.garmentDesktop.reworkRequest({
    method,
    path,
    body
  });
}

// Garment Rework camera feed
export const REWORK_STREAM_URL =
  "http://127.0.0.1:8011/video_feed";