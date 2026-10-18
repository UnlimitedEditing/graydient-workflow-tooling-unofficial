# ComfyUI & Graydient SaaS Workflow Engineering OKF Catalog

[![OKF Specification Standard](https://img.shields.io/badge/OKF-v1.0.0-blue.svg)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An Open Knowledge Format (OKF) specification and knowledge catalog for agentic AI coders and human developers building, decoupling, and deploying **ComfyUI workflows** on the **Graydient SaaS platform** via single-file Backup/Restore JSON artifacts (`GraydientWorkflow-*.json`).

---

## 📚 Knowledge Catalog Index

| ID | Title | Summary |
|---|---|---|
| **[KI-001](catalog/KI-001-architecture-overview.md)** | Dual-Workflow JSON Architecture | Standard UI graph vs API prompt format requirements and backup/restore lifecycle. |
| **[KI-002](catalog/KI-002-concept-mapping-staging.md)** | Model Staging & Offline Loading Rules | Pre-downloading model weights via `concept_mapping` and mandatory `os.path.isfile()` checks in custom nodes to prevent container timeouts. |
| **[KI-003](catalog/KI-003-field-mapping-slots.md)** | Field Mapping & Parameter Indexing | Connecting Graydient UI slots to node parameters; primitive widget indexing rules (`widgets_values` vs socket links). |
| **[KI-004](catalog/KI-004-decoupled-node-patterns.md)** | Decoupled Node Patterns | Monolithic node refactoring pattern: `ModelLoader` (memory cache) + `Sampler` (inference). |
| **[KI-005](catalog/KI-005-saas-execution-constraints.md)** | SaaS Constraints, VRAM & Timeout Budgets | ~180s ComfyUI run-time budget (startup/downloads not counted), VRAM limits (24GB RTX 4090 / 32GB RTX 5090), and DynamicVRAM (`comfy-aimdo`). |
| **[KI-006](catalog/KI-006-audio-generation-standards.md)** | Audio Generation Standards | AudioLDM, Higgs, and MisoTTS audio pipeline standards with scipy 48kHz polyphase resampling. |

---

## 🚀 Repository Structure

```
.
├── okf.yaml                                 # OKF Catalog Root Specification
├── README.md                                # Repository documentation & index
├── LICENSE                                  # MIT License
├── catalog/                                 # OKF Knowledge Items (KIs)
│   ├── KI-001-architecture-overview.md
│   ├── KI-002-concept-mapping-staging.md
│   ├── KI-003-field-mapping-slots.md
│   ├── KI-004-decoupled-node-patterns.md
│   ├── KI-005-saas-execution-constraints.md
│   └── KI-006-audio-generation-standards.md
└── templates/                               # Generator script templates & reference JSONs
    ├── gen_template.py
    ├── gen_audioldm_t2s.py
    └── GraydientWorkflow-audioldm-t2s-v1.json
```

---

## 💡 Quick Start for AI Agents & Developers

When authoring or modifying a Graydient ComfyUI workflow:
1. **Read KI-001** to understand the `workflow` (UI) and `workflow_2` (API) dual-JSON contract.
2. **Read KI-002** before configuring model downloads. Ensure your custom node Python code checks `if os.path.isfile(...)` before making any network calls.
3. **Read KI-003** to calculate `node_input_index` accurately (count primitive widgets in `widgets_values` only, skipping connected socket links).
4. **Read KI-004** to refactor monolithic custom nodes into decoupled `ModelLoader` and `Sampler` nodes.
5. Use `templates/gen_template.py` as your baseline script to output `GraydientWorkflow-<name>-v1.json`.

---

## 📄 License
This catalog is licensed under the [MIT License](LICENSE).
