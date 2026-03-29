import { useState, useEffect } from "react";

const BACKEND_URL = "http://localhost:8000";

function App() {
  const [backendStatus, setBackendStatus] = useState("checking...");

  useEffect(() => {
    fetch(`${BACKEND_URL}/health`)
      .then((res) => res.json())
      .then((data) => setBackendStatus(data.status))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>DuckDome</h1>
      <p>App status: running</p>
      <p>Backend: {backendStatus}</p>
    </div>
  );
}

export default App;
