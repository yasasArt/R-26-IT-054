import { net, protocol } from "electron";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { backendManager } from "./backend-manager";

export const APP_PROTOCOL = "garment";
export const APP_ORIGIN = `${APP_PROTOCOL}://app`;
export const STREAM_PROTOCOL = "garmentstream";

let packagedProtocolRegistered = false;
let streamProtocolRegistered = false;
export function registerApplicationProtocolScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: APP_PROTOCOL,
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        corsEnabled: true,
        stream: true,
      },
    },
    {
      scheme: STREAM_PROTOCOL,
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        corsEnabled: true,
        stream: true,
      },
    },
  ]);
}

export function registerWorkstationStreamProtocol(): void {
  if (streamProtocolRegistered) return;

  protocol.handle(STREAM_PROTOCOL, async (request) => {
    try {
      const requested = new URL(request.url);
      const match = /^\/session\/(\d+)\.mjpeg$/.exec(requested.pathname);

      if (request.method !== "GET" || requested.hostname !== "live" || !match) {
        return new Response("Unknown workstation video stream.", { status: 404 });
      }

      return await backendManager.openVisionStream(Number(match[1]));
    } catch {
      return new Response("The workstation video stream is unavailable.", { status: 503 });
    }
  });

  streamProtocolRegistered = true;
}

export function registerPackagedRendererProtocol(rendererEntryUrl: string): void {
  if (packagedProtocolRegistered) {
    return;
  }

  const rendererEntryFile = fileURLToPath(rendererEntryUrl);
  const rendererDirectory = path.dirname(path.dirname(rendererEntryFile));

  protocol.handle(APP_PROTOCOL, async (request) => {
    const requestUrl = new URL(request.url);

    if (requestUrl.hostname !== "app") {
      return new Response("Unknown application host.", { status: 404 });
    }

    const relativePath = decodeURIComponent(requestUrl.pathname)
      .replace(/^[/\\]+/, "")
      .replace(/\0/g, "");

    const requestedFile = path.resolve(rendererDirectory, relativePath || "index.html");
    const rendererRoot = `${rendererDirectory}${path.sep}`;

    if (requestedFile !== rendererDirectory && !requestedFile.startsWith(rendererRoot)) {
      return new Response("Invalid application resource path.", { status: 403 });
    }

    return net.fetch(pathToFileURL(requestedFile).toString());
  });

  packagedProtocolRegistered = true;
}

export function isTrustedRendererUrl(url: string, developmentEntryUrl: string): boolean {
  try {
    const requestedUrl = new URL(url);

    if (requestedUrl.protocol === `${APP_PROTOCOL}:`) {
      return requestedUrl.hostname === "app";
    }

    const developmentUrl = new URL(developmentEntryUrl);

    if (!["http:", "https:"].includes(developmentUrl.protocol)) {
      return false;
    }

    return (
      ["http:", "https:"].includes(requestedUrl.protocol) &&
      requestedUrl.origin === developmentUrl.origin
    );
  } catch {
    return false;
  }
}
