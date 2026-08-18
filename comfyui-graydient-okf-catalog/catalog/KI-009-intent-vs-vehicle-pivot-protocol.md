---
id: "KI-009"
title: "The Intent-vs-Vehicle Pivot Protocol & Planning Directives"
version: "1.0.0"
type: "planning_protocol"
tags:
  - planning
  - agent-rules
  - pivot-protocol
  - intent-first
  - human-ai-pairing
sources:
  - "CLAUDE.md"
  - "okf_knowledge_catalog.md"
---

# KI-009: The Intent-vs-Vehicle Pivot Protocol & Planning Directives

When humans and AI agents collaborate on complex ComfyUI workflows, humans frequently specify a **proposed technical vehicle** (e.g. *"Let's build a Rust crate for speech parsing"*) that contains an unintended platform violation.

This protocol establishes how agents and engineers MUST evaluate directives during the planning phase.

---

## 1. The Core Principle: Intent vs. Vehicle

* **Intent (The Goal)**: What functional capability the user wants to achieve (e.g., synchronize frame count to audio duration, generate 3D STL from prompt, upscale without latency).
* **Vehicle (The Method)**: The specific library, language, node structure, or workflow pattern suggested to achieve that goal.

> [!CRITICAL]
> **Agents are strictly forbidden from blind compliance.** If the proposed vehicle violates a platform constraint or Graveyard rule (`KI-007`), the agent must NOT build it, nor should it simply stop with an error. The agent must trigger the **Pivot Protocol**.

---

## 2. The 3-Step Pivot Protocol

Whenever a proposed method conflicts with platform constraints:

### Step 1: Acknowledge & Isolate the Intent
Explicitly state the functional goal to confirm full alignment with the user.

### Step 2: Explain the Specific Platform Failure Mode
State the exact physical or runtime bottleneck (e.g. missing `cargo` on ephemeral runners, live HF download timeout, slot boolean type mismatch).

### Step 3: Offer 1–2 Pre-Validated Compliant Routes
Provide concrete, tested alternative architectures that deliver the exact same outcome without quota risk.

---

## 3. Example Pivot Interactions

### Scenario A: Compiling Source Code
* **User Directive**: *"Let's compile this fast C++/Rust speech tokeniser node for Graydient."*
* **Agent Response**:
  > **Intent**: Fast speech tokenisation for audio conditioning.
  > **Platform Constraint**: Graydient runners lack C++/Rust build toolchains; source distributions fail during `pip install`.
  > **Pivot Route 1 (Instant)**: Use pre-built Python bindings from `torchaudio` / `scipy` already in the container.
  > **Pivot Route 2 (Modular Node)**: Use our pure-Python fork `UnlimitedEditing/<repo>` with standard wheel dependencies.

### Scenario B: Dynamic Duration Extraction
* **User Directive**: *"Have the workflow query the video duration via an un-staged HTTP node."*
* **Agent Response**:
  > **Intent**: Match generated video frame count to reference voice clip length.
  > **Platform Constraint**: Naive HTTP nodes crash when Graydient passes local staged filenames instead of remote URLs.
  > **Pivot Route**: Use `Load Audio Any` -> `Audio Duration` -> `ComfyMathExpression` block (`graydient_builder.blocks.audio_duration_sync`).
