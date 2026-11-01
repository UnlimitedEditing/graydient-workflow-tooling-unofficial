#!/usr/bin/env bash
#
# Publish the vendored ComfyUI-MediaMetadata node pack to its own GitHub repo.
#
# The pack lives in this repository at custom_nodes/ComfyUI-MediaMetadata/ so
# that the workflow which depends on it (templates/gen_media_metadata_report.py)
# and the node it needs are versioned together. Graydient installs custom nodes
# from a GitHub URL, so the pack has to exist as its OWN repository before the
# workflow can run.
#
# Usage:
#   ./tools/publish_media_metadata_pack.sh [owner/repo]
#
# Requires `gh` authenticated with permission to create repositories.

set -euo pipefail

REPO_SLUG="${1:-UnlimitedEditing/UnlimitedEditing-ComfyUI-MediaMetadata}"
SRC="$(cd "$(dirname "$0")/../custom_nodes/ComfyUI-MediaMetadata" && pwd)"

if [ ! -f "$SRC/media_metadata.py" ]; then
    echo "[ERROR] node pack not found at $SRC" >&2
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cp -r "$SRC/." "$WORK/"
rm -rf "$WORK/.git" "$WORK/tests/fixtures" "$WORK/tests/bin"
cd "$WORK"

git init -b main -q
git add -A
git commit -q -m "Media metadata probe: report a media file's own metadata as an image

Reads the media Graydient attached to a job (init_video / init_image /
init_audio, in both the _url and the _filename flavour), resolves it to a real
file, and extracts file-level metadata with ffprobe plus PIL/EXIF for stills.
Returns the report as text, as JSON, and rendered as a metadata card image."

if gh repo view "$REPO_SLUG" >/dev/null 2>&1; then
    echo "==> $REPO_SLUG exists already; pushing to it"
    git remote add origin "https://github.com/$REPO_SLUG.git"
    git push -u origin main
else
    echo "==> creating $REPO_SLUG"
    gh repo create "$REPO_SLUG" --public --source=. --remote=origin --push \
        --description "ComfyUI node: probe the media Graydient attached (init_video/init_image/init_audio) and render its full metadata (resolution, duration, fps, total frames, bit rate, codec, creation time, EXIF) as an image"
fi

echo
echo "==> done. The workflow's requirements.github now resolves to:"
echo "    https://github.com/$REPO_SLUG"
