const { spawn } = require("child_process");
const path = require("path");

const BACKEND_DIR = path.resolve(__dirname, "..", "..", "..", "backend");
const BACKEND_SRC = path.join(BACKEND_DIR, "src");

let backendProcess = null;

function startBackend() {
  const env = { ...process.env, PYTHONPATH: BACKEND_SRC };

  backendProcess = spawn(
    "uvicorn",
    ["duckdome.main:app", "--host", "127.0.0.1", "--port", "8000"],
    {
      cwd: BACKEND_DIR,
      env,
      stdio: "pipe",
    },
  );

  backendProcess.stdout.on("data", (data) => {
    console.log(`[backend] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[backend] ${data}`);
  });

  backendProcess.on("error", (err) => {
    console.error(`[backend] failed to start: ${err.message}`);
    backendProcess = null;
  });

  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
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
