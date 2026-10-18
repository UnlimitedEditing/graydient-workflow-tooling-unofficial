# Handoff: PirateUI Unity Engine Support & Multi-Engine Architecture

**Date**: 2026-10-18  
**Subject**: Architectural Design & Implementation Blueprint for Unity 2022.3 LTS / Unity 6 Integration into PirateUI & Game Dev Agent  
**Status**: Ready for Implementation  
**Dependencies**: `studio/game_dev_bridge.py`, `studio/gemini_agent.py`, `studio/server.py`, `studio/static/app.js`, `studio/static/index.html`

---

## 1. Executive Summary & Objective

PirateUI currently integrates two major game engines via dedicated IPC mechanisms:
1. **Unreal Engine 5.8**: Live duplex control over TCP socket (`127.0.0.1:55557`) via the VAIL (Virtual Agent Interface Layer) C++ plugin.
2. **Godot Engine 4.6.1**: Tool execution via the Godot MCP (Model Context Protocol) Node.js runner interfacing with Godot Console binary and `ToolRegistry.js`.

The objective of this handoff is to design and implement **Unity Engine support** (targeting Unity 2022.3 LTS and Unity 6), completing the "Big Three" game engine triage. This bridge enables:
- Live command dispatch and editor reflection (inspecting hierarchy, querying assets, invoking menu items, creating gameobjects, compiling C# scripts).
- Direct 3D mesh deployment (`.glb`, `.ply`, `.fbx`) from PirateUI's M3DS decoder and render studio into Unity projects with automated asset database refresh.
- Integration into the **Game Dev Agent**'s decoupled Gemini session without introducing workflow/Graveyard prompt bloat.

---

## 2. Unity Bridge Architecture: Analysis & Design

Three architectural models were evaluated for connecting PirateUI to the Unity Editor:

### Option A: Unity Editor TCP/HTTP Listener (Recommended - The "VAIL Pattern")
* **Mechanism**: A lightweight C# Editor script (`PirateUIBridge.cs`) located in an `Editor/` folder of the target Unity project. When the Unity Editor is running, it spawns an asynchronous `HttpListener` or raw TCP socket on `127.0.0.1:55558`.
* **Execution**: Commands received over TCP/HTTP are queued onto the Unity Main Thread using `EditorApplication.update` and executed synchronously against the `UnityEditor` and `UnityEngine` APIs.
* **Pros**:
  - Near-zero latency (<5ms round trip).
  - Live inspection of open scenes, active game objects, materials, and inspector properties.
  - Zero external package dependencies (uses native .NET `System.Net.HttpListener`).
  - Mirrors the exact ergonomics of the Unreal Engine VAIL bridge (`127.0.0.1:55557`).
* **Cons**: Requires the Unity Editor to be open with the script installed in the project.

### Option B: Unity Model Context Protocol (MCP) Server
* **Mechanism**: A Node.js or Python MCP server that interfaces with Unity via standard MCP stdio JSON-RPC.
* **Execution**: Utilizes open-source Unity MCP tools (e.g. `unity-mcp` or Unity Roslyn analyzers).
* **Pros**: Direct alignment with Godot MCP's architecture.
* **Cons**: Unity does not have an official native stdio interface like Godot's console; an internal Editor socket is still required under the hood to talk to the running editor.

### Option C: Unity Headless BatchMode CLI
* **Mechanism**: Executing `Unity.exe -batchmode -quit -executeMethod PirateUIBridge.ExecuteCommand -projectPath ...`
* **Pros**: Can run without an active Editor GUI window (useful in CI or headless environments).
* **Cons**: Severe cold-start overhead (15-35 seconds per invocation while the Unity engine initializes and imports assets). Unacceptable for interactive chat agent workflows.

### Selected Hybrid Architecture
- **Primary Live Channel**: Lightweight Editor TCP/HTTP Socket (`127.0.0.1:55558`) for real-time interaction.
- **Fallback / Cold Channel**: BatchMode CLI execution for headless asset compilation or project verification when the editor is closed.

```
┌─────────────────────────────────────────────────────────────┐
│                 PirateUI (Python / FastAPI)                 │
│                 studio/game_dev_bridge.py                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │ HTTP / JSON-RPC over 127.0.0.1:55558 │
            ▼                                     ▼
┌─────────────────────────────────┐   ┌──────────────────────────────┐
│       Unity Editor (Active)     │   │   Unity.exe -batchmode       │
│  PirateUIBridge.cs (EditorWindow)│   │   (Headless Fallback)        │
│  - MainThreadQueue dispatch     │   └──────────────────────────────┘
│  - AssetDatabase.Refresh()      │
│  - GameObject & Component API   │
└─────────────────────────────────┘
```

---

## 3. Unity Editor Plugin Specification (`PirateUIBridge.cs`)

Create a drop-in C# Editor script to be placed in `Assets/Editor/PirateUI/PirateUIBridge.cs` in any Unity project:

```csharp
#if UNITY_EDITOR
using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class PirateUIBridge
{
    private const int PORT = 55558;
    private static HttpListener listener;
    private static Thread listenerThread;
    private static readonly ConcurrentQueue<Action> mainThreadQueue = new ConcurrentQueue<Action>();

    static PirateUIBridge()
    {
        EditorApplication.update += ProcessMainThreadQueue;
        StartServer();
    }

    public static void StartServer()
    {
        if (listener != null && listener.IsListening) return;

        try
        {
            listener = new HttpListener();
            listener.Prefixes.Add($"http://127.0.0.1:{PORT}/");
            listener.Start();
            listenerThread = new Thread(ListenLoop) { IsBackground = true };
            listenerThread.Start();
            Debug.Log($"[PirateUI] Bridge active on http://127.0.0.1:{PORT}/");
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[PirateUI] Failed to start bridge on port {PORT}: {ex.Message}");
        }
    }

    private static void ProcessMainThreadQueue()
    {
        while (mainThreadQueue.TryDequeue(out var action))
        {
            try { action(); }
            catch (Exception ex) { Debug.LogError($"[PirateUI] Error executing action: {ex}"); }
        }
    }

    private static void ListenLoop()
    {
        while (listener != null && listener.IsListening)
        {
            try
            {
                var context = listener.GetContext();
                ThreadPool.QueueUserWorkItem((_) => HandleRequest(context));
            }
            catch (HttpListenerException) { break; }
            catch (Exception ex) { Debug.LogError($"[PirateUI] Listener error: {ex}"); }
        }
    }

    private static void HandleRequest(HttpListenerContext context)
    {
        var request = context.Request;
        var response = context.Response;

        if (request.HttpMethod == "OPTIONS")
        {
            response.AddHeader("Access-Control-Allow-Origin", "*");
            response.AddHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
            response.AddHeader("Access-Control-Allow-Headers", "Content-Type");
            response.StatusCode = 200;
            response.Close();
            return;
        }

        string responseJson = "{}";
        int statusCode = 200;

        try
        {
            string path = request.Url.AbsolutePath.ToLowerInvariant();
            if (path == "/status")
            {
                responseJson = JsonUtility.ToJson(new StatusResponse {
                    status = "online",
                    unity_version = Application.unityVersion,
                    project_name = Application.productName,
                    project_path = Directory.GetCurrentDirectory(),
                    is_playing = EditorApplication.isPlaying
                });
            }
            else if (path == "/command" && request.HttpMethod == "POST")
            {
                using var reader = new StreamReader(request.InputStream, request.ContentEncoding);
                string body = reader.ReadToEnd();
                var cmd = JsonUtility.FromJson<CommandRequest>(body);

                var waitHandle = new ManualResetEvent(false);
                string executionResult = "";

                mainThreadQueue.Enqueue(() =>
                {
                    try
                    {
                        executionResult = ExecuteEditorCommand(cmd.command, cmd.payload);
                    }
                    catch (Exception e)
                    {
                        executionResult = $"{{\"status\":\"error\",\"message\":\"{e.Message}\"}}";
                    }
                    finally
                    {
                        waitHandle.Set();
                    }
                });

                waitHandle.WaitOne(10000); // 10s timeout
                responseJson = executionResult;
            }
            else
            {
                statusCode = 404;
                responseJson = "{\"status\":\"error\",\"message\":\"Not found\"}";
            }
        }
        catch (Exception ex)
        {
            statusCode = 500;
            responseJson = $"{{\"status\":\"error\",\"message\":\"{ex.Message}\"}}";
        }

        byte[] buf = Encoding.UTF8.GetBytes(responseJson);
        response.ContentType = "application/json";
        response.StatusCode = statusCode;
        response.AddHeader("Access-Control-Allow-Origin", "*");
        response.OutputStream.Write(buf, 0, buf.Length);
        response.Close();
    }

    private static string ExecuteEditorCommand(string command, string payload)
    {
        switch (command)
        {
            case "refresh_assets":
                AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
                return "{\"status\":\"success\",\"message\":\"AssetDatabase refreshed\"}";

            case "get_scene_hierarchy":
                var roots = UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects();
                var names = new string[roots.Length];
                for (int i = 0; i < roots.Length; i++) names[i] = roots[i].name;
                return $"{{\"status\":\"success\",\"root_objects\":{JsonUtility.ToJson(names)}}}";

            case "create_gameobject":
                var go = new GameObject(string.IsNullOrEmpty(payload) ? "PirateUI_Entity" : payload);
                Undo.RegisterCreatedObjectUndo(go, "Create PirateUI GameObject");
                return $"{{\"status\":\"success\",\"name\":\"{go.name}\",\"instance_id\":{go.GetInstanceID()}}}";

            case "ping":
                return "{\"status\":\"success\",\"pong\":true}";

            default:
                return $"{{\"status\":\"error\",\"message\":\"Unknown command: {command}\"}}";
        }
    }

    [Serializable] private class StatusResponse { public string status; public string unity_version; public string project_name; public string project_path; public bool is_playing; }
    [Serializable] private class CommandRequest { public string command; public string payload; }
}
#endif
```

---

## 4. Backend Implementation in PirateUI

### 4.1. Extensions to `studio/game_dev_bridge.py`

Add Unity socket checks, command dispatch, and asset deployment targets:

```python
# Unity Configuration
UNITY_HOST = "127.0.0.1"
UNITY_PORT = 55558
UNITY_HUB_PATH = Path(r"C:\Program Files\Unity\Hub\Editor")

def check_unity_connection(timeout: float = 1.0) -> Dict[str, Any]:
    """Probes whether Unity Editor is active with PirateUIBridge listening on 55558."""
    import urllib.request
    status = {
        "engine": "Unity",
        "plugin": "PirateUI Unity Bridge",
        "host": UNITY_HOST,
        "port": UNITY_PORT,
        "online": False,
        "details": None
    }
    try:
        url = f"http://{UNITY_HOST}:{UNITY_PORT}/status"
        req = urllib.request.Request(url, headers={"User-Agent": "PirateUI"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                status["online"] = True
                status["details"] = data
    except Exception as e:
        status["error"] = str(e)
    return status

def send_unity_command(command: str, payload: str = "", timeout: float = 10.0) -> Dict[str, Any]:
    """Sends an editor command to Unity via the local bridge."""
    import urllib.request
    url = f"http://{UNITY_HOST}:{UNITY_PORT}/command"
    body = json.dumps({"command": command, "payload": payload}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": f"Unity bridge error: {str(e)}"}
```

### 4.2. Updating `deploy_mesh_to_game()`
Add Unity target routing:
```python
elif target_engine in ["unity", "unity-engine"]:
    # Defaults to custom_project_dir or standard Unity export folder
    dest_dir = Path(custom_project_dir) if custom_project_dir else (BASE_DIR / "game_exports" / "unity_assets")
```
When deployed to an active Unity project's `Assets/` directory, invoke `send_unity_command("refresh_assets")` so Unity immediately reindexes and compiles the mesh.

### 4.3. Exposing FastAPI Endpoints in `studio/server.py`
Add:
- `GET /api/gamedev/unity/status` -> `check_unity_connection()`
- `POST /api/gamedev/unity/command` -> `send_unity_command(req.command, req.payload)`

---

## 5. Integrating Unity into the Game Dev Agent LLM Persona

In `studio/gemini_agent.py`, update `_build_gamedev_system_instruction()`:
- Add Unity C# (MonoBehaviour lifecycle, ScriptableObjects, Transform hierarchy, Prefabs, `[SerializeField]`, and Unity 6 DOTS/JobSystem conventions).
- Explicitly enforce **zero ComfyUI bloat**: Keep ComfyUI, Graveyard KI-007, and node schemas strictly confined to the Workflow Engineer.
- Register Unity tool call signatures:
  - `unity_get_status()`
  - `unity_send_command(command: str, payload: str)`
  - `unity_deploy_asset(mesh_path: str, project_assets_dir: str)`

---

## 6. Frontend UI Integration (`tab-gamedev`)

1. **Header Status Pill**:
   Add a third engine status pill next to Godot and UE5:
   `<div class="engine-pill" id="pill-unity"><span class="engine-indicator offline"></span><span class="engine-label">Unity:</span><span class="engine-val">Offline</span></div>`
2. **Left Deck Deck Cards**:
   Add a dedicated "Unity Engine Controller" accordion card with:
   - Hierarchy inspector button (`get_scene_hierarchy`).
   - Create GameObject quick action.
   - Force Asset Refresh button (`refresh_assets`).
   - Custom command sender.
3. **Asset Deployment Dropdown**:
   Add `Unity (Assets/Imports)` alongside `Godot (res://)` and `Unreal Engine (Content/Imported_PirateUI)`.

---

## 7. Verification & Acceptance Testing Protocol

1. **Socket Probe Test**:
   - With Unity closed: `GET /api/gamedev/unity/status` returns `{"online": false}`.
   - Install `PirateUIBridge.cs` in `Assets/Editor/PirateUI/` of any Unity project and launch the Editor.
   - `GET /api/gamedev/unity/status` returns `{"online": true, "unity_version": "2022.3...", "project_name": "..."}`.
2. **Asset Import Round-trip**:
   - In PirateUI M3DS viewer, click "Deploy Asset" targeting Unity.
   - Verify mesh file appears in `Assets/Imports/` and Unity triggers `AssetDatabase.Refresh()` automatically.
3. **Chat Command Execution**:
   - In Game Dev Agent chat, instruct: *"Create a new GameObject named PirateUI_Spawner in Unity and query the active scene hierarchy."*
   - Verify Gemini executes the tool call and reports back the created instance ID without any ComfyUI hallucination.
