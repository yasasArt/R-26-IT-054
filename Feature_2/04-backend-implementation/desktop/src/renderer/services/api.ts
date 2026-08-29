import type {
  ApiRequest,
  ApiResult,
  BinaryApiResult,
  JsonValue,
  VisionStartInput,
} from "../../shared/api-types.js";

export class GarmentApiClient {
  private previewObjectUrl: string | undefined;

  request<T extends JsonValue>(input: ApiRequest): Promise<ApiResult> {
    return window.garmentApi.request(input);
  }

  async previewFrameUrl(): Promise<string> {
    const frame: BinaryApiResult = await window.garmentApi.vision.previewFrame();
    if (!frame.contentType.startsWith("image/jpeg")) {
      throw new Error("Backend preview returned an unexpected content type");
    }
    if (this.previewObjectUrl) URL.revokeObjectURL(this.previewObjectUrl);
    const ownedBytes = new Uint8Array(frame.bytes.byteLength);
    ownedBytes.set(frame.bytes);
    this.previewObjectUrl = URL.createObjectURL(
      new Blob([ownedBytes.buffer], { type: frame.contentType }),
    );
    return this.previewObjectUrl;
  }

  releasePreviewUrl(): void {
    if (this.previewObjectUrl) URL.revokeObjectURL(this.previewObjectUrl);
    this.previewObjectUrl = undefined;
  }

  startVision(input: VisionStartInput): Promise<ApiResult> {
    return window.garmentApi.vision.start(input);
  }

  stopVision(): Promise<ApiResult> {
    return window.garmentApi.vision.stop();
  }

  visionStatus(): Promise<ApiResult> {
    return window.garmentApi.vision.status();
  }
}

export const api = new GarmentApiClient();
