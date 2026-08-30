import { contextBridge, ipcRenderer } from "electron";

import type {
  ApiRequest,
  ApiResult,
  GarmentDesktopApi,
  VisionStartInput,
} from "../shared/api-types.js";

const garmentApi: GarmentDesktopApi = Object.freeze({
  request: (input: ApiRequest): Promise<ApiResult> =>
    ipcRenderer.invoke("garment:api", input),
  vision: Object.freeze({
    start: (input: VisionStartInput): Promise<ApiResult> =>
      ipcRenderer.invoke("garment:vision:start", input),
    stop: (): Promise<ApiResult> => ipcRenderer.invoke("garment:vision:stop"),
    status: (): Promise<ApiResult> => ipcRenderer.invoke("garment:vision:status"),
    previewFrame: () => ipcRenderer.invoke("garment:vision:preview-frame"),
    selectAndUploadVideo: () => ipcRenderer.invoke("garment:vision:choose-video"),
    deleteVideo: (videoId: string): Promise<ApiResult> =>
      ipcRenderer.invoke("garment:vision:delete-video", videoId),
  }),
});

contextBridge.exposeInMainWorld("garmentApi", garmentApi);

