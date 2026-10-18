const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    title: "MAS Automated Garment Quality Assurance",
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Development එකේදී localhost එකත්, Build කළාට පස්සේ index.html එකත් පෙන්වයි
  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});