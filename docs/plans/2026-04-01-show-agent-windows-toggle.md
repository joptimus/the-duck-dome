# Show Agent Windows Toggle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a server-persisted toggle in the Settings panel that controls whether CLI agent windows are visible or hidden, applying immediately to all running agents.

**Architecture:** New `SettingsStore` persists `settings.json` in `data_dir`. A new `/api/settings` route exposes GET/PATCH. `AgentProcessManager` gains `set_show_windows(visible)` which iterates running agents and shows/hides windows via platform APIs (macOS: AppleScript Terminal.app helpers that already exist; Windows: ctypes `ShowWindow`). New agents respect the flag at launch. Frontend adds a single toggle in `SettingsPanel` that calls PATCH on change.

**Tech Stack:** FastAPI + Python backend, React/JSX frontend, ctypes (Windows), osascript (macOS)

---

### Task 1: SettingsStore

**Files:**
- Create: `backend/src/duckdome/stores/settings_store.py`
- Create: `backend/tests/test_settings_store.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_settings_store.py
from duckdome.stores.settings_store import SettingsStore


def test_default_show_windows_is_false(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    assert store.get("show_agent_windows") is False


def test_set_and_get(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    store.set("show_agent_windows", True)
    assert store.get("show_agent_windows") is True


def test_persists_across_reload(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    store.set("show_agent_windows", True)
    store2 = SettingsStore(data_dir=tmp_path)
    assert store2.get("show_agent_windows") is True


def test_get_all_includes_defaults(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    result = store.get_all()
    assert "show_agent_windows" in result
    assert result["show_agent_windows"] is False
```

**Step 2: Run — expect ImportError**
```bash
cd backend && python3 -m pytest tests/test_settings_store.py -v
```

**Step 3: Implement**

```python
# backend/src/duckdome/stores/settings_store.py
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

DEFAULTS: dict[str, object] = {
    "show_agent_windows": False,
}


class SettingsStore:
    def __init__(self, data_dir: Path) -> None:
        self._file = Path(data_dir) / "settings.json"
        self._lock = Lock()
        self._data: dict[str, object] = {**DEFAULTS}
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._file)

    def get(self, key: str) -> object:
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def get_all(self) -> dict[str, object]:
        with self._lock:
            return {**DEFAULTS, **self._data}
```

**Step 4: Run — expect 4 passed**
```bash
cd backend && python3 -m pytest tests/test_settings_store.py -v
```

**Step 5: Commit**
```bash
git add backend/src/duckdome/stores/settings_store.py backend/tests/test_settings_store.py
git commit -m "feat: add SettingsStore for server-side settings persistence"
```

---

### Task 2: Settings Route

**Files:**
- Create: `backend/src/duckdome/routes/settings.py`
- Create: `backend/tests/test_settings_route.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_settings_route.py
from fastapi.testclient import TestClient
from duckdome.app import create_app


def test_get_settings_returns_defaults(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["show_agent_windows"] is False


def test_patch_settings_persists(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.patch("/api/settings", json={"show_agent_windows": True})
    assert resp.status_code == 200
    assert resp.json()["show_agent_windows"] is True

    # Verify persisted by re-reading
    resp2 = client.get("/api/settings")
    assert resp2.json()["show_agent_windows"] is True


def test_patch_unknown_key_is_ignored(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.patch("/api/settings", json={"unknown_key": "foo"})
    assert resp.status_code == 200
    assert "unknown_key" not in resp.json()
```

**Step 2: Run — expect ImportError / 404**
```bash
cd backend && python3 -m pytest tests/test_settings_route.py -v
```

**Step 3: Implement route**

```python
# backend/src/duckdome/routes/settings.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from duckdome.stores.settings_store import DEFAULTS, SettingsStore
from duckdome.services.wrapper_service import WrapperService

router = APIRouter(prefix="/api/settings", tags=["settings"])

_store: SettingsStore | None = None
_wrapper_service: WrapperService | None = None


def init(store: SettingsStore, wrapper_service: WrapperService | None = None) -> None:
    global _store, _wrapper_service
    _store = store
    _wrapper_service = wrapper_service


def _get_store() -> SettingsStore:
    assert _store is not None
    return _store


class SettingsPatch(BaseModel):
    show_agent_windows: bool | None = None


@router.get("", status_code=200)
def get_settings():
    return _get_store().get_all()


@router.patch("", status_code=200)
def patch_settings(body: SettingsPatch):
    store = _get_store()
    if body.show_agent_windows is not None:
        store.set("show_agent_windows", body.show_agent_windows)
        if _wrapper_service is not None:
            _wrapper_service.set_show_windows(body.show_agent_windows)
    return store.get_all()
```

**Step 4: Wire into app.py**

In `backend/src/duckdome/app.py`, add these changes:

```python
# Add import at top with other route imports:
from duckdome.routes import settings as settings_mod
from duckdome.stores.settings_store import SettingsStore

# In create_app(), after other stores:
settings_store = SettingsStore(data_dir=data_dir)

# After wrapper_service is created:
settings_mod.init(settings_store, wrapper_service=wrapper_service)

# In route registration:
app.include_router(settings_mod.router)
```

**Step 5: Run — expect 3 passed**
```bash
cd backend && python3 -m pytest tests/test_settings_route.py -v
```

**Step 6: Commit**
```bash
git add backend/src/duckdome/routes/settings.py backend/tests/test_settings_route.py backend/src/duckdome/app.py
git commit -m "feat: add GET/PATCH /api/settings route"
```

---

### Task 3: WrapperService.set_show_windows()

**Files:**
- Modify: `backend/src/duckdome/services/wrapper_service.py`
- Modify: `backend/tests/test_wrapper_service.py`

**Step 1: Write failing test**

```python
# append to backend/tests/test_wrapper_service.py
from unittest.mock import patch as mock_patch

def test_set_show_windows_delegates_to_manager(tmp_path):
    svc = WrapperService(data_dir=tmp_path)
    svc._manager.set_show_windows = MagicMock()
    svc.set_show_windows(True)
    svc._manager.set_show_windows.assert_called_once_with(True)
```

**Step 2: Run — expect AttributeError**
```bash
cd backend && python3 -m pytest tests/test_wrapper_service.py::test_set_show_windows_delegates_to_manager -v
```

**Step 3: Add method to WrapperService**

```python
# append to WrapperService class in wrapper_service.py:
def set_show_windows(self, visible: bool) -> None:
    self._manager.set_show_windows(visible)
```

**Step 4: Run — expect 1 passed**
```bash
cd backend && python3 -m pytest tests/test_wrapper_service.py -v
```

**Step 5: Commit**
```bash
git add backend/src/duckdome/services/wrapper_service.py backend/tests/test_wrapper_service.py
git commit -m "feat: add WrapperService.set_show_windows()"
```

---

### Task 4: AgentProcessManager.set_show_windows()

This is the platform-specific core. It needs to:
1. Store the flag (`_show_windows`)
2. Apply immediately to all running agents
3. Respect the flag when starting new agents

**Files:**
- Modify: `backend/src/duckdome/wrapper/manager.py`
- Modify: `backend/tests/test_wrapper_manager.py`

**Step 1: Write failing tests**

```python
# append to backend/tests/test_wrapper_manager.py
from unittest.mock import patch, MagicMock
from pathlib import Path
from duckdome.wrapper.manager import AgentProcessManager


def test_default_show_windows_is_false(tmp_path):
    mgr = AgentProcessManager(data_dir=tmp_path)
    assert mgr._show_windows is False


def test_set_show_windows_updates_flag(tmp_path):
    mgr = AgentProcessManager(data_dir=tmp_path)
    mgr.set_show_windows(True)
    assert mgr._show_windows is True


def test_set_show_windows_calls_open_terminal_for_tmux_agents(tmp_path):
    mgr = AgentProcessManager(data_dir=tmp_path)
    # Inject a fake running tmux agent
    from duckdome.wrapper.manager import AgentProcess
    ap = AgentProcess(agent_type="claude", tmux_session="duckdome-claude")
    ap.started_at = 1.0
    with mgr._lock:
        mgr._agents["claude"] = ap

    with patch("duckdome.wrapper.manager._open_agent_terminal") as mock_open, \
         patch("duckdome.wrapper.manager._close_agent_terminal") as mock_close, \
         patch.object(mgr, "_is_alive", return_value=True):
        mgr.set_show_windows(True)
        mock_open.assert_called_once_with("duckdome-claude")
        mock_close.assert_not_called()

        mgr.set_show_windows(False)
        mock_close.assert_called_once_with("duckdome-claude")
```

**Step 2: Run — expect AttributeError**
```bash
cd backend && python3 -m pytest tests/test_wrapper_manager.py -v -k "show_windows"
```

**Step 3: Add `_show_windows` flag and platform helpers**

In `AgentProcessManager.__init__`, add:
```python
self._show_windows: bool = False
```

Add Windows HWND helper (near top of manager.py, after imports, inside a `if sys.platform == "win32":` guard or just using lazy imports):

```python
def _win_set_window_visible(pid: int, visible: bool) -> None:
    """Show or hide the console window for a process on Windows."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    SW_HIDE = 0
    SW_SHOW = 5
    user32 = ctypes.windll.user32
    found: list[int] = []

    WinEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd: int, _: int) -> bool:
        pid_out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value == pid:
            found.append(hwnd)
        return True

    user32.EnumWindows(WinEnumProc(_cb), 0)
    for hwnd in found:
        user32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)
```

Add `set_show_windows` method to `AgentProcessManager`:

```python
def set_show_windows(self, visible: bool) -> None:
    """Update window visibility flag and apply to all running agents."""
    self._show_windows = visible
    with self._lock:
        agents = list(self._agents.items())
    for key, ap in agents:
        if not self._is_alive(key):
            continue
        if ap.tmux_session:
            # macOS: open/close Terminal.app window for the tmux session
            if visible:
                _open_agent_terminal(ap.tmux_session)
            else:
                _close_agent_terminal(ap.tmux_session)
        elif ap.pid is not None:
            # Windows: show/hide the console window by PID
            _win_set_window_visible(ap.pid, visible)
```

**Step 4: Respect flag on new agent start**

In `_run_one_tmux_iteration()` (macOS path), replace the unconditional call:
```python
# BEFORE:
_open_agent_terminal(session)

# AFTER:
if self._show_windows:
    _open_agent_terminal(session)
```

In `_run_one_popen_iteration()` (Windows path), after `agent_proc.ready_event.set()`:
```python
# After proc starts and ready_event is set:
if not self._show_windows and ap.pid is not None:
    _win_set_window_visible(proc.pid, False)
```

Note: `_run_one_popen_iteration` is a closure inside `start_agent`. It captures `agent_proc` from the outer scope and `self` via closure. Adjust accordingly — the method reference to `self._show_windows` works because the closure captures `self`.

**Step 5: Run tests**
```bash
cd backend && python3 -m pytest tests/test_wrapper_manager.py -v -k "show_windows"
```
Expected: 3 passed

**Step 6: Commit**
```bash
git add backend/src/duckdome/wrapper/manager.py backend/tests/test_wrapper_manager.py
git commit -m "feat: add AgentProcessManager.set_show_windows() with platform show/hide"
```

---

### Task 5: Frontend Toggle

**Files:**
- Modify: `apps/web/src/features/channel-shell/api.js`
- Modify: `apps/web/src/components/panels/SettingsPanel.jsx`

**Step 1: Add API functions to api.js**

Append to `apps/web/src/features/channel-shell/api.js`:

```js
export async function getSettings() {
  try {
    return await request("/api/settings");
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return { show_agent_windows: false };
  }
}

export async function patchSettings(patch) {
  return request("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
```

**Step 2: Add toggle to SettingsPanel.jsx**

Import the API functions at the top:
```jsx
import { getSettings, patchSettings } from "../../features/channel-shell/api";
```

Add state for `showAgentWindows` and fetch on mount:
```jsx
// Inside SettingsPanel component, alongside existing state:
const [showAgentWindows, setShowAgentWindows] = useState(false);

useEffect(() => {
  getSettings()
    .then((s) => setShowAgentWindows(Boolean(s.show_agent_windows)))
    .catch(() => {});
}, []);

const handleShowWindowsToggle = (value) => {
  setShowAgentWindows(value);
  patchSettings({ show_agent_windows: value }).catch(() => {});
};
```

Add a new "Agents" section in the JSX, after the Sounds section:
```jsx
<Section title="Agents">
  <Toggle
    label="Show agent windows"
    on={showAgentWindows}
    onChange={handleShowWindowsToggle}
  />
</Section>
```

**Note on PR 47 conflict:** PR 47 refactors `Toggle` from self-managed state to controlled (`on` + `onChange` props). If PR 47 is merged before this task runs, the `Toggle` call above is already correct. If not, the existing `Toggle` component takes `defaultOn` instead — adjust the call to match whichever version is in the branch.

**Step 3: Manual verify**
- Start the backend and frontend
- Open Settings panel — toggle should appear in "Agents" section defaulting to off
- Toggle on — agent windows should appear immediately
- Toggle off — agent windows should hide immediately
- Restart backend — setting should be remembered

**Step 4: Commit**
```bash
git add apps/web/src/features/channel-shell/api.js apps/web/src/components/panels/SettingsPanel.jsx
git commit -m "feat: add Show Agent Windows toggle to settings panel"
```

---

### Task 6: Initialize from persisted value on backend startup

When the backend restarts, `AgentProcessManager` defaults `_show_windows = False`. But the user may have saved `show_agent_windows = True`. The startup path should read the persisted value and initialize the manager.

**Files:**
- Modify: `backend/src/duckdome/app.py`

**Step 1: After both `settings_store` and `wrapper_service` are created, add:**

```python
# In create_app(), after wrapper_service and settings_store are both created:
initial_show_windows = settings_store.get("show_agent_windows")
if initial_show_windows:
    wrapper_service.set_show_windows(True)
```

**Step 2: Run full test suite to confirm no regressions**
```bash
cd backend && python3 -m pytest -x -q
```

**Step 3: Commit**
```bash
git add backend/src/duckdome/app.py
git commit -m "feat: initialize show_windows from persisted settings on startup"
```

---

## Branch setup

Create a new branch from `main` before starting:
```bash
git fetch origin
git worktree add /tmp/the-duck-dome-show-windows -b feat/show-agent-windows origin/main
cd /tmp/the-duck-dome-show-windows
```

## Test commands reference

```bash
# All backend tests
cd backend && python3 -m pytest -x -q

# Specific test files
cd backend && python3 -m pytest tests/test_settings_store.py tests/test_settings_route.py tests/test_wrapper_service.py tests/test_wrapper_manager.py -v
```
