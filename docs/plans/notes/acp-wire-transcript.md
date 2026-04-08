# ACP Wire Transcript (gemini --acp)

> Captured: 2026-04-04
> Gemini version: 0.35.2 (`/opt/homebrew/bin/gemini`)
> Purpose: Reference for GeminiBridge implementation. Exact wire shapes observed from the real binary.

## Probe script

Run in a scratch dir (`/tmp/gemini-acp-probe`) outside the worktree:

```python
import json, subprocess, threading, time, sys

proc = subprocess.Popen(
    ["gemini", "--acp"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1,
)
def pump(name, stream):
    try:
        for line in stream:
            print(f"<<{name}>> {line.rstrip()}", flush=True)
    except Exception as e:
        print(f"<<{name}:err>> {e}", flush=True)
threading.Thread(target=pump, args=("stdout", proc.stdout), daemon=True).start()
threading.Thread(target=pump, args=("stderr", proc.stderr), daemon=True).start()

def send(msg):
    line = json.dumps(msg) + "\n"
    print(f">>send>> {line.strip()}", flush=True)
    proc.stdin.write(line); proc.stdin.flush()

# Give gemini startup time (keychain + cached creds load on stderr)
time.sleep(2.0)

send({"jsonrpc":"2.0","id":1,"method":"initialize",
      "params":{"protocolVersion":1,
                "clientCapabilities":{"fs":{"readTextFile":True,"writeTextFile":True},"terminal":False}}})
time.sleep(4.0)

send({"jsonrpc":"2.0","id":2,"method":"session/new",
      "params":{"cwd":"/tmp/gemini-acp-probe","mcpServers":[]}})
time.sleep(6.0)

proc.terminate()
try: proc.wait(timeout=3)
except Exception: proc.kill()
```

Notes:
- Transport is newline-delimited JSON-RPC 2.0 over stdio (no `Content-Length` framing).
- An initial sleep of ~2s before the first request is required; the binary emits stderr startup logs (keychain fallback, credential load) before it's ready.
- An earlier attempt with only 1.5s between messages produced no visible responses before termination — responses *were* emitted, just after our probe had already exited. Increase the waits for reliable capture.

## Raw log

```
>>send>> {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": true, "writeTextFile": true}, "terminal": false}}}
<<stdout>> {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"authMethods":[{"id":"oauth-personal","name":"Log in with Google","description":"Log in with your Google account"},{"id":"gemini-api-key","name":"Gemini API key","description":"Use an API key with Gemini Developer API","_meta":{"api-key":{"provider":"google"}}},{"id":"vertex-ai","name":"Vertex AI","description":"Use an API key with Vertex AI GenAI API"},{"id":"gateway","name":"AI API Gateway","description":"Use a custom AI API Gateway","_meta":{"gateway":{"protocol":"google","restartRequired":"false"}}}],"agentInfo":{"name":"gemini-cli","title":"Gemini CLI","version":"0.35.2"},"agentCapabilities":{"loadSession":true,"promptCapabilities":{"image":true,"audio":true,"embeddedContext":true},"mcpCapabilities":{"http":true,"sse":true}}}}
>>send>> {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": "/tmp/gemini-acp-probe", "mcpServers": []}}
<<stdout>> {"jsonrpc":"2.0","id":2,"result":{"sessionId":"1cf07f9c-eb75-4f90-aadc-4749025bbf96","modes":{"availableModes":[{"id":"default","name":"Default","description":"Prompts for approval"},{"id":"autoEdit","name":"Auto Edit","description":"Auto-approves edit tools"},{"id":"yolo","name":"YOLO","description":"Auto-approves all tools"},{"id":"plan","name":"Plan","description":"Read-only mode"}],"currentModeId":"default"},"models":{"availableModels":[{"modelId":"auto-gemini-3","name":"Auto (Gemini 3)","description":"Let Gemini CLI decide the best model for the task: gemini-3-pro, gemini-3-flash"},{"modelId":"auto-gemini-2.5","name":"Auto (Gemini 2.5)","description":"Let Gemini CLI decide the best model for the task: gemini-2.5-pro, gemini-2.5-flash"},{"modelId":"gemini-3-pro-preview","name":"gemini-3-pro-preview"},{"modelId":"gemini-3-flash-preview","name":"gemini-3-flash-preview"},{"modelId":"gemini-2.5-pro","name":"gemini-2.5-pro"},{"modelId":"gemini-2.5-flash","name":"gemini-2.5-flash"},{"modelId":"gemini-2.5-flash-lite","name":"gemini-2.5-flash-lite"}],"currentModelId":"gemini-3-flash-preview"}}}
<<stdout>> {"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"1cf07f9c-eb75-4f90-aadc-4749025bbf96","update":{"sessionUpdate":"available_commands_update","availableCommands":[{"name":"memory","description":"Manage memory."},{"name":"memory show","description":"Shows the current memory contents."},{"name":"memory refresh","description":"Refreshes the memory from the source."},{"name":"memory list","description":"Lists the paths of the GEMINI.md files in use."},{"name":"memory add","description":"Add content to the memory."},{"name":"extensions","description":"Manage extensions."},{"name":"extensions list","description":"Lists all installed extensions."},{"name":"extensions explore","description":"Explore available extensions."},{"name":"extensions enable","description":"Enable an extension."},{"name":"extensions disable","description":"Disable an extension."},{"name":"extensions install","description":"Install an extension from a git repo or local path."},{"name":"extensions link","description":"Link an extension from a local path."},{"name":"extensions uninstall","description":"Uninstall an extension."},{"name":"extensions restart","description":"Restart an extension."},{"name":"extensions update","description":"Update an extension."},{"name":"init","description":"Analyzes the project and creates a tailored GEMINI.md file"},{"name":"restore","description":"Restore to a previous checkpoint, or list available checkpoints to restore. This will reset the conversation and file history to the state it was in when the checkpoint was created"},{"name":"restore list","description":"Lists all available checkpoints."}]}}}
<<stderr>> Keychain initialization encountered an error: Cannot find module '../build/Release/keytar.node'
<<stderr>> Require stack:
<<stderr>> - /opt/homebrew/Cellar/gemini-cli/0.35.2/libexec/lib/node_modules/@google/gemini-cli/node_modules/keytar/lib/keytar.js
<<stderr>> Using FileKeychain fallback for secure storage.
<<stderr>> Loaded cached credentials.
```

## Cross-reference: vendored ACP SDK method table

Confirmed directly from the bundled `@agentclientprotocol/sdk` (the same package gemini-cli links against) at
`/opt/homebrew/Cellar/gemini-cli/0.35.2/libexec/lib/node_modules/@google/gemini-cli/node_modules/@agentclientprotocol/sdk/dist/schema/index.js`:

```js
export const AGENT_METHODS = {
  authenticate: "authenticate",
  initialize: "initialize",
  session_cancel: "session/cancel",
  session_fork: "session/fork",
  session_list: "session/list",
  session_load: "session/load",
  session_new: "session/new",
  session_prompt: "session/prompt",
  session_resume: "session/resume",
  session_set_config_option: "session/set_config_option",
  session_set_mode: "session/set_mode",
  session_set_model: "session/set_model",
};
export const CLIENT_METHODS = {
  fs_read_text_file: "fs/read_text_file",
  fs_write_text_file: "fs/write_text_file",
  session_request_permission: "session/request_permission",
  session_update: "session/update",
  terminal_create: "terminal/create",
  terminal_kill: "terminal/kill",
  terminal_output: "terminal/output",
  terminal_release: "terminal/release",
  terminal_wait_for_exit: "terminal/wait_for_exit",
};
export const PROTOCOL_VERSION = 1;
```

These are the canonical wire strings. Agent-side methods are things the client (us) sends to gemini. Client-side methods are things gemini sends to us (requests or notifications). `session/update` and `session/cancel` are notifications; the rest are requests.

## Observations

- **`initialize` method name:** `initialize` (confirmed)
- **`initialize` request params shape:** `{ protocolVersion: 1, clientCapabilities: { fs: { readTextFile, writeTextFile }, terminal?: bool }, clientInfo?: { name, version, title? } }`. `clientCapabilities.fs` defaults to `{readTextFile:false,writeTextFile:false}` and `terminal` defaults to `false` if omitted. `_meta` optional.
- **`initialize` response shape:**
  - `protocolVersion: 1`
  - `authMethods: [{ id, name, description, _meta? }, ...]` — observed IDs: `oauth-personal`, `gemini-api-key`, `vertex-ai`, `gateway`
  - `agentInfo: { name: "gemini-cli", title: "Gemini CLI", version: "0.35.2" }`
  - `agentCapabilities: { loadSession: bool, promptCapabilities: { image, audio, embeddedContext }, mcpCapabilities: { http, sse } }`
  - No `modes`/`models` here — those arrive in the `session/new` response.
- **`session/new` method name:** `session/new` (with slash, confirmed). NOT `newSession` on the wire; `newSession` is only the SDK's JS method name.
- **`session/new` request params shape:** `{ cwd: string, mcpServers: McpServer[] }`. Empty array is accepted. `_meta` optional.
- **`session/new` response shape:**
  - `sessionId: string` — top-level, JSON path is `result.sessionId`. Observed UUID: `1cf07f9c-eb75-4f90-aadc-4749025bbf96`.
  - `modes: { availableModes: [{id,name,description}], currentModeId }` — observed modes: `default`, `autoEdit`, `yolo`, `plan`. Current: `default`.
  - `models: { availableModels: [{modelId,name,description?}], currentModelId }` — current default: `gemini-3-flash-preview`. Models include `auto-gemini-3`, `auto-gemini-2.5`, `gemini-3-pro-preview`, `gemini-3-flash-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`.
- **Auth behavior with only env vars:** Succeeded with no JSON-RPC error. On this machine gemini had cached OAuth credentials (stderr: `Loaded cached credentials.`). No `authenticate` call was required. If no creds are available the expected behavior (per SDK) is that `session/new` would raise and the bridge should call the `authenticate` method with a chosen `authMethods[].id`. The probe did not exercise the unauth path.
- **`session/prompt` method name (not yet tested):** `session/prompt` (confirmed from SDK schema — agent-side request).
- **`session/cancel` method name (not yet tested):** `session/cancel` (confirmed from SDK schema — agent-side **notification**, not a request; no response expected).
- **`session/update` notification shape (observed):** `{ jsonrpc:"2.0", method:"session/update", params: { sessionId, update: { sessionUpdate: <kind>, ...payload } } }`. The `update.sessionUpdate` discriminator tag names the kind. One kind observed live: `available_commands_update` (carries `availableCommands: [{name,description}]`). Other kinds per SDK include agent message chunks, tool call events, etc. — to be confirmed when exercising `session/prompt`.
- **Surprises / deviations from the plan's draft method names:**
  - Draft referred to method names casually; the wire names are unambiguously slash-separated (`session/new`, `session/prompt`, `session/cancel`, `session/update`, `session/request_permission`, `fs/read_text_file`, `fs/write_text_file`). Do NOT use camelCase wire names.
  - `session/cancel` is a **notification**, not a request — implementations must not wait for a response or use `id`.
  - `initialize` response does NOT include session modes or models. Those come with `session/new`. Any assumption that modes/models are known at initialize time is wrong.
  - `session/new` already emits a `session/update` notification (`available_commands_update`) before the bridge sends any prompt. The transport layer must be able to accept notifications interleaved between request responses from the moment the session is created.
  - gemini writes non-JSON lines to **stderr** at startup (keychain / credential logs). The bridge must not parse stderr as JSON-RPC; treat it as log data only.
  - `clientCapabilities.fs` is not `{ readTextFile: true, writeTextFile: true, ... }` by default — both default to `false`. The bridge must advertise them explicitly to receive `fs/read_text_file` / `fs/write_text_file` requests from gemini.

## Implications for implementation

1. **Wire names (Task 2 transport):** hard-code the exact strings from `AGENT_METHODS` / `CLIENT_METHODS` above. No camelCase variants.
2. **Framing (Task 2):** newline-delimited JSON, one JSON object per line, UTF-8, no `Content-Length` header. Writer appends `\n`; reader splits on `\n`.
3. **Notifications (Tasks 2, 3):** a JSON-RPC message with no `id` is a notification. The dispatcher must route `session/update` to the notification handler and must NOT attempt to match it to a pending request. `session/cancel` is also a notification (outbound, from bridge to gemini) — send it without an `id` and do not await.
4. **Session response parsing (Task 6 lifecycle):** `sessionId` lives at `response.result.sessionId`. Persist `modes.currentModeId` and `models.currentModelId` if we want to surface them.
5. **Capability advertisement (Task 5 FS proxy):** set `clientCapabilities.fs.readTextFile=true` and `writeTextFile=true` on initialize so gemini will actually issue `fs/read_text_file` / `fs/write_text_file`. Leave `terminal:false` for now (Task 5 scope does not include terminal proxy).
6. **Stderr handling (Tasks 2, 6):** read stderr on a separate thread and route to the bridge log only. Do not let stderr lines reach the JSON parser.
7. **Startup timing (Task 6):** gemini performs credential/keychain work before it's ready to respond. The bridge should not rely on immediate turnaround on the very first `initialize` — either wait for the first line on stdout or set a generous timeout (observed: response arrived within ~2–4 seconds on a warm machine with cached OAuth).
8. **Auth fallback (Task 6, future):** if `session/new` fails with an auth-related error, call `authenticate` with a selected `authMethods[].id`. This path is NOT exercised by this probe and remains unverified — flagged as follow-up.
9. **Initial `session/update` burst (Task 3):** expect notifications (e.g., `available_commands_update`) immediately after `session/new` returns, before any prompt is sent. The update handler must tolerate unknown `sessionUpdate` kinds and avoid crashing on kinds it doesn't care about.
