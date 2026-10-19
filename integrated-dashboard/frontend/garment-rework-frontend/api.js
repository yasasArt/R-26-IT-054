export async function reworkRequest(method, path, body) {
  return globalThis.window.garmentDesktop.reworkRequest({ method, path, body });
}

export const REWORK_STREAM_URL = "garmentrework://live/video.mjpeg";
