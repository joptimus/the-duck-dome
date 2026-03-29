const { spawn } = require("child_process");
const path = require("path");

const BACKEND_DIR = path.resolve(__dirname, "..", "..", "..", "backend");

let backendProcess = null;

function startBackend() {
  backendProcess = spawn(
    "uvicorn",
    ["duckdome.main:app", "--host", "127.0.0.1", "--port", "8000"],
    {
      cwd: BACKEND_DIR,
      stdio: "pipe",
    },
  );

  backendProcess.stdout.on("data", (data) => {
    console.log(`[backend] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[backend] ${data}`);
  });

  return backendProcess;
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

module.exports = { startBackend, stopBackend };
