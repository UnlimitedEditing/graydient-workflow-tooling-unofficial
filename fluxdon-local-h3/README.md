# Fluxdon Local H3 — ComfyUI custom nodes

Six **local H3 conditioning/preparation nodes** for Recast, Extend, Reframe,
Insert, Lip Sync, and Camera Control. These are not the hosted MiniMax partner
API nodes; they use ComfyUI's local MiniMax H3 implementation and local weights.
Each produces conditioning and a latent to use with the normal H3 sampler,
VAE decoders and output nodes. They are intended for the companion Graydient
backups; they do not produce a finished video on their own.

## Upload / install

Upload the **contents of this folder** to the root of
`https://github.com/UnlimitedEditing/fluxdon-local-h3` (including `__init__.py`
and `nodes.py`). The repository URL is already listed as a requirement in each
backup. The repo must contain these files and be accessible to the Graydient
installer before restoring/running the workflows. No files have been uploaded
for you.

For local ComfyUI, place this directory in `ComfyUI/custom_nodes/` and restart
ComfyUI. You need a recent ComfyUI version containing
`comfy_extras/nodes_minimax_h3.py`. Extend and Insert additionally need
`seitanism/ComfyUI-H3-Motion-Context-MultiRef`; their output also requires the
MCR trim/assemble nodes in the companion workflows. The backups retain all
seven originally requested node-pack requirements, including MCR, Easy-Use,
VideoHelperSuite and Optional Asset Loader. No additional pip requirements
are declared by this pack.

## Behavior and limitations

- **Recast:** H3 reference-to-video conditioning from identity image(s) and
  source video (and optional source audio). Identity/motion preservation is
  model-guided, not guaranteed.
- **Extend / Insert:** create H3 conditioning and call MCR's masked-context
  preparation. Additional MCR nodes assemble the decoded result with the
  source. These are not standalone complete video-processing nodes.
- **Reframe:** anchors padded video as an H3 guide. It is not masked outpainting
  and cannot guarantee unchanged centre pixels.
- **Lip Sync:** anchors speech as an H3 guide to animate a portrait. It is not
  a phoneme-based lip-sync model; precision is not guaranteed.
- **Camera Control:** appends descriptive numeric camera motion to the H3
  prompt. Angles and distance are not geometric camera guarantees.

All six use 24 fps H3 conventions. The workflows stage weights separately; this
pack contains no model files. Code/graph tests are CPU-only mock and static
checks. **No real ComfyUI or Graydient render has been performed**, so install
and run a short smoke test before production use.
