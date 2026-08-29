export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface ApiRequest {
  method: HttpMethod;
  path: string;
  query?: Record<string, JsonPrimitive>;
  body?: { [key: string]: JsonValue };
}

export interface JsonApiResult {
  kind: "json";
  status: number;
  data: JsonValue;
}

export interface BinaryApiResult {
  kind: "binary";
  status: number;
  bytes: Uint8Array;
  contentType: string;
  filename?: string;
}

export type ApiResult = JsonApiResult | BinaryApiResult;

export interface VisionStartInput {
  sessionId: number;
  sourceType: "CAMERA" | "VIDEO";
  cameraIndex?: number;
  videoId?: string;
}

export interface PhysicalControllerEvent {
  sessionId: number;
  eventKey: string;
  eventType: "REWORK" | "DOWNTIME" | "RESET";
  occurredAt: string;
  deviceName?: string;
  deviceId?: string;
}

export interface GarmentDesktopApi {
  request(input: ApiRequest): Promise<ApiResult>;
  vision: {
    start(input: VisionStartInput): Promise<ApiResult>;
    stop(): Promise<ApiResult>;
    status(): Promise<ApiResult>;
    previewFrame(): Promise<BinaryApiResult>;
    selectAndUploadVideo(): Promise<ApiResult | null>;
    deleteVideo(videoId: string): Promise<ApiResult>;
  };
}

declare global {
  interface Window {
    garmentApi: GarmentDesktopApi;
  }
}
