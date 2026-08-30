/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./src/main/backend-manager.ts"
/*!*************************************!*\
  !*** ./src/main/backend-manager.ts ***!
  \*************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   BackendManager: () => (/* binding */ BackendManager),
/* harmony export */   backendManager: () => (/* binding */ backendManager)
/* harmony export */ });
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var node_child_process__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! node:child_process */ "node:child_process");
/* harmony import */ var node_child_process__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(node_child_process__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var node_crypto__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! node:crypto */ "node:crypto");
/* harmony import */ var node_crypto__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(node_crypto__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var node_fs__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! node:fs */ "node:fs");
/* harmony import */ var node_fs__WEBPACK_IMPORTED_MODULE_3___default = /*#__PURE__*/__webpack_require__.n(node_fs__WEBPACK_IMPORTED_MODULE_3__);
/* harmony import */ var node_net__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! node:net */ "node:net");
/* harmony import */ var node_net__WEBPACK_IMPORTED_MODULE_4___default = /*#__PURE__*/__webpack_require__.n(node_net__WEBPACK_IMPORTED_MODULE_4__);
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_5___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_5__);
/* harmony import */ var _shared_backend_connection_policy__WEBPACK_IMPORTED_MODULE_6__ = __webpack_require__(/*! ../shared/backend-connection-policy */ "./src/shared/backend-connection-policy.ts");
/* harmony import */ var _readiness_service__WEBPACK_IMPORTED_MODULE_7__ = __webpack_require__(/*! ./readiness-service */ "./src/main/readiness-service.ts");
/* harmony import */ var _sidecar_launch__WEBPACK_IMPORTED_MODULE_8__ = __webpack_require__(/*! ./sidecar-launch */ "./src/main/sidecar-launch.ts");









const DEVELOPMENT_STARTUP_TIMEOUT_MS = 30_000;
const PACKAGED_STARTUP_TIMEOUT_MS = 90_000;
const HEALTH_POLL_INTERVAL_MS = 250;
function allocateLocalPort() {
    return new Promise((resolve, reject) => {
        const server = (0,node_net__WEBPACK_IMPORTED_MODULE_4__.createServer)();
        server.once("error", reject);
        server.listen(0, "127.0.0.1", () => {
            const address = server.address();
            if (!address || typeof address === "string") {
                server.close();
                reject(new Error("A localhost port could not be allocated for the application service."));
                return;
            }
            const { port } = address;
            server.close((error) => (error ? reject(error) : resolve(port)));
        });
    });
}
function pause(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
class BackendManager {
    child = null;
    port = null;
    token = null;
    status = {
        state: "stopped",
        message: "The local application service has not started yet.",
    };
    recentLogs = [];
    getStatus() {
        return { ...this.status };
    }
    async start() {
        if (this.child || this.status.state === "starting")
            return;
        this.status = { state: "starting", message: "Starting the local application service…" };
        this.port = await allocateLocalPort();
        this.token = (0,node_crypto__WEBPACK_IMPORTED_MODULE_2__.randomBytes)(32).toString("hex");
        let launchPlan;
        try {
            launchPlan = (0,_sidecar_launch__WEBPACK_IMPORTED_MODULE_8__.resolveSidecarLaunchPlan)({
                packaged: electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged,
                applicationPath: electron__WEBPACK_IMPORTED_MODULE_0__.app.getAppPath(),
                resourcesPath: process.resourcesPath,
                platform: process.platform,
                configuredPython: process.env.GARMENT_COUNTER_PYTHON,
                fileExists: node_fs__WEBPACK_IMPORTED_MODULE_3__.existsSync,
            });
        }
        catch (error) {
            this.status = {
                state: "error",
                message: error instanceof Error ? error.message : "The application service could not be located.",
            };
            throw error;
        }
        const userDataDirectory = electron__WEBPACK_IMPORTED_MODULE_0__.app.getPath("userData");
        this.child = (0,node_child_process__WEBPACK_IMPORTED_MODULE_1__.spawn)(launchPlan.executable, launchPlan.arguments, {
            cwd: launchPlan.workingDirectory,
            stdio: "pipe",
            windowsHide: true,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: "1",
                GARMENT_COUNTER_PORT: String(this.port),
                GARMENT_COUNTER_AUTH_TOKEN: this.token,
                GARMENT_COUNTER_DATA_DIR: userDataDirectory,
                GARMENT_COUNTER_MODEL_DIR: (0,_readiness_service__WEBPACK_IMPORTED_MODULE_7__.getModelResourceDirectory)(),
                GARMENT_COUNTER_ENVIRONMENT: electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged ? "production" : "development",
                YOLO_CONFIG_DIR: node_path__WEBPACK_IMPORTED_MODULE_5___default().join(userDataDirectory, "ultralytics"),
                MPLCONFIGDIR: node_path__WEBPACK_IMPORTED_MODULE_5___default().join(userDataDirectory, "matplotlib"),
                PYTORCH_ENABLE_MPS_FALLBACK: "1",
            },
        });
        this.child.stdout.on("data", (data) => this.rememberLog(data));
        this.child.stderr.on("data", (data) => this.rememberLog(data));
        this.child.once("error", (error) => {
            this.status = {
                state: "error",
                message: electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged
                    ? `The bundled application service could not start. Reinstall Garment Counter if the problem continues. ${error.message}`
                    : `The local service could not start. Check Python dependencies. ${error.message}`,
            };
            this.child = null;
        });
        this.child.once("exit", (code) => {
            if (this.status.state !== "stopped") {
                const finalMessage = this.recentLogs.at(-1);
                this.status = {
                    state: "error",
                    message: finalMessage ||
                        `The local application service exited unexpectedly${code === null ? "." : ` (${code}).`}`,
                };
            }
            this.child = null;
        });
        const deadline = Date.now() + (electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged ? PACKAGED_STARTUP_TIMEOUT_MS : DEVELOPMENT_STARTUP_TIMEOUT_MS);
        while (Date.now() < deadline) {
            if (this.status.state === "error") {
                throw new Error(this.status.message);
            }
            try {
                const response = await fetch(`${this.baseUrl()}/api/health`, {
                    headers: { Authorization: `Bearer ${this.token}` },
                });
                if (response.ok) {
                    this.status = { state: "ready", message: "The local application service is ready." };
                    return;
                }
            }
            catch {
                // The Python process may still be importing its application dependencies.
            }
            await pause(HEALTH_POLL_INTERVAL_MS);
        }
        this.status = {
            state: "error",
            message: electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged
                ? "The bundled application service did not become ready. Restart Garment Counter or reinstall the application."
                : "The local application service did not become ready. Check the backend setup guide.",
        };
        this.stopChild();
        throw new Error(this.status.message);
    }
    async request(request) {
        if (this.status.state !== "ready" || !this.port || !this.token) {
            throw new Error(this.status.message);
        }
        if (!["GET", "POST", "PUT"].includes(request.method)) {
            throw new Error("The requested application-service action is not allowed.");
        }
        if (!request.path.startsWith("/api/") || request.path.startsWith("//")) {
            throw new Error("Only local application-service API routes are allowed.");
        }
        const destination = new URL(request.path, this.baseUrl());
        if (destination.origin !== this.baseUrl() || !destination.pathname.startsWith("/api/")) {
            throw new Error("The requested service destination is not allowed.");
        }
        const response = await this.fetchLocal(destination, {
            method: request.method,
            headers: {
                Authorization: `Bearer ${this.token}`,
                ...(request.body === undefined ? {} : { "Content-Type": "application/json" }),
            },
            body: request.body === undefined ? undefined : JSON.stringify(request.body),
        }, `${request.method} ${request.path}`);
        if (!response.ok) {
            const errorPayload = (await response.json().catch(() => null));
            const detail = errorPayload?.detail;
            const message = typeof detail === "string"
                ? detail
                : detail?.message
                    ? `${detail.message}${detail.blockers?.length ? ` ${detail.blockers.join(", ")}.` : ""}`
                    : `The application service rejected this request (${response.status}).`;
            console.error(`[BACKEND REQUEST FAILED] ${request.method} ${request.path}: ${message}`);
            throw new Error(`${request.method} ${request.path}: ${message}`);
        }
        return (await response.json());
    }
    async downloadAnalytics(query) {
        if (this.status.state !== "ready" || !this.port || !this.token) {
            throw new Error(this.status.message);
        }
        if (query && !query.startsWith("?")) {
            throw new Error("Invalid analytics filters.");
        }
        const destination = new URL(`/api/analytics/export.xlsx${query}`, this.baseUrl());
        const response = await this.fetchLocal(destination, {
            headers: { Authorization: `Bearer ${this.token}` },
        }, "GET /api/analytics/export.xlsx");
        if (!response.ok) {
            throw new Error("The filtered Excel report could not be generated.");
        }
        return response.arrayBuffer();
    }
    async openVisionStream(sessionId) {
        if (this.status.state !== "ready" || !this.port || !this.token) {
            throw new Error(this.status.message);
        }
        if (!Number.isSafeInteger(sessionId) || sessionId < 1) {
            throw new Error("The requested workstation stream is invalid.");
        }
        const response = await this.fetchLocal(`${this.baseUrl()}/api/vision/stream/${sessionId}`, {
            headers: { Authorization: `Bearer ${this.token}` },
        }, `GET /api/vision/stream/${sessionId}`);
        if (!response.ok || !response.body) {
            throw new Error("The authenticated workstation camera stream is unavailable.");
        }
        return new Response(response.body, {
            status: 200,
            headers: {
                "Content-Type": response.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-store",
            },
        });
    }
    stop() {
        this.status = { state: "stopped", message: "The local application service has stopped." };
        this.stopChild();
        this.token = null;
        this.port = null;
    }
    baseUrl() {
        return `http://127.0.0.1:${this.port}`;
    }
    async fetchLocal(destination, options, operation) {
        const method = options.method || "GET";
        for (let attempt = 0;; attempt += 1) {
            try {
                return await fetch(destination, options);
            }
            catch (caughtError) {
                if (this.status.state === "ready" &&
                    this.child &&
                    !this.child.killed &&
                    (0,_shared_backend_connection_policy__WEBPACK_IMPORTED_MODULE_6__.shouldRetryBackendConnection)(method, attempt, caughtError)) {
                    await pause(150 * (attempt + 1));
                    continue;
                }
                const code = (0,_shared_backend_connection_policy__WEBPACK_IMPORTED_MODULE_6__.backendConnectionErrorCode)(caughtError);
                const detail = code ? ` (${code})` : "";
                const message = `${operation}: The local application service connection was interrupted${detail}.`;
                console.error(`[BACKEND CONNECTION FAILED] ${message}`);
                throw new Error(message, { cause: caughtError });
            }
        }
    }
    stopChild() {
        if (!this.child)
            return;
        const child = this.child;
        child.kill();
        const forceClose = setTimeout(() => {
            if (!child.killed)
                child.kill("SIGKILL");
        }, 2_500);
        forceClose.unref();
    }
    rememberLog(data) {
        const message = data.toString("utf8").trim();
        if (!message)
            return;
        if (/traceback|exception|error:/i.test(message)) {
            console.error("[PYTHON BACKEND ERROR]\n", message);
        }
        this.recentLogs.push(message);
        this.recentLogs = this.recentLogs.slice(-8);
    }
}
const backendManager = new BackendManager();


/***/ },

/***/ "./src/main/ipc.ts"
/*!*************************!*\
  !*** ./src/main/ipc.ts ***!
  \*************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   registerDesktopIpc: () => (/* binding */ registerDesktopIpc)
/* harmony export */ });
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var node_fs_promises__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! node:fs/promises */ "node:fs/promises");
/* harmony import */ var node_fs_promises__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(node_fs_promises__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var _shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../shared/ipc-channels */ "./src/shared/ipc-channels.ts");
/* harmony import */ var _shared_ipc_policy__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! ../shared/ipc-policy */ "./src/shared/ipc-policy.ts");
/* harmony import */ var _shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(/*! ../shared/bluetooth-policy */ "./src/shared/bluetooth-policy.ts");
/* harmony import */ var _backend_manager__WEBPACK_IMPORTED_MODULE_6__ = __webpack_require__(/*! ./backend-manager */ "./src/main/backend-manager.ts");
/* harmony import */ var _protocol__WEBPACK_IMPORTED_MODULE_7__ = __webpack_require__(/*! ./protocol */ "./src/main/protocol.ts");
/* harmony import */ var _readiness_service__WEBPACK_IMPORTED_MODULE_8__ = __webpack_require__(/*! ./readiness-service */ "./src/main/readiness-service.ts");
/* harmony import */ var _window_manager__WEBPACK_IMPORTED_MODULE_9__ = __webpack_require__(/*! ./window-manager */ "./src/main/window-manager.ts");










function assertTrustedSender(event, resolveWindow) {
    const window = resolveWindow();
    if (!window || window.isDestroyed()) {
        throw new Error("The desktop application window is unavailable.");
    }
    if (event.sender.id !== window.webContents.id) {
        throw new Error("IPC request rejected: unknown renderer.");
    }
    const senderUrl = event.senderFrame?.url || event.sender.getURL();
    if (!(0,_protocol__WEBPACK_IMPORTED_MODULE_7__.isTrustedRendererUrl)(senderUrl, 'http://localhost:3000/main_window/index.html')) {
        throw new Error("IPC request rejected: untrusted renderer origin.");
    }
    return window;
}
function registerDesktopIpc(resolveWindow) {
    let activeHardwareDeviceId = null;
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.appInfo, (event) => {
        assertTrustedSender(event, resolveWindow);
        return (0,_readiness_service__WEBPACK_IMPORTED_MODULE_8__.getDesktopAppInfo)();
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.readiness, async (event) => {
        assertTrustedSender(event, resolveWindow);
        if (_backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.getStatus().state !== "ready") {
            return (0,_readiness_service__WEBPACK_IMPORTED_MODULE_8__.checkPhaseOneReadiness)();
        }
        return _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.request({ method: "GET", path: "/api/readiness" });
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.backendStatus, (event) => {
        assertTrustedSender(event, resolveWindow);
        return _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.getStatus();
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.backendRequest, async (event, request) => {
        assertTrustedSender(event, resolveWindow);
        if (!request || typeof request !== "object" || typeof request.path !== "string") {
            throw new Error("Invalid local application-service request.");
        }
        if (!(0,_shared_ipc_policy__WEBPACK_IMPORTED_MODULE_4__.allowsRendererBackendRequest)(request)) {
            throw new Error("The desktop interface cannot impersonate a physical controller or vision engine.");
        }
        return _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.request(request);
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.exportAnalytics, async (event, query) => {
        const window = assertTrustedSender(event, resolveWindow);
        if (typeof query !== "string") {
            throw new Error("Invalid analytics export request.");
        }
        const date = new Date().toISOString().slice(0, 10);
        const parameters = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
        const sessionId = parameters.get("session_id");
        const employeeId = parameters.get("employee_id");
        const reportScope = sessionId
            ? `Session_${sessionId}`
            : employeeId
                ? `Employee_${employeeId}`
                : "Filtered";
        const destination = await electron__WEBPACK_IMPORTED_MODULE_0__.dialog.showSaveDialog(window, {
            title: "Save production analytics report",
            defaultPath: `Garment_Production_Analytics_${reportScope}_${date}.xlsx`,
            filters: [{ name: "Microsoft Excel workbook", extensions: ["xlsx"] }],
        });
        if (destination.canceled || !destination.filePath) {
            return { canceled: true };
        }
        const workbook = await _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.downloadAnalytics(query);
        await (0,node_fs_promises__WEBPACK_IMPORTED_MODULE_1__.writeFile)(destination.filePath, Buffer.from(workbook));
        return { canceled: false, filePath: destination.filePath };
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.selectValidationVideo, async (event) => {
        const window = assertTrustedSender(event, resolveWindow);
        const selected = await electron__WEBPACK_IMPORTED_MODULE_0__.dialog.showOpenDialog(window, {
            title: "Choose a recorded sewing-workstation video",
            properties: ["openFile"],
            filters: [
                { name: "Workstation video", extensions: ["mp4", "mov", "avi", "mkv", "m4v", "webm"] },
            ],
        });
        if (selected.canceled || !selected.filePaths[0]) {
            return { canceled: true };
        }
        return {
            canceled: false,
            filePath: selected.filePaths[0],
            fileName: node_path__WEBPACK_IMPORTED_MODULE_2___default().basename(selected.filePaths[0]),
        };
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.liveStreamUrl, (event, sessionId) => {
        assertTrustedSender(event, resolveWindow);
        if (!Number.isSafeInteger(sessionId) || sessionId < 1) {
            throw new Error("Invalid workstation video request.");
        }
        return `${_protocol__WEBPACK_IMPORTED_MODULE_7__.STREAM_PROTOCOL}://live/session/${sessionId}.mjpeg`;
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.iotSelectDevice, (event, deviceId) => {
        assertTrustedSender(event, resolveWindow);
        if (typeof deviceId !== "string" || !deviceId) {
            throw new Error("Select an available Bluetooth device before connecting.");
        }
        ;(0,_window_manager__WEBPACK_IMPORTED_MODULE_9__.selectBluetoothController)(deviceId);
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.iotCancelSelection, (event) => {
        assertTrustedSender(event, resolveWindow);
        (0,_window_manager__WEBPACK_IMPORTED_MODULE_9__.cancelBluetoothControllerSelection)();
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.iotConnection, async (event, input) => {
        assertTrustedSender(event, resolveWindow);
        if (!input ||
            typeof input.device_id !== "string" ||
            !input.device_id ||
            typeof input.device_name !== "string" ||
            !input.device_name.trim() ||
            typeof input.connected !== "boolean" ||
            typeof input.notifications_active !== "boolean") {
            throw new Error("The physical controller connection could not be verified.");
        }
        const approved = input.connected && input.notifications_active
            ? (0,_window_manager__WEBPACK_IMPORTED_MODULE_9__.bindApprovedBluetoothController)(input.device_id)
            : (0,_window_manager__WEBPACK_IMPORTED_MODULE_9__.hasApprovedBluetoothController)(input.device_id);
        if (!approved) {
            throw new Error("Select the controller in the Bluetooth window before connecting it.");
        }
        const result = await _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.request({
            method: "POST",
            path: "/api/iot/connection",
            body: input,
        });
        activeHardwareDeviceId =
            input.connected && input.notifications_active ? input.device_id : null;
        return result;
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.iotHardwareEvent, async (event, input) => {
        assertTrustedSender(event, resolveWindow);
        if (!input ||
            typeof input.device_id !== "string" ||
            !input.device_id ||
            input.device_id !== activeHardwareDeviceId ||
            typeof input.device_name !== "string" ||
            !input.device_name.trim() ||
            !(0,_window_manager__WEBPACK_IMPORTED_MODULE_9__.hasApprovedBluetoothController)(input.device_id) ||
            !_shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_5__.HARDWARE_BUTTON_EVENTS.some((allowed) => allowed === input.event_type)) {
            throw new Error("The physical operator button event could not be verified.");
        }
        return _backend_manager__WEBPACK_IMPORTED_MODULE_6__.backendManager.request({
            method: "POST",
            path: "/api/iot-events",
            body: {
                event_type: input.event_type,
                event_source: "HARDWARE",
                device_name: input.device_name,
                payload: { device_id: input.device_id, ...input.payload },
            },
        });
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.minimizeWindow, (event) => {
        assertTrustedSender(event, resolveWindow).minimize();
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.toggleMaximizeWindow, (event) => {
        const window = assertTrustedSender(event, resolveWindow);
        if (window.isMaximized()) {
            window.unmaximize();
        }
        else {
            window.maximize();
        }
        return { maximized: window.isMaximized() };
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.ipcMain.handle(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.closeWindow, (event) => {
        assertTrustedSender(event, resolveWindow).close();
    });
}


/***/ },

/***/ "./src/main/protocol.ts"
/*!******************************!*\
  !*** ./src/main/protocol.ts ***!
  \******************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   APP_ORIGIN: () => (/* binding */ APP_ORIGIN),
/* harmony export */   APP_PROTOCOL: () => (/* binding */ APP_PROTOCOL),
/* harmony export */   STREAM_PROTOCOL: () => (/* binding */ STREAM_PROTOCOL),
/* harmony export */   isTrustedRendererUrl: () => (/* binding */ isTrustedRendererUrl),
/* harmony export */   registerApplicationProtocolScheme: () => (/* binding */ registerApplicationProtocolScheme),
/* harmony export */   registerPackagedRendererProtocol: () => (/* binding */ registerPackagedRendererProtocol),
/* harmony export */   registerWorkstationStreamProtocol: () => (/* binding */ registerWorkstationStreamProtocol)
/* harmony export */ });
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var node_url__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! node:url */ "node:url");
/* harmony import */ var node_url__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(node_url__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var _backend_manager__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./backend-manager */ "./src/main/backend-manager.ts");




const APP_PROTOCOL = "garment";
const APP_ORIGIN = `${APP_PROTOCOL}://app`;
const STREAM_PROTOCOL = "garmentstream";
let packagedProtocolRegistered = false;
let streamProtocolRegistered = false;
function registerApplicationProtocolScheme() {
    electron__WEBPACK_IMPORTED_MODULE_0__.protocol.registerSchemesAsPrivileged([
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
function registerWorkstationStreamProtocol() {
    if (streamProtocolRegistered)
        return;
    electron__WEBPACK_IMPORTED_MODULE_0__.protocol.handle(STREAM_PROTOCOL, async (request) => {
        try {
            const requested = new URL(request.url);
            const match = /^\/session\/(\d+)\.mjpeg$/.exec(requested.pathname);
            if (request.method !== "GET" || requested.hostname !== "live" || !match) {
                return new Response("Unknown workstation video stream.", { status: 404 });
            }
            return await _backend_manager__WEBPACK_IMPORTED_MODULE_3__.backendManager.openVisionStream(Number(match[1]));
        }
        catch {
            return new Response("The workstation video stream is unavailable.", { status: 503 });
        }
    });
    streamProtocolRegistered = true;
}
function registerPackagedRendererProtocol(rendererEntryUrl) {
    if (packagedProtocolRegistered) {
        return;
    }
    const rendererEntryFile = (0,node_url__WEBPACK_IMPORTED_MODULE_2__.fileURLToPath)(rendererEntryUrl);
    const rendererDirectory = node_path__WEBPACK_IMPORTED_MODULE_1___default().dirname(node_path__WEBPACK_IMPORTED_MODULE_1___default().dirname(rendererEntryFile));
    electron__WEBPACK_IMPORTED_MODULE_0__.protocol.handle(APP_PROTOCOL, async (request) => {
        const requestUrl = new URL(request.url);
        if (requestUrl.hostname !== "app") {
            return new Response("Unknown application host.", { status: 404 });
        }
        const relativePath = decodeURIComponent(requestUrl.pathname)
            .replace(/^[/\\]+/, "")
            .replace(/\0/g, "");
        const requestedFile = node_path__WEBPACK_IMPORTED_MODULE_1___default().resolve(rendererDirectory, relativePath || "index.html");
        const rendererRoot = `${rendererDirectory}${(node_path__WEBPACK_IMPORTED_MODULE_1___default().sep)}`;
        if (requestedFile !== rendererDirectory && !requestedFile.startsWith(rendererRoot)) {
            return new Response("Invalid application resource path.", { status: 403 });
        }
        return electron__WEBPACK_IMPORTED_MODULE_0__.net.fetch((0,node_url__WEBPACK_IMPORTED_MODULE_2__.pathToFileURL)(requestedFile).toString());
    });
    packagedProtocolRegistered = true;
}
function isTrustedRendererUrl(url, developmentEntryUrl) {
    try {
        const requestedUrl = new URL(url);
        if (requestedUrl.protocol === `${APP_PROTOCOL}:`) {
            return requestedUrl.hostname === "app";
        }
        const developmentUrl = new URL(developmentEntryUrl);
        if (!["http:", "https:"].includes(developmentUrl.protocol)) {
            return false;
        }
        return (["http:", "https:"].includes(requestedUrl.protocol) &&
            requestedUrl.origin === developmentUrl.origin);
    }
    catch {
        return false;
    }
}


/***/ },

/***/ "./src/main/readiness-service.ts"
/*!***************************************!*\
  !*** ./src/main/readiness-service.ts ***!
  \***************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   checkPhaseOneReadiness: () => (/* binding */ checkPhaseOneReadiness),
/* harmony export */   getDesktopAppInfo: () => (/* binding */ getDesktopAppInfo),
/* harmony export */   getModelResourceDirectory: () => (/* binding */ getModelResourceDirectory)
/* harmony export */ });
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var node_fs__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! node:fs */ "node:fs");
/* harmony import */ var node_fs__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(node_fs__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var _shared_readiness__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../shared/readiness */ "./src/shared/readiness.ts");




function getModelResourceDirectory() {
    if (electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged) {
        return node_path__WEBPACK_IMPORTED_MODULE_2___default().join(process.resourcesPath, "models");
    }
    return node_path__WEBPACK_IMPORTED_MODULE_2___default().resolve(electron__WEBPACK_IMPORTED_MODULE_0__.app.getAppPath(), "..", "resources", "models");
}
function getDesktopAppInfo() {
    return {
        appName: electron__WEBPACK_IMPORTED_MODULE_0__.app.getName(),
        appVersion: electron__WEBPACK_IMPORTED_MODULE_0__.app.getVersion(),
        electronVersion: process.versions.electron,
        chromiumVersion: process.versions.chrome,
        nodeVersion: process.versions.node,
        platform: process.platform,
        architecture: process.arch,
        packaged: electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged,
        resourceDirectory: getModelResourceDirectory(),
        userDataDirectory: electron__WEBPACK_IMPORTED_MODULE_0__.app.getPath("userData"),
    };
}
function checkPhaseOneReadiness() {
    const modelDirectory = getModelResourceDirectory();
    return (0,_shared_readiness__WEBPACK_IMPORTED_MODULE_3__.createPhaseOneReadiness)({
        classifierCheckpointExists: (0,node_fs__WEBPACK_IMPORTED_MODULE_1__.existsSync)(node_path__WEBPACK_IMPORTED_MODULE_2___default().join(modelDirectory, "best_model.pt")),
        workstationCheckpointExists: (0,node_fs__WEBPACK_IMPORTED_MODULE_1__.existsSync)(node_path__WEBPACK_IMPORTED_MODULE_2___default().join(modelDirectory, "best.pt")),
    });
}


/***/ },

/***/ "./src/main/sidecar-launch.ts"
/*!************************************!*\
  !*** ./src/main/sidecar-launch.ts ***!
  \************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   resolveSidecarLaunchPlan: () => (/* binding */ resolveSidecarLaunchPlan)
/* harmony export */ });
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _shared_release_policy_ts__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ../shared/release-policy.ts */ "./src/shared/release-policy.ts");


function resolveSidecarLaunchPlan(context) {
    if (context.packaged) {
        const workingDirectory = node_path__WEBPACK_IMPORTED_MODULE_0___default().join(context.resourcesPath, "sidecar");
        const executable = node_path__WEBPACK_IMPORTED_MODULE_0___default().join(workingDirectory, (0,_shared_release_policy_ts__WEBPACK_IMPORTED_MODULE_1__.sidecarExecutableName)(context.platform));
        if (!context.fileExists(executable)) {
            throw new Error("The bundled application service is missing or damaged. Reinstall Garment Counter from the official installer.");
        }
        return { executable, arguments: [], workingDirectory, mode: "bundled" };
    }
    const workingDirectory = node_path__WEBPACK_IMPORTED_MODULE_0___default().resolve(context.applicationPath, "..", "backend");
    const virtualEnvironmentPython = context.platform === "win32"
        ? node_path__WEBPACK_IMPORTED_MODULE_0___default().join(workingDirectory, ".venv", "Scripts", "python.exe")
        : node_path__WEBPACK_IMPORTED_MODULE_0___default().join(workingDirectory, ".venv", "bin", "python");
    const executable = context.configuredPython ||
        (context.fileExists(virtualEnvironmentPython)
            ? virtualEnvironmentPython
            : context.platform === "win32"
                ? "python"
                : "python3");
    return { executable, arguments: ["-m", "app.main"], workingDirectory, mode: "development" };
}


/***/ },

/***/ "./src/main/window-manager.ts"
/*!************************************!*\
  !*** ./src/main/window-manager.ts ***!
  \************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   bindApprovedBluetoothController: () => (/* binding */ bindApprovedBluetoothController),
/* harmony export */   cancelBluetoothControllerSelection: () => (/* binding */ cancelBluetoothControllerSelection),
/* harmony export */   createMainWindow: () => (/* binding */ createMainWindow),
/* harmony export */   getMainWindow: () => (/* binding */ getMainWindow),
/* harmony export */   hasApprovedBluetoothController: () => (/* binding */ hasApprovedBluetoothController),
/* harmony export */   selectBluetoothController: () => (/* binding */ selectBluetoothController)
/* harmony export */ });
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! node:path */ "node:path");
/* harmony import */ var node_path__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(node_path__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var _shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ../shared/bluetooth-policy */ "./src/shared/bluetooth-policy.ts");
/* harmony import */ var _shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../shared/ipc-channels */ "./src/shared/ipc-channels.ts");
/* harmony import */ var _protocol__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! ./protocol */ "./src/main/protocol.ts");





let mainWindow = null;
const controllerApproval = new _shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_2__.BluetoothControllerApproval();
let pendingBluetoothSelection = null;
function hasApprovedBluetoothController(deviceId) {
    return controllerApproval.isApproved(deviceId);
}
function bindApprovedBluetoothController(deviceId) {
    return controllerApproval.bindRuntimeDevice(deviceId);
}
function getMainWindow() {
    return mainWindow;
}
function selectBluetoothController(deviceId) {
    const pending = pendingBluetoothSelection;
    if (!pending)
        throw new Error("Bluetooth device discovery is no longer active. Search again.");
    const device = pending.devices.get(deviceId);
    if (!device) {
        throw new Error("Select one of the available Bluetooth devices.");
    }
    controllerApproval.select(device.deviceId);
    clearBluetoothSelection(device.deviceId);
}
function cancelBluetoothControllerSelection() {
    clearBluetoothSelection("");
}
function clearBluetoothSelection(deviceId) {
    const pending = pendingBluetoothSelection;
    if (!pending)
        return;
    pendingBluetoothSelection = null;
    clearTimeout(pending.timeout);
    pending.callback(deviceId);
}
function protectWindowNavigation(window) {
    window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    window.webContents.on("will-navigate", (event, destinationUrl) => {
        if (!(0,_protocol__WEBPACK_IMPORTED_MODULE_4__.isTrustedRendererUrl)(destinationUrl, 'http://localhost:3000/main_window/index.html')) {
            event.preventDefault();
        }
    });
    window.webContents.on("will-attach-webview", (event) => {
        event.preventDefault();
    });
    window.webContents.on("select-bluetooth-device", (event, devices, callback) => {
        event.preventDefault();
        if (!(0,_protocol__WEBPACK_IMPORTED_MODULE_4__.isTrustedRendererUrl)(window.webContents.getURL(), 'http://localhost:3000/main_window/index.html')) {
            callback("");
            return;
        }
        if (!pendingBluetoothSelection) {
            pendingBluetoothSelection = {
                callback,
                devices: new Map(),
                timeout: setTimeout(() => clearBluetoothSelection(""), 30_000),
            };
        }
        for (const candidate of devices) {
            pendingBluetoothSelection.devices.set(candidate.deviceId, (0,_shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_2__.describeDiscoveredBluetoothDevice)(candidate.deviceId, candidate.deviceName));
        }
        const discovered = (0,_shared_bluetooth_policy__WEBPACK_IMPORTED_MODULE_2__.sortDiscoveredBluetoothDevices)(pendingBluetoothSelection.devices.values());
        window.webContents.send(_shared_ipc_channels__WEBPACK_IMPORTED_MODULE_3__.IPC_CHANNELS.iotDiscoveredDevices, discovered);
    });
    window.webContents.session.setPermissionRequestHandler((contents, permission, callback, details) => {
        const trustedWindow = contents.id === window.webContents.id &&
            (0,_protocol__WEBPACK_IMPORTED_MODULE_4__.isTrustedRendererUrl)(contents.getURL(), 'http://localhost:3000/main_window/index.html');
        const mediaTypes = "mediaTypes" in details ? details.mediaTypes : undefined;
        const cameraOnly = permission === "media" &&
            mediaTypes?.includes("video") === true &&
            mediaTypes?.includes("audio") !== true;
        callback(trustedWindow && cameraOnly);
    });
}
async function createMainWindow() {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.focus();
        return mainWindow;
    }
    mainWindow = new electron__WEBPACK_IMPORTED_MODULE_0__.BrowserWindow({
        title: "Garment Counter",
        width: 1480,
        height: 980,
        minWidth: 1060,
        minHeight: 720,
        show: false,
        icon: node_path__WEBPACK_IMPORTED_MODULE_1___default().join(electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged ? process.resourcesPath : node_path__WEBPACK_IMPORTED_MODULE_1___default().resolve(electron__WEBPACK_IMPORTED_MODULE_0__.app.getAppPath(), "..", "resources"), "branding", "icon.png"),
        backgroundColor: "#f4f6fa",
        titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "hidden",
        trafficLightPosition: process.platform === "darwin" ? { x: 19, y: 18 } : undefined,
        webPreferences: {
            preload: '/Users/nuwandharmarathna/Desktop/Projects/R-26-IT-054/Feature_2/06-garment-counting-desktop-app/desktop/.webpack/renderer/main_window/preload.js',
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: true,
            webSecurity: true,
            spellcheck: false,
        },
    });
    protectWindowNavigation(mainWindow);
    mainWindow.once("ready-to-show", () => {
        mainWindow?.show();
    });
    mainWindow.on("closed", () => {
        clearBluetoothSelection("");
        controllerApproval.clear();
        mainWindow = null;
    });
    if (electron__WEBPACK_IMPORTED_MODULE_0__.app.isPackaged) {
        (0,_protocol__WEBPACK_IMPORTED_MODULE_4__.registerPackagedRendererProtocol)('http://localhost:3000/main_window/index.html');
        await mainWindow.loadURL(`${_protocol__WEBPACK_IMPORTED_MODULE_4__.APP_ORIGIN}/main_window/index.html`);
    }
    else {
        await mainWindow.loadURL('http://localhost:3000/main_window/index.html');
    }
    return mainWindow;
}


/***/ },

/***/ "./src/shared/backend-connection-policy.ts"
/*!*************************************************!*\
  !*** ./src/shared/backend-connection-policy.ts ***!
  \*************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   backendConnectionErrorCode: () => (/* binding */ backendConnectionErrorCode),
/* harmony export */   shouldRetryBackendConnection: () => (/* binding */ shouldRetryBackendConnection)
/* harmony export */ });
const RETRYABLE_CONNECTION_CODES = new Set([
    "ECONNRESET",
    "ECONNREFUSED",
    "EPIPE",
    "UND_ERR_SOCKET",
    "UND_ERR_CONNECT_TIMEOUT",
]);
function backendConnectionErrorCode(error) {
    if (!error || typeof error !== "object")
        return null;
    const candidate = error;
    if (typeof candidate.code === "string")
        return candidate.code;
    if (candidate.cause && candidate.cause !== error) {
        return backendConnectionErrorCode(candidate.cause);
    }
    return null;
}
function shouldRetryBackendConnection(method, attempt, error) {
    if (method !== "GET" || attempt >= 2)
        return false;
    const code = backendConnectionErrorCode(error);
    return code !== null && RETRYABLE_CONNECTION_CODES.has(code);
}


/***/ },

/***/ "./src/shared/bluetooth-policy.ts"
/*!****************************************!*\
  !*** ./src/shared/bluetooth-policy.ts ***!
  \****************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   BluetoothControllerApproval: () => (/* binding */ BluetoothControllerApproval),
/* harmony export */   CONTROLLER_DEVICE_NAME: () => (/* binding */ CONTROLLER_DEVICE_NAME),
/* harmony export */   CONTROLLER_EVENT_CHARACTERISTIC_UUID: () => (/* binding */ CONTROLLER_EVENT_CHARACTERISTIC_UUID),
/* harmony export */   CONTROLLER_SERVICE_UUID: () => (/* binding */ CONTROLLER_SERVICE_UUID),
/* harmony export */   HARDWARE_BUTTON_EVENTS: () => (/* binding */ HARDWARE_BUTTON_EVENTS),
/* harmony export */   describeDiscoveredBluetoothDevice: () => (/* binding */ describeDiscoveredBluetoothDevice),
/* harmony export */   isSupportedControllerName: () => (/* binding */ isSupportedControllerName),
/* harmony export */   parseControllerNotification: () => (/* binding */ parseControllerNotification),
/* harmony export */   reconnectDelayMilliseconds: () => (/* binding */ reconnectDelayMilliseconds),
/* harmony export */   sortDiscoveredBluetoothDevices: () => (/* binding */ sortDiscoveredBluetoothDevices)
/* harmony export */ });
const CONTROLLER_DEVICE_NAME = "GarmentCounter-IoT";
const CONTROLLER_SERVICE_UUID = "7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e";
const CONTROLLER_EVENT_CHARACTERISTIC_UUID = "8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a";
const HARDWARE_BUTTON_EVENTS = ["REWORK", "DOWNTIME", "RESET"];
/**
 * Chromium intentionally exposes different Bluetooth identifiers to Electron's
 * native chooser and the origin-scoped Web Bluetooth API on some platforms.
 * Bind the first verified GATT connection to an explicit operator selection,
 * then reject every other runtime device until a new selection is made.
 */
class BluetoothControllerApproval {
    selectedDeviceId = null;
    runtimeDeviceId = null;
    select(deviceId) {
        this.selectedDeviceId = deviceId.trim() || null;
        this.runtimeDeviceId = null;
    }
    bindRuntimeDevice(deviceId) {
        const normalized = deviceId.trim();
        if (!this.selectedDeviceId || !normalized)
            return false;
        if (!this.runtimeDeviceId) {
            this.runtimeDeviceId = normalized;
        }
        return this.runtimeDeviceId === normalized;
    }
    isApproved(deviceId) {
        const normalized = deviceId.trim();
        return Boolean(normalized) && this.runtimeDeviceId === normalized;
    }
    clear() {
        this.selectedDeviceId = null;
        this.runtimeDeviceId = null;
    }
}
function isSupportedControllerName(name) {
    return name?.trim() === CONTROLLER_DEVICE_NAME;
}
function describeDiscoveredBluetoothDevice(deviceId, deviceName) {
    const name = deviceName?.trim() || "Unnamed Bluetooth device";
    return { deviceId, deviceName: name, compatible: isSupportedControllerName(name) };
}
function sortDiscoveredBluetoothDevices(devices) {
    return [...devices].sort((left, right) => Number(right.compatible) - Number(left.compatible) || left.deviceName.localeCompare(right.deviceName));
}
function parseControllerNotification(value) {
    const normalized = value.replace(/\0/g, "").trim().toUpperCase();
    if (normalized === "REWORK" ||
        normalized === "DOWNTIME" ||
        normalized === "RESET" ||
        normalized === "CONNECT_REQUEST" ||
        normalized === "SHUTDOWN" ||
        normalized === "READY") {
        return normalized;
    }
    return null;
}
function reconnectDelayMilliseconds(attempt) {
    return Math.min(15_000, 1_000 * 2 ** Math.max(0, attempt - 1));
}


/***/ },

/***/ "./src/shared/ipc-channels.ts"
/*!************************************!*\
  !*** ./src/shared/ipc-channels.ts ***!
  \************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   IPC_CHANNELS: () => (/* binding */ IPC_CHANNELS)
/* harmony export */ });
const IPC_CHANNELS = {
    appInfo: "desktop:app-info",
    readiness: "desktop:readiness",
    backendStatus: "backend:status",
    backendRequest: "backend:request",
    exportAnalytics: "analytics:export-excel",
    selectValidationVideo: "vision:select-validation-video",
    liveStreamUrl: "vision:live-stream-url",
    iotDiscoveredDevices: "iot:discovered-devices",
    iotSelectDevice: "iot:select-device",
    iotCancelSelection: "iot:cancel-device-selection",
    iotConnection: "iot:connection-state",
    iotHardwareEvent: "iot:hardware-event",
    minimizeWindow: "window:minimize",
    toggleMaximizeWindow: "window:toggle-maximize",
    closeWindow: "window:close",
};


/***/ },

/***/ "./src/shared/ipc-policy.ts"
/*!**********************************!*\
  !*** ./src/shared/ipc-policy.ts ***!
  \**********************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   allowsRendererBackendRequest: () => (/* binding */ allowsRendererBackendRequest)
/* harmony export */ });
function allowsRendererBackendRequest(request) {
    const path = request.path.split("?", 1)[0];
    if (path === "/api/iot/connection")
        return false;
    if (request.method !== "POST")
        return true;
    const body = request.body;
    if (path === "/api/iot-events") {
        return Boolean(body &&
            typeof body === "object" &&
            "event_source" in body &&
            body.event_source === "VALIDATION");
    }
    if (body && typeof body === "object" && "event_source" in body) {
        return body.event_source === "VALIDATION";
    }
    return true;
}


/***/ },

/***/ "./src/shared/readiness.ts"
/*!*********************************!*\
  !*** ./src/shared/readiness.ts ***!
  \*********************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   createPhaseOneReadiness: () => (/* binding */ createPhaseOneReadiness)
/* harmony export */ });
function createPhaseOneReadiness(resources, checkedAt = new Date().toISOString()) {
    const components = [
        {
            id: "desktop",
            label: "Desktop runtime",
            description: "Electron main, preload, and React renderer",
            status: "ready",
            detail: "Secure desktop shell is active.",
        },
        {
            id: "backend",
            label: "Python backend",
            description: "FastAPI session and inference sidecar",
            status: "pending",
            detail: "Automatic backend startup is scheduled for Phase 2.",
            actionLabel: "Phase 2",
        },
        {
            id: "workstation_detector",
            label: "Workstation detector",
            description: "YOLOv8n · workstation · 640 × 640",
            status: resources.workstationCheckpointExists ? "attention" : "blocked",
            detail: resources.workstationCheckpointExists
                ? "Checkpoint present. Runtime loading and test inference are pending."
                : "The workstation checkpoint best.pt is missing.",
            actionLabel: resources.workstationCheckpointExists ? "Phase 3" : "Add model",
        },
        {
            id: "garment_classifier",
            label: "Garment classifier",
            description: "Temporal MobileNetV3 · 8 frames · 224 × 224",
            status: resources.classifierCheckpointExists ? "attention" : "blocked",
            detail: resources.classifierCheckpointExists
                ? "Checkpoint present. Runtime loading and test inference are pending."
                : "The garment checkpoint best_model.pt is missing.",
            actionLabel: resources.classifierCheckpointExists ? "Phase 3" : "Add model",
        },
        {
            id: "camera",
            label: "Sewing camera",
            description: "Camera permissions and live workstation view",
            status: "pending",
            detail: "Camera capture becomes available with the Python sidecar.",
            actionLabel: "Check camera",
        },
        {
            id: "iot_controller",
            label: "IoT controller",
            description: "ESP32-C3 · BLE · rework / downtime",
            status: "pending",
            detail: "Connect the physical ESP32-C3 controller after the local service starts.",
            actionLabel: "Connect controller",
        },
    ];
    const readyCount = components.filter((component) => component.status === "ready").length;
    return {
        checkedAt,
        components,
        productionReady: components.every((component) => component.status === "ready"),
        completionPercent: Math.round((readyCount / components.length) * 100),
    };
}


/***/ },

/***/ "./src/shared/release-policy.ts"
/*!**************************************!*\
  !*** ./src/shared/release-policy.ts ***!
  \**************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   FROZEN_TORCH_NUMPY_MODULES: () => (/* binding */ FROZEN_TORCH_NUMPY_MODULES),
/* harmony export */   REQUIRED_BRANDING_FILES: () => (/* binding */ REQUIRED_BRANDING_FILES),
/* harmony export */   REQUIRED_MODEL_FILES: () => (/* binding */ REQUIRED_MODEL_FILES),
/* harmony export */   missingReleaseBranding: () => (/* binding */ missingReleaseBranding),
/* harmony export */   missingReleaseModels: () => (/* binding */ missingReleaseModels),
/* harmony export */   repairFrozenTorchNumpySource: () => (/* binding */ repairFrozenTorchNumpySource),
/* harmony export */   sidecarExecutableName: () => (/* binding */ sidecarExecutableName),
/* harmony export */   validateReleaseManifest: () => (/* binding */ validateReleaseManifest)
/* harmony export */ });
const REQUIRED_MODEL_FILES = [
    "best_model.pt",
    "best.pt",
    "label_mapping.json",
    "data.yaml",
];
const REQUIRED_BRANDING_FILES = ["icon.png", "icon.icns", "icon.ico"];
const FROZEN_TORCH_NUMPY_MODULES = ["_ufuncs.py", "_funcs.py", "_dtypes.py"];
function sidecarExecutableName(platform) {
    return platform === "win32" ? "garment-counter-sidecar.exe" : "garment-counter-sidecar";
}
function missingReleaseModels(modelDirectory, joinPath, fileExists) {
    return REQUIRED_MODEL_FILES.filter((filename) => !fileExists(joinPath(modelDirectory, filename)));
}
function missingReleaseBranding(brandingDirectory, joinPath, fileExists) {
    return REQUIRED_BRANDING_FILES.filter((filename) => !fileExists(joinPath(brandingDirectory, filename)));
}
function repairFrozenTorchNumpySource(source) {
    return source.replaceAll("vars()[name]", "globals()[name]");
}
function validateReleaseManifest(manifest, platform, architecture) {
    if (manifest.platform !== platform) {
        return `The Python service was prepared for ${manifest.platform}, not ${platform}. Rebuild it on the target operating system.`;
    }
    if (manifest.architecture !== architecture) {
        return `The Python service was prepared for ${manifest.architecture}, not ${architecture}. Rebuild it on the target CPU architecture.`;
    }
    if (manifest.executable !== sidecarExecutableName(platform)) {
        return "The prepared Python service executable does not match the target operating system.";
    }
    for (const filename of REQUIRED_MODEL_FILES) {
        if (!manifest.modelChecksums[filename]) {
            return `The release manifest does not include an integrity checksum for ${filename}.`;
        }
    }
    return null;
}


/***/ },

/***/ "electron"
/*!***************************!*\
  !*** external "electron" ***!
  \***************************/
(module) {

module.exports = require("electron");

/***/ },

/***/ "node:child_process"
/*!*************************************!*\
  !*** external "node:child_process" ***!
  \*************************************/
(module) {

module.exports = require("node:child_process");

/***/ },

/***/ "node:crypto"
/*!******************************!*\
  !*** external "node:crypto" ***!
  \******************************/
(module) {

module.exports = require("node:crypto");

/***/ },

/***/ "node:fs"
/*!**************************!*\
  !*** external "node:fs" ***!
  \**************************/
(module) {

module.exports = require("node:fs");

/***/ },

/***/ "node:fs/promises"
/*!***********************************!*\
  !*** external "node:fs/promises" ***!
  \***********************************/
(module) {

module.exports = require("node:fs/promises");

/***/ },

/***/ "node:net"
/*!***************************!*\
  !*** external "node:net" ***!
  \***************************/
(module) {

module.exports = require("node:net");

/***/ },

/***/ "node:path"
/*!****************************!*\
  !*** external "node:path" ***!
  \****************************/
(module) {

module.exports = require("node:path");

/***/ },

/***/ "node:url"
/*!***************************!*\
  !*** external "node:url" ***!
  \***************************/
(module) {

module.exports = require("node:url");

/***/ }

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	const __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		const cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		const module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		if (!(moduleId in __webpack_modules__)) {
/******/ 			delete __webpack_module_cache__[moduleId];
/******/ 			const e = new Error("Cannot find module '" + moduleId + "'");
/******/ 			e.code = 'MODULE_NOT_FOUND';
/******/ 			throw e;
/******/ 		}
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat get default export */
/******/ 	(() => {
/******/ 		// getDefaultExport function for compatibility with non-harmony modules
/******/ 		__webpack_require__.n = (module) => {
/******/ 			const getter = module && module.__esModule ?
/******/ 				() => (module['default']) :
/******/ 				() => (module);
/******/ 			__webpack_require__.d(getter, { a: getter });
/******/ 			return getter;
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter/value functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			if(Array.isArray(definition)) {
/******/ 				var i = 0;
/******/ 				while(i < definition.length) {
/******/ 					var key = definition[i++];
/******/ 					var binding = definition[i++];
/******/ 					if(!__webpack_require__.o(exports, key)) {
/******/ 						if(binding === 0) {
/******/ 							Object.defineProperty(exports, key, { enumerable: true, value: definition[i++] });
/******/ 						} else {
/******/ 							Object.defineProperty(exports, key, { enumerable: true, get: binding });
/******/ 						}
/******/ 					} else if(binding === 0) { i++; }
/******/ 				}
/******/ 			} else {
/******/ 				for(var key in definition) {
/******/ 					if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 						Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 					}
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
let __webpack_exports__ = {};
// This entry needs to be wrapped in an IIFE because it needs to be isolated against other modules in the chunk.
(() => {
/*!**************************!*\
  !*** ./src/main/main.ts ***!
  \**************************/
__webpack_require__.r(__webpack_exports__);
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! electron */ "electron");
/* harmony import */ var electron__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(electron__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _backend_manager__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./backend-manager */ "./src/main/backend-manager.ts");
/* harmony import */ var _ipc__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./ipc */ "./src/main/ipc.ts");
/* harmony import */ var _protocol__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./protocol */ "./src/main/protocol.ts");
/* harmony import */ var _window_manager__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! ./window-manager */ "./src/main/window-manager.ts");





(0,_protocol__WEBPACK_IMPORTED_MODULE_3__.registerApplicationProtocolScheme)();
electron__WEBPACK_IMPORTED_MODULE_0__.app.setAppUserModelId("lk.zgen.garmentcounter");
const hasSingleInstanceLock = electron__WEBPACK_IMPORTED_MODULE_0__.app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
    electron__WEBPACK_IMPORTED_MODULE_0__.app.quit();
}
else {
    electron__WEBPACK_IMPORTED_MODULE_0__.app.on("second-instance", () => {
        const existingWindow = (0,_window_manager__WEBPACK_IMPORTED_MODULE_4__.getMainWindow)();
        if (!existingWindow)
            return;
        if (existingWindow.isMinimized())
            existingWindow.restore();
        existingWindow.focus();
    });
    electron__WEBPACK_IMPORTED_MODULE_0__.app.whenReady().then(async () => {
        (0,_ipc__WEBPACK_IMPORTED_MODULE_2__.registerDesktopIpc)(_window_manager__WEBPACK_IMPORTED_MODULE_4__.getMainWindow);
        (0,_protocol__WEBPACK_IMPORTED_MODULE_3__.registerWorkstationStreamProtocol)();
        await (0,_window_manager__WEBPACK_IMPORTED_MODULE_4__.createMainWindow)();
        void _backend_manager__WEBPACK_IMPORTED_MODULE_1__.backendManager.start().catch(() => {
            // The renderer receives a safe, actionable startup message through the IPC status endpoint.
        });
        electron__WEBPACK_IMPORTED_MODULE_0__.app.on("activate", async () => {
            if (electron__WEBPACK_IMPORTED_MODULE_0__.BrowserWindow.getAllWindows().length === 0) {
                await (0,_window_manager__WEBPACK_IMPORTED_MODULE_4__.createMainWindow)();
            }
        });
    });
}
electron__WEBPACK_IMPORTED_MODULE_0__.app.on("before-quit", () => {
    _backend_manager__WEBPACK_IMPORTED_MODULE_1__.backendManager.stop();
});
electron__WEBPACK_IMPORTED_MODULE_0__.app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        electron__WEBPACK_IMPORTED_MODULE_0__.app.quit();
    }
});

})();

module.exports = __webpack_exports__;
/******/ })()
;
//# sourceMappingURL=index.js.map