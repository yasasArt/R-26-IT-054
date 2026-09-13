import { app, shell, BrowserWindow } from 'electron'
import { join } from 'path'
import { existsSync, readdirSync } from 'fs'
import { homedir } from 'os'
import { spawn, execFile, ChildProcess } from 'child_process'
import { promisify } from 'util'
import net from 'net'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'

const execFileAsync = promisify(execFile)

// One command (`npm run dev`, or the packaged app) boots the whole system -
// this process auto-launches both Python services if they aren't already
// running, so nobody has to manually start three things in three terminals.
interface ManagedProcess {
  name: string
  port: number
  command: string
  args: string[]
  cwd: string
}

// A bare command name (e.g. 'python') only resolves if it's on *this
// process's* PATH - which is not guaranteed to match an interactive shell's
// PATH. Confirmed in practice: probing 'python'/'py'/'python3' succeeded
// when run from a terminal, but failed when Electron itself spawned the
// probe, because the app's own environment didn't have the user-level
// Python install directory on PATH at all. This scans the standard
// per-user install location directly - no PATH dependency - as a fallback
// so a real interpreter with the right packages is still found even then.
function findWindowsPythonInstalls(): string[] {
  const programsDir = join(homedir(), 'AppData', 'Local', 'Programs', 'Python')
  try {
    return readdirSync(programsDir)
      .filter((entry) => /^Python3\d+$/.test(entry))
      .sort()
      .reverse() // newest version first
      .map((entry) => join(programsDir, entry, 'python.exe'))
      .filter((path) => existsSync(path))
  } catch {
    return [] // directory doesn't exist - nothing extra to offer
  }
}

// Rather than hardcoding one user's exact interpreter path (which only
// works on that one machine), probe each platform-appropriate command name
// plus (on Windows) directly-discovered installs, and use the first one
// that actually imports the backend's dependencies.
async function findBackendPython(): Promise<string> {
  const pathCandidates = process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python']
  const extraCandidates = process.platform === 'win32' ? findWindowsPythonInstalls() : []
  const candidates = [...pathCandidates, ...extraCandidates]

  for (const candidate of candidates) {
    try {
      await execFileAsync(candidate, ['-c', 'import fastapi, uvicorn'])
      return candidate
    } catch {
      continue
    }
  }

  console.warn(
    `Could not find a Python interpreter with fastapi/uvicorn installed (tried: ${candidates.join(', ')}). ` +
      `Install them with '<python> -m pip install fastapi uvicorn' for whichever interpreter you intend to use. ` +
      `Falling back to '${pathCandidates[0]}' - the backend will fail to start if it's missing those packages.`
  )
  return pathCandidates[0]
}

// venv layout differs by platform: Scripts/python.exe on Windows,
// bin/python everywhere else.
function venvPython(venvDir: string): string {
  return process.platform === 'win32' ? join(venvDir, 'Scripts', 'python.exe') : join(venvDir, 'bin', 'python')
}

async function buildManagedProcesses(): Promise<ManagedProcess[]> {
  const resourcesVenvPython = venvPython(join(__dirname, '../../../resources/.venv'))
  if (!existsSync(resourcesVenvPython)) {
    console.warn(
      `CV pipeline venv not found at ${resourcesVenvPython} - see resources/ for first-time setup instructions.`
    )
  }

  return [
    {
      name: 'FastAPI backend',
      port: 8000,
      command: await findBackendPython(),
      args: ['-m', 'uvicorn', 'main:app', '--port', '8000'],
      cwd: join(__dirname, '../../../backend')
    },
    {
      name: 'CV capture pipeline',
      port: 5050,
      // Its own venv (torch/ultralytics/opencv) - deliberately not the
      // interpreter the lightweight backend above uses.
      command: resourcesVenvPython,
      args: ['live_webcam_pipeline.py'],
      cwd: join(__dirname, '../../../resources')
    }
  ]
}

const runningProcesses: ChildProcess[] = []

function isPortOpen(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host: '127.0.0.1' })
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('error', () => {
      socket.destroy()
      resolve(false)
    })
    socket.setTimeout(500, () => {
      socket.destroy()
      resolve(false)
    })
  })
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

// Guards against this function's own body running twice within the same
// process - observed happening on some launches even with nothing else
// changed (electron-vite appears to invoke the ready flow more than once
// under some conditions), which without this produced two independent CV
// pipeline child processes both fighting over the same DirectShow camera -
// a real, confirmed cause of "Could not open this camera" failures having
// nothing to do with any other application actually using the device.
let hasEnsuredProcesses = false

async function ensureManagedProcessesRunning(): Promise<void> {
  if (hasEnsuredProcesses) {
    console.log('ensureManagedProcessesRunning already ran once this session - skipping.')
    return
  }
  hasEnsuredProcesses = true

  const managedProcesses = await buildManagedProcesses()
  for (const proc of managedProcesses) {
    if (await isPortOpen(proc.port)) {
      console.log(`${proc.name} already running on port ${proc.port} - not starting a new one.`)
      continue
    }

    // Narrows (does not eliminate) a real race: something else - another
    // launch, a not-yet-exited previous instance - may already be mid-spawn
    // for this same port. Waiting and re-checking once catches that in the
    // common case instead of assuming the very first check is authoritative.
    await sleep(300)
    if (await isPortOpen(proc.port)) {
      console.log(`${proc.name} became available on port ${proc.port} while checking - not starting a new one.`)
      continue
    }

    console.log(`Starting ${proc.name}...`)
    const child = spawn(proc.command, proc.args, {
      cwd: proc.cwd,
      stdio: 'inherit'
    })

    child.on('error', (err) => {
      console.error(`Failed to start ${proc.name}:`, err)
    })

    runningProcesses.push(child)
  }
}

function stopManagedProcesses(): void {
  for (const child of runningProcesses) {
    if (!child.killed) {
      child.kill()
    }
  }
  runningProcesses.length = 0
}

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: '#F5F7FB',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.threadscan.app')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  await ensureManagedProcessesRunning()
  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopManagedProcesses()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopManagedProcesses()
})
