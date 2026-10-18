/**
 * Graydient Studio Frontend Application Logic.
 * Orchestrates Three.js 3D Viewport, Gemini Agent Chat, M3DS Auto-Decoder,
 * Render Library, and Zero-Defect Linter.
 */

import { StudioViewer3D } from './viewer3d.js';

let viewer = null;
let currentExtractedAsset = null;

document.addEventListener('DOMContentLoaded', () => {
  try {
    initViewer();
  } catch (err) {
    console.error("Three.js Viewer initialization error:", err);
  }
  initTabs();
  initM3DS();
  initAgent();
  initGameDev();
  initRenders();
  initLinter();
  initDiagnostics();
  initSettings();
  checkStatus();
});

// ── 1. 3D Viewer Initialization ───────────────────────────────────────────
function initViewer() {
  viewer = new StudioViewer3D('three-viewport');

  // Controls
  const wireframeToggle = document.getElementById('wireframe-toggle');
  if (wireframeToggle) {
    wireframeToggle.addEventListener('change', (e) => {
      viewer.toggleWireframe(e.target.checked);
    });
  }

  const resetCamBtn = document.getElementById('reset-cam-btn');
  if (resetCamBtn) {
    resetCamBtn.addEventListener('click', () => {
      if (viewer.currentModel) viewer.frameObject(viewer.currentModel);
    });
  }

  // Gizmo Mode Buttons (W, E, R)
  const btnT = document.getElementById('gizmo-translate-btn');
  const btnR = document.getElementById('gizmo-rotate-btn');
  const btnS = document.getElementById('gizmo-scale-btn');

  function setMode(mode, activeBtn) {
    viewer.setGizmoMode(mode);
    [btnT, btnR, btnS].forEach(b => b && b.classList.remove('active'));
    if (activeBtn) activeBtn.classList.add('active');
  }

  if (btnT) btnT.addEventListener('click', () => setMode('translate', btnT));
  if (btnR) btnR.addEventListener('click', () => setMode('rotate', btnR));
  if (btnS) btnS.addEventListener('click', () => setMode('scale', btnS));

  // Delete Selected Prop
  const deleteBtn = document.getElementById('delete-asset-btn');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      viewer.deleteSelectedAsset();
      updateSceneOutliner();
    });
  }

  // Export Combined Scene (.glb)
  const exportSceneBtn = document.getElementById('export-scene-btn');
  if (exportSceneBtn) {
    exportSceneBtn.addEventListener('click', () => {
      if (viewer.assets.length === 0) {
        alert('No 3D props staged in scene to export.');
        return;
      }
      viewer.exportCombinedScene('staged_environment.glb');
    });
  }
}

function updateSceneOutliner() {
  const listEl = document.getElementById('staged-assets-list');
  if (!listEl) return;
  listEl.innerHTML = '';

  if (viewer.assets.length === 0) {
    listEl.innerHTML = '<div style="font-size:11.5px;color:var(--text-dim);padding:8px 0;">No props staged yet. Load or drop assets to build environments.</div>';
    return;
  }

  viewer.assets.forEach((a, idx) => {
    const item = document.createElement('div');
    item.className = 'staged-asset-item' + (viewer.selectedAsset && viewer.selectedAsset.id === a.id ? ' selected' : '');
    item.innerHTML = `
      <span>📦 ${a.name || 'Prop ' + (idx + 1)}</span>
      <span style="font-size:10px;color:var(--text-dim);text-transform:uppercase;">${a.type}</span>
    `;
    item.addEventListener('click', () => {
      viewer.selectAsset(a.id);
      updateSceneOutliner();
    });
    listEl.appendChild(item);
  });
}

// ── 2. Tab Navigation ─────────────────────────────────────────────────────
function initTabs() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetId = tab.getAttribute('data-tab');
      const panel = document.getElementById(targetId);
      if (panel) {
        panel.classList.add('active');
        if (targetId === 'tab-m3ds' && viewer) {
          setTimeout(() => viewer.onResize(), 50);
        }
        if (targetId === 'tab-gamedev' && window.probeGameDevEngines) {
          window.probeGameDevEngines();
        }
      }
    });
  });
}

// ── 3. M3DS Auto-Decoder & Converter ──────────────────────────────────────
function initM3DS() {
  const dropZone = document.getElementById('m3ds-drop-zone');
  const fileInput = document.getElementById('m3ds-file-input');

  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      await uploadAndProcessM3DS(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', async () => {
    if (fileInput.files.length > 0) {
      await uploadAndProcessM3DS(fileInput.files[0]);
    }
  });

  // Quick Test Buttons
  const sampleSplatBtn = document.getElementById('load-sample-splat');
  if (sampleSplatBtn) {
    sampleSplatBtn.addEventListener('click', () => loadSampleByName('v9oKd0-workflow3848v4-0-Z3G2OT8A7.png'));
  }

  const sampleScoreBtn = document.getElementById('load-sample-score');
  if (sampleScoreBtn) {
    sampleScoreBtn.addEventListener('click', () => loadSampleByName('fur_elise_metal_score.png'));
  }

  // Export Decoded Asset Button
  const dlBtn = document.getElementById('download-extracted-btn');
  if (dlBtn) {
    dlBtn.addEventListener('click', () => {
      if (currentExtractedAsset && currentExtractedAsset.extracted_path) {
        const url = `/files/${encodeURIComponent(currentExtractedAsset.extracted_filename)}`;
        const a = document.createElement('a');
        a.href = url;
        a.download = currentExtractedAsset.extracted_filename;
        a.click();
      }
    });
  }
}

async function uploadAndProcessM3DS(file) {
  const formData = new FormData();
  formData.append('file', file);

  updateViewportStatus(`Unpacking M3DS steganography: ${file.name}...`);
  try {
    const res = await fetch('/api/m3ds/upload', { method: 'POST', body: formData });
    const data = await res.json();
    handleM3DSResult(data);
  } catch (err) {
    alert('Failed to decode M3DS: ' + err.message);
  }
}

async function loadSampleByName(filename) {
  updateViewportStatus(`Loading local sample: ${filename}...`);
  try {
    const fd = new FormData();
    fd.append('sample_name', filename);
    const res = await fetch('/api/render/import-sample', { method: 'POST', body: fd });
    const job = await res.json();
    if (job.m3ds_assets && job.m3ds_assets.length > 0) {
      handleM3DSResult(job.m3ds_assets[0]);
    } else {
      alert('Sample did not contain an M3DS payload');
    }
  } catch (err) {
    alert('Error loading sample: ' + err.message);
  }
}

function handleM3DSResult(meta) {
  currentExtractedAsset = meta;
  const infoCard = document.getElementById('decoded-info-card');
  const typeBadge = document.getElementById('decoded-type-badge');
  const sizeLabel = document.getElementById('decoded-size');
  const fnameLabel = document.getElementById('decoded-filename');
  const hintEl = document.getElementById('three-hint');
  const jsonView = document.getElementById('json-viewport');

  if (!meta.is_m3ds) {
    alert('This image does not contain an M3DS steganography container.');
    return;
  }

  infoCard.style.display = 'block';
  typeBadge.textContent = meta.category === '3d_mesh' ? '3D GLB Mesh' :
                          meta.category === '3d_pointcloud' ? 'Gaussian Splat (.ply)' : 'Score JSON';
  sizeLabel.textContent = `${(meta.size_bytes / 1024).toFixed(1)} KB`;
  fnameLabel.textContent = meta.extracted_filename;

  const fileUrl = `/files/${encodeURIComponent(meta.extracted_filename)}`;

  if (meta.category === '3d_mesh') {
    if (hintEl) hintEl.style.display = 'none';
    if (jsonView) jsonView.style.display = 'none';
    updateViewportStatus(`Staging 3D Prop: ${meta.extracted_filename}`);
    viewer.addGLBToScene(fileUrl, meta.extracted_filename, () => {
      updateSceneOutliner();
    });
  } else if (meta.category === '3d_pointcloud') {
    if (hintEl) hintEl.style.display = 'none';
    if (jsonView) jsonView.style.display = 'none';
    updateViewportStatus(`Rendering Point Cloud: ${meta.extracted_filename}`);
    viewer.loadPLY(fileUrl);
    updateSceneOutliner();
  } else if (meta.category === 'score_json') {
    if (hintEl) hintEl.style.display = 'none';
    if (jsonView) {
      jsonView.style.display = 'block';
      fetch(fileUrl)
        .then(r => r.json())
        .then(data => {
          document.getElementById('json-score-code').textContent = JSON.stringify(data, null, 2);
        });
    }
    updateViewportStatus(`Decoded Musical Score: ${meta.extracted_filename}`);
  }
}

function updateViewportStatus(text) {
  const el = document.getElementById('viewport-status');
  if (el) el.textContent = text;
}

// ── 4. Gemini Flash Agent Chat ────────────────────────────────────────────
function initAgent() {
  const input = document.getElementById('agent-input');
  const sendBtn = document.getElementById('agent-send-btn');
  const messages = document.getElementById('chat-messages');

  async function sendMessage(text) {
    const msg = text || input.value.trim();
    if (!msg) return;

    // Append User Message
    appendMessage('user', msg);
    if (!text) input.value = '';

    // Append Temporary Assistant Bubble
    const typingMsg = appendMessage('assistant', 'Thinking with Gemini Flash (1M Context)...');

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      let fullText = '';
      if (data.responses) {
        data.responses.forEach(chunk => {
          if (chunk.text) fullText += chunk.text;
          if (chunk.message) fullText += `\n*${chunk.message}*\n`;
        });
      }
      typingMsg.innerHTML = formatMarkdown(fullText || 'No response returned.');
    } catch (err) {
      typingMsg.innerHTML = `<span style="color:var(--accent-rose)">Error calling Gemini Flash: ${err.message}</span>`;
    }
  }

  sendBtn.addEventListener('click', () => sendMessage());
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Suggestion Chips
  document.querySelectorAll('.chip-suggestion').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      sendMessage(prompt);
    });
  });
}

function appendMessage(role, text) {
  const messages = document.getElementById('chat-messages');
  const msgEl = document.createElement('div');
  msgEl.className = `message msg-${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = formatMarkdown(text);
  msgEl.appendChild(bubble);
  messages.appendChild(msgEl);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function formatMarkdown(text) {
  if (!text) return '';
  // 1. Triple backtick code blocks
  let formatted = text.replace(/```([a-zA-Z0-9_\-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre style="background:rgba(0,0,0,0.5);border:1px solid var(--border-color);padding:10px;border-radius:6px;overflow-x:auto;margin:8px 0;"><code style="font-family:'Fira Code',monospace;font-size:11.5px;color:var(--accent-cyan);">${escapeHtml(code)}</code></pre>`;
  });
  // 2. Bold & Italic
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // 3. Inline backtick code
  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.4);padding:2px 5px;border-radius:4px;color:var(--accent-cyan);font-family:\'Fira Code\',monospace;font-size:11.5px;">$1</code>');
  // 4. Line breaks
  formatted = formatted.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
  return formatted;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── 5. Render Studio & Library ────────────────────────────────────────────
function initRenders() {
  const form = document.getElementById('render-form');
  const refreshBtn = document.getElementById('refresh-renders-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      workflow_slug: document.getElementById('render-slug').value.trim(),
      prompt: document.getElementById('render-prompt').value.trim(),
      slot1: document.getElementById('render-slot1').value.trim() || null,
      slot2: document.getElementById('render-slot2').value.trim() || null
    };

    try {
      const res = await fetch('/api/render/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const job = await res.json();
      alert(`Render launched! Job ID: ${job.id}`);
      loadRenders();
    } catch (err) {
      alert('Error submitting render: ' + err.message);
    }
  });

  refreshBtn.addEventListener('click', () => loadRenders());
  loadRenders();
}

async function loadRenders() {
  const grid = document.getElementById('renders-grid');
  try {
    const res = await fetch('/api/renders');
    const data = await res.json();
    grid.innerHTML = '';

    if (!data.renders || data.renders.length === 0) {
      grid.innerHTML = '<div style="color:var(--text-dim);grid-column:1/-1;padding:20px;text-align:center;">No renders in library yet. Launch one on the left or drop an M3DS image in the 3D Viewer tab!</div>';
      return;
    }

    data.renders.forEach(job => {
      const card = document.createElement('div');
      card.className = 'render-card';

      const has3D = job.m3ds_assets && job.m3ds_assets.length > 0;
      const statusColor = job.status === 'SUCCESS' ? 'var(--accent-emerald)' :
                          job.status === 'RUNNING' ? 'var(--accent-amber)' : 'var(--accent-rose)';

      card.innerHTML = `
        <div class="render-card-thumb">
          ${has3D ? '<span style="font-size:32px;">🧊</span>' : '<span style="font-size:32px;">🖼️</span>'}
        </div>
        <div style="font-weight:700;font-size:12px;color:var(--accent-cyan);">${job.workflow}</div>
        <div style="font-size:11.5px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${job.prompt}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto;">
          <span style="font-size:10px;font-weight:700;color:${statusColor};">${job.status}</span>
          ${has3D ? `<button class="btn-sm inspect-3d-btn" style="color:var(--accent-cyan);border-color:var(--accent-cyan);">Inspect 3D</button>` : ''}
        </div>
      `;

      if (has3D) {
        const btn = card.querySelector('.inspect-3d-btn');
        btn.addEventListener('click', () => {
          // Switch to M3DS tab
          document.querySelector('[data-tab="tab-m3ds"]').click();
          handleM3DSResult(job.m3ds_assets[0]);
        });
      }

      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading renders:', err);
  }
}

// ── 6. Linter & Templates ─────────────────────────────────────────────────
function initLinter() {
  const tplList = document.getElementById('template-list');
  const editor = document.getElementById('code-editor');
  const runLintBtn = document.getElementById('run-linter-btn');
  const statusBadge = document.getElementById('linter-status-badge');
  const resultsArea = document.getElementById('linter-results-area');
  const issuesList = document.getElementById('linter-issues-list');

  // Load templates
  fetch('/api/templates')
    .then(r => r.json())
    .then(data => {
      tplList.innerHTML = '';
      data.templates.forEach((tpl, idx) => {
        const item = document.createElement('div');
        item.className = 'template-item' + (idx === 0 ? ' active' : '');
        item.textContent = tpl.name;
        item.addEventListener('click', () => {
          document.querySelectorAll('.template-item').forEach(i => i.classList.remove('active'));
          item.classList.add('active');
          fetch(`/api/template/${tpl.name}`)
            .then(r => r.json())
            .then(d => { editor.value = d.content; });
        });
        tplList.appendChild(item);
      });

      // Load first template by default
      if (data.templates.length > 0) {
        fetch(`/api/template/${data.templates[0].name}`)
          .then(r => r.json())
          .then(d => { editor.value = d.content; });
      }
    });

  runLintBtn.addEventListener('click', async () => {
    const code = editor.value;
    statusBadge.textContent = 'Linting...';
    try {
      const res = await fetch('/api/agent/lint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      const data = await res.json();
      resultsArea.style.display = 'block';

      if (data.is_valid) {
        statusBadge.textContent = '✓ PASS (0 Errors)';
        statusBadge.className = 'badge-tag';
        issuesList.innerHTML = '<div style="color:var(--accent-emerald);font-size:12px;">All 25+ pre-flight checks passed! Workflow graph conforms to Graydient standards.</div>';
      } else {
        statusBadge.textContent = `⚠ ${data.error_count || 1} Errors`;
        statusBadge.className = 'badge-tag badge-err';
        issuesList.innerHTML = '';
        if (data.issues) {
          data.issues.forEach(iss => {
            const el = document.createElement('div');
            el.style.cssText = 'padding:6px;border-bottom:1px solid var(--border-color);font-size:11.5px;';
            el.innerHTML = `<span style="color:var(--accent-rose);font-weight:700;">[${iss.rule}]</span> ${iss.message}`;
            issuesList.appendChild(el);
          });
        }
      }
    } catch (err) {
      alert('Lint error: ' + err.message);
    }
  });
}

// ── 7. Diagnostics ────────────────────────────────────────────────────────
function initDiagnostics() {
  const runBtn = document.getElementById('run-diagnose-btn');
  const input = document.getElementById('diagnose-input');
  const resultCard = document.getElementById('diagnose-result');
  const bodyEl = document.getElementById('diag-body');

  runBtn.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) {
      alert('Please paste a log to diagnose.');
      return;
    }

    try {
      const res = await fetch('/api/agent/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log_text: text })
      });
      const data = await res.json();
      resultCard.style.display = 'block';
      bodyEl.innerHTML = `
        <div style="font-weight:700;color:var(--accent-cyan);margin-bottom:6px;">${data.summary || 'Graveyard Diagnostic Match'}</div>
        <div style="color:var(--text-main);font-size:12px;margin-bottom:8px;">${data.root_cause || data.analysis || 'Identified pattern.'}</div>
        <div style="background:rgba(0,242,254,0.05);border:1px solid var(--accent-cyan);padding:10px;border-radius:6px;color:var(--accent-emerald);font-size:12px;">
          <strong>Recommended Fix:</strong> ${data.recommendation || data.fix || 'Check container requirements.'}
        </div>
      `;
    } catch (err) {
      alert('Diagnosis failed: ' + err.message);
    }
  });
}

// ── 8. Settings Modal ─────────────────────────────────────────────────────
function initSettings() {
  const modal = document.getElementById('settings-modal');
  const openBtn = document.getElementById('open-settings-btn');
  const closeBtn = document.getElementById('close-settings-btn');
  const saveBtn = document.getElementById('save-key-btn');
  const keyInput = document.getElementById('settings-key-input');

  openBtn.addEventListener('click', () => { modal.style.display = 'flex'; });
  closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });

  saveBtn.addEventListener('click', async () => {
    const key = keyInput.value.trim();
    if (!key) return;

    try {
      const res = await fetch('/api/settings/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();
      modal.style.display = 'none';
      checkStatus();
      alert('Gemini API Key saved successfully!');
    } catch (err) {
      alert('Failed to save key: ' + err.message);
    }
  });
}

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const pill = document.getElementById('pill-ai');
    const text = document.getElementById('ai-status-text');
    if (data.has_gemini_key) {
      text.textContent = 'Gemini 3.8 Flash: Active (1M)';
      pill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      pill.style.color = 'var(--accent-emerald)';
    } else {
      text.textContent = 'Gemini 3.8 Flash: Key Needed';
      pill.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      pill.style.color = 'var(--accent-amber)';
    }
  } catch (err) {
    console.error('Status check error:', err);
  }
}

// ── 9. Game Dev Agent (VAIL + Godot MCP) ──────────────────────────────────
function initGameDev() {
  const vailBadge = document.getElementById('vail-deck-badge');
  const godotBadge = document.getElementById('godot-deck-badge');
  const probeVailBtn = document.getElementById('probe-vail-btn');
  const probeGodotBtn = document.getElementById('probe-godot-btn');

  const vailCmdSelect = document.getElementById('vail-cmd-select');
  const vailCmdArgs = document.getElementById('vail-cmd-args');
  const dispatchVailBtn = document.getElementById('dispatch-vail-btn');

  const godotToolSelect = document.getElementById('godot-tool-select');
  const godotToolArgs = document.getElementById('godot-tool-args');
  const dispatchGodotBtn = document.getElementById('dispatch-godot-btn');

  const bridgeDeployBtn = document.getElementById('bridge-deploy-btn');
  const bridgeEngineSelect = document.getElementById('bridge-engine-select');
  const bridgeStatusNote = document.getElementById('bridge-status-note');

  const gdInput = document.getElementById('gamedev-input');
  const gdSendBtn = document.getElementById('gamedev-send-btn');

  // Probe engines
  async function probeEngines() {
    try {
      const res = await fetch('/api/gamedev/status');
      const data = await res.json();

      // VAIL
      const vailDot = document.getElementById('vail-dot');
      const vailText = document.getElementById('vail-status-text');
      if (data.vail && data.vail.online) {
        if (vailBadge) {
          vailBadge.textContent = 'Online (55557)';
          vailBadge.className = 'badge-tag';
          vailBadge.style.color = 'var(--accent-emerald)';
        }
        if (vailDot) vailDot.className = 'status-dot dot-online';
        if (vailText) vailText.textContent = 'UE5 VAIL: Online';
      } else {
        if (vailBadge) {
          vailBadge.textContent = 'Offline';
          vailBadge.className = 'badge-tag badge-err';
        }
        if (vailDot) vailDot.className = 'status-dot dot-offline';
        if (vailText) vailText.textContent = 'UE5 VAIL: Offline';
      }

      // Godot
      const godotDot = document.getElementById('godot-dot');
      const godotText = document.getElementById('godot-status-text');
      if (data.godot && data.godot.online) {
        if (godotBadge) {
          godotBadge.textContent = `Online (${data.godot.version || '4.6.1'})`;
          godotBadge.className = 'badge-tag';
          godotBadge.style.color = 'var(--accent-cyan)';
        }
        if (godotDot) godotDot.className = 'status-dot dot-online';
        if (godotText) godotText.textContent = `Godot MCP: ${data.godot.version || '4.6.1'}`;
      } else {
        if (godotBadge) {
          godotBadge.textContent = 'Missing Config';
          godotBadge.className = 'badge-tag badge-err';
        }
        if (godotDot) godotDot.className = 'status-dot dot-offline';
        if (godotText) godotText.textContent = 'Godot MCP: Offline';
      }
    } catch (err) {
      console.error('Failed to probe engines:', err);
    }
  }

  window.probeGameDevEngines = probeEngines;
  if (probeVailBtn) probeVailBtn.addEventListener('click', probeEngines);
  if (probeGodotBtn) probeGodotBtn.addEventListener('click', probeEngines);

  // Dispatch VAIL command
  if (dispatchVailBtn) {
    dispatchVailBtn.addEventListener('click', async () => {
      const cmd = vailCmdSelect.value;
      let params = {};
      try {
        if (vailCmdArgs.value.trim()) params = JSON.parse(vailCmdArgs.value.trim());
      } catch (err) {
        alert('Invalid JSON in arguments: ' + err.message);
        return;
      }

      appendGameDevMessage('user', `Dispatch VAIL Command: <code>${cmd}</code>`);
      const bubble = appendGameDevMessage('assistant', `Dispatching <code>${cmd}</code> to Unreal Engine (TCP 55557)...`);

      try {
        const res = await fetch('/api/gamedev/vail/exec', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd, params })
        });
        const data = await res.json();
        bubble.innerHTML = formatMarkdown(`**VAIL Response for \`${cmd}\`:**\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``);
      } catch (err) {
        bubble.innerHTML = `<span style="color:var(--accent-rose)">VAIL Error: ${err.message}</span>`;
      }
    });
  }

  // Dispatch Godot MCP Tool
  if (dispatchGodotBtn) {
    dispatchGodotBtn.addEventListener('click', async () => {
      const tool = godotToolSelect.value;
      let params = {};
      try {
        if (godotToolArgs.value.trim()) params = JSON.parse(godotToolArgs.value.trim());
      } catch (err) {
        alert('Invalid JSON in arguments: ' + err.message);
        return;
      }

      appendGameDevMessage('user', `Run Godot MCP Tool: <code>${tool}</code>`);
      const bubble = appendGameDevMessage('assistant', `Executing Godot MCP Tool <code>${tool}</code>...`);

      try {
        const res = await fetch('/api/gamedev/godot/exec', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool_name: tool, params })
        });
        const data = await res.json();
        bubble.innerHTML = formatMarkdown(`**Godot MCP Tool Result for \`${tool}\`:**\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``);
      } catch (err) {
        bubble.innerHTML = `<span style="color:var(--accent-rose)">Godot MCP Error: ${err.message}</span>`;
      }
    });
  }

  // Asset Bridge Deploy
  if (bridgeDeployBtn) {
    bridgeDeployBtn.addEventListener('click', async () => {
      if (!currentExtractedAsset || !currentExtractedAsset.extracted_filename) {
        alert('No 3D asset currently loaded or decoded. Extract an M3DS image in 3D Viewer first.');
        return;
      }
      const engine = bridgeEngineSelect.value;
      bridgeStatusNote.textContent = `Deploying ${currentExtractedAsset.extracted_filename} to ${engine}...`;

      try {
        const res = await fetch('/api/gamedev/deploy-asset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mesh_path: currentExtractedAsset.extracted_filename,
            target_engine: engine
          })
        });
        const data = await res.json();
        if (data.status === 'success') {
          bridgeStatusNote.innerHTML = `<span style="color:var(--accent-emerald)">✓ Deployed to ${data.destination}</span>`;
          appendGameDevMessage('assistant', `📦 **Asset Deployed!**\nCopied \`${currentExtractedAsset.extracted_filename}\` to **${engine.toUpperCase()}** at:\n\`${data.destination}\``);
        } else {
          bridgeStatusNote.innerHTML = `<span style="color:var(--accent-rose)">❌ ${data.message}</span>`;
        }
      } catch (err) {
        bridgeStatusNote.textContent = 'Deploy failed: ' + err.message;
      }
    });
  }

  // Game Dev Agent Chat
  async function sendGameDevChat(text) {
    const msg = text || gdInput.value.trim();
    if (!msg) return;

    appendGameDevMessage('user', msg);
    if (!text) gdInput.value = '';

    const typingMsg = appendGameDevMessage('assistant', 'Game Dev Agent thinking (Gemini Flash)...');

    try {
      const res = await fetch('/api/gamedev/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      let fullText = '';
      if (data.responses) {
        data.responses.forEach(chunk => {
          if (chunk.text) fullText += chunk.text;
          if (chunk.message) fullText += `\n*${chunk.message}*\n`;
        });
      }
      typingMsg.innerHTML = formatMarkdown(fullText || 'No response returned.');
    } catch (err) {
      typingMsg.innerHTML = `<span style="color:var(--accent-rose)">Game Dev Agent error: ${err.message}</span>`;
    }
  }

  if (gdSendBtn) gdSendBtn.addEventListener('click', () => sendGameDevChat());
  if (gdInput) {
    gdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendGameDevChat();
      }
    });
  }

  // Suggestion chips
  document.querySelectorAll('.chip-suggestion-gd').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      sendGameDevChat(prompt);
    });
  });

  // Initial probe
  probeEngines();
}

function appendGameDevMessage(role, text) {
  const messages = document.getElementById('gamedev-messages');
  if (!messages) return null;
  const msgEl = document.createElement('div');
  msgEl.className = `message msg-${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = formatMarkdown(text);
  msgEl.appendChild(bubble);
  messages.appendChild(msgEl);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}
