#if UNITY_EDITOR
using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;

/// <summary>
/// PirateUI Unity Bridge (C# Editor IPC Listener)
/// Spawns an asynchronous HTTP/TCP listener on 127.0.0.1:55558.
/// Dispatches editor reflection, scene queries, and asset refresh calls
/// to the Unity Main Thread via EditorApplication.update.
/// </summary>
[InitializeOnLoad]
public static class PirateUIBridge
{
    private const int PORT = 55558;
    private static HttpListener listener;
    private static Thread listenerThread;
    private static readonly ConcurrentQueue<Action> mainThreadQueue = new ConcurrentQueue<Action>();

    static PirateUIBridge()
    {
        EditorApplication.update -= ProcessMainThreadQueue;
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

    public static void StopServer()
    {
        try
        {
            if (listener != null && listener.IsListening)
            {
                listener.Stop();
                listener.Close();
                listener = null;
            }
        }
        catch (Exception) { }
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
            if (path == "/status" || path == "/")
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
                        executionResult = $"{{\"status\":\"error\",\"message\":\"{EscapeJson(e.Message)}\"}}";
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
            responseJson = $"{{\"status\":\"error\",\"message\":\"{EscapeJson(ex.Message)}\"}}";
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
                for (int i = 0; i < roots.Length; i++) names[i] = EscapeJson(roots[i].name);
                var listJson = "[\"" + string.Join("\",\"", names) + "\"]";
                return $"{{\"status\":\"success\",\"root_objects\":{listJson}}}";

            case "create_gameobject":
                var goName = string.IsNullOrEmpty(payload) ? "PirateUI_Entity" : payload;
                var go = new GameObject(goName);
                Undo.RegisterCreatedObjectUndo(go, "Create PirateUI GameObject");
                return $"{{\"status\":\"success\",\"name\":\"{EscapeJson(go.name)}\",\"instance_id\":{go.GetInstanceID()}}}";

            case "ping":
                return "{\"status\":\"success\",\"pong\":true}";

            default:
                return $"{{\"status\":\"error\",\"message\":\"Unknown command: {EscapeJson(command)}\"}}";
        }
    }

    private static string EscapeJson(string s)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
    }

    [Serializable]
    private class StatusResponse
    {
        public string status;
        public string unity_version;
        public string project_name;
        public string project_path;
        public bool is_playing;
    }

    [Serializable]
    private class CommandRequest
    {
        public string command;
        public string payload;
    }
}
#endif
