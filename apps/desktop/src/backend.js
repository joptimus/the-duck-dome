const { spawn } = require("child_process");
const path = require("path");

const BACKEND_DIR = path.resolve(__dirname, "..", "..", "..", "backend");
const BACKEND_SRC = path.join(BACKEND_DIR, "src");
const BACKEND_STOP_TIMEOUT_MS = 8000;

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
  if (!backendProcess) return Promise.resolve();

  return new Promise((resolve) => {
    const proc = backendProcess;
    let finished = false;

    const finish = () => {
      if (finished) return;
      finished = true;
      resolve();
    };

    const timeout = setTimeout(() => {
      if (finished) return;
      console.warn("[backend] graceful shutdown timed out, forcing exit");
      try {
        proc.kill("SIGKILL");
      } catch {}
    }, BACKEND_STOP_TIMEOUT_MS);

    proc.once("exit", () => {
      clearTimeout(timeout);
      finish();
    });

    try {
      proc.kill("SIGINT");
    } catch {
      clearTimeout(timeout);
      finish();
    }
  });
}

module.exports = { startBackend, stopBackend };
