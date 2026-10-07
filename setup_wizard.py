#!/usr/bin/env python3
"""Setup wizard for the Graydient workflow tooling stack.

Checks (and, with your OK, installs) everything the stack needs:
  1. Python >= 3.9 and git
  2. Node >= 22 + npm, and a Chromium-based browser (Edge or Chrome) for the web-UI driver
  3. the bundled `graydient` CLI (cli/): npm ci + build
  4. Hugging Face CLI (`hf`) and a login (concept weights must be hosted on a public HF repo)
  5. a Graydient API key (for renders) and an archive/concept session (magic link from the Telegram bot)
  6. a self-test: the workflow linter and the CLI both run

It never asks you to type a secret into itself: `hf auth login` uses Hugging Face's own prompt, and the
Graydient key / magic link steps only print the command for you to run.

Usage:
  python setup_wizard.py            interactive (asks before each install)
  python setup_wizard.py --check    report only, change nothing
  python setup_wizard.py --yes      install/build without asking
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "cli"
IS_WIN = platform.system() == "Windows"
OK, WARN, FAIL = "[ ok ]", "[warn]", "[FAIL]"

results: list[tuple[str, str, str]] = []  # (status, step, detail)


def record(status: str, step: str, detail: str = "") -> None:
    results.append((status, step, detail))
    print(f"{status} {step}" + (f" - {detail}" if detail else ""))


def run(cmd: list[str], cwd: Path | None = None, capture: bool = True, timeout: int = 900) -> tuple[int, str]:
    exe = shutil.which(cmd[0]) or cmd[0]
    try:
        p = subprocess.run([exe, *cmd[1:]], cwd=cwd, capture_output=capture, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def ask(question: str, args: argparse.Namespace) -> bool:
    if args.check:
        return False
    if args.yes:
        return True
    return input(f"      {question} [y/N] ").strip().lower().startswith("y")


def find_browser() -> str | None:
    env = os.environ.get("GRAYDIENT_BROWSER_CHANNEL")
    candidates: list[str] = []
    if IS_WIN:
        for base in filter(None, [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]):
            candidates += [
                rf"{base}\Microsoft\Edge\Application\msedge.exe",
                rf"{base}\Google\Chrome\Application\chrome.exe",
            ]
    elif platform.system() == "Darwin":
        candidates = ["/Applications/Google Chrome.app", "/Applications/Microsoft Edge.app"]
    else:
        candidates = [p for n in ("google-chrome", "google-chrome-stable", "microsoft-edge", "chromium") if (p := shutil.which(n))]
    hit = next((c for c in candidates if Path(c).exists()), None)
    return hit or (f"channel '{env}' (GRAYDIENT_BROWSER_CHANNEL)" if env else None)


def step_python_git() -> None:
    v = sys.version_info
    if v >= (3, 9):
        record(OK, "Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        record(FAIL, "Python", f"{v.major}.{v.minor} found, need >= 3.9: https://www.python.org/downloads/")
    if shutil.which("git"):
        record(OK, "git", run(["git", "--version"])[1])
    else:
        record(WARN, "git", "not found (only needed to clone/update the repos): https://git-scm.com/downloads")


def step_node() -> bool:
    if not shutil.which("node"):
        record(FAIL, "Node.js", "not found. Install Node >= 22 from https://nodejs.org/ (the CLI needs it)")
        return False
    out = run(["node", "--version"])[1]
    m = re.match(r"v(\d+)", out)
    major = int(m.group(1)) if m else 0
    if major < 22:
        record(FAIL, "Node.js", f"{out} found, need >= 22: https://nodejs.org/")
        return False
    record(OK, "Node.js", out)
    if shutil.which("npm"):
        record(OK, "npm", run(["npm", "--version"])[1])
        return True
    record(FAIL, "npm", "not found (ships with Node)")
    return False


def step_browser() -> None:
    b = find_browser()
    if b:
        record(OK, "Browser (Edge/Chrome)", b)
    else:
        record(FAIL, "Browser (Edge/Chrome)", "none found. The archive/concept driver needs Microsoft Edge or Google Chrome installed")


def step_cli(args: argparse.Namespace, node_ok: bool) -> bool:
    if not CLI.exists():
        record(FAIL, "graydient CLI", f"{CLI} missing; re-clone the repo")
        return False
    built = (CLI / "dist" / "index.js").exists() and (CLI / "node_modules").exists()
    if built:
        record(OK, "graydient CLI built", str(CLI / "dist" / "index.js"))
        return True
    if not node_ok:
        record(FAIL, "graydient CLI build", "needs Node >= 22 first")
        return False
    if ask("Run `npm ci && npm run build` in cli/ now?", args):
        print("      installing (this downloads ~40 MB)...")
        rc, out = run(["npm", "ci"], cwd=CLI)
        if rc == 0:
            rc, out = run(["npm", "run", "build"], cwd=CLI)
        if rc == 0:
            record(OK, "graydient CLI built", "cli/dist/index.js")
            return True
        record(FAIL, "graydient CLI build", out[-400:])
        return False
    record(WARN, "graydient CLI not built", "run: cd cli && npm ci && npm run build")
    return False


def step_hf(args: argparse.Namespace) -> None:
    if not shutil.which("hf"):
        record(WARN, "Hugging Face CLI (hf)", "not installed (needed to host concept weights)")
        if ask("Install it with `pip install -U huggingface_hub`?", args):
            rc, out = run([sys.executable, "-m", "pip", "install", "-U", "huggingface_hub"])
            if rc != 0 or not shutil.which("hf"):
                record(FAIL, "Hugging Face CLI (hf)", (out[-300:] or "installed but `hf` is not on PATH; reopen your terminal"))
                return
            record(OK, "Hugging Face CLI (hf)", "installed")
        else:
            print("      to install: pip install -U huggingface_hub")
            return
    else:
        record(OK, "Hugging Face CLI (hf)", run(["hf", "version"])[1].splitlines()[0] if run(["hf", "version"])[0] == 0 else "found")
    rc, out = run(["hf", "auth", "whoami"])
    if rc == 0 and out:
        record(OK, "Hugging Face login", out.splitlines()[-1])
        return
    record(WARN, "Hugging Face login", "not logged in")
    if args.check:
        print("      to log in: hf auth login   (create a token with WRITE access at https://huggingface.co/settings/tokens)")
    elif ask("Run `hf auth login` now? (you paste the token into Hugging Face's own prompt)", args) and not args.yes:
        subprocess.run([shutil.which("hf") or "hf", "auth", "login"])
        rc, out = run(["hf", "auth", "whoami"])
        record(OK if rc == 0 else WARN, "Hugging Face login", out.splitlines()[-1] if rc == 0 else "still not logged in")
    else:
        print("      to log in later: hf auth login   (token with WRITE access: https://huggingface.co/settings/tokens)")


def step_graydient(cli_ok: bool) -> None:
    if not cli_ok:
        record(WARN, "Graydient API key / sessions", "skipped (CLI not built)")
        return
    node_cli = ["node", str(CLI / "dist" / "index.js")]
    if os.environ.get("GRAYDIENT_API_KEY"):
        record(OK, "Graydient API key", "from GRAYDIENT_API_KEY")
    else:
        rc, out = run([*node_cli, "auth", "status"])
        if rc == 0 and "not" not in out.lower().split("\n")[0]:
            record(OK, "Graydient API key", "stored and live-checked")
        else:
            record(WARN, "Graydient API key", "missing. Get one at https://app.graydient.ai/dashboard/token/ then run:")
            print(f"      node {CLI / 'dist' / 'index.js'} auth login --key <your-key>")
    rc, out = run([*node_cli, "archive", "status"], timeout=120)
    if rc == 0 and "Logged in" in out:
        record(OK, "Archive/concept web session", out.splitlines()[0])
    else:
        record(WARN, "Archive/concept web session", "not logged in (sessions expire overnight). Needed for workflow deploys and concept installs:")
        print("      1. In Telegram, send /archive (workflows) or /concept /edit (concepts) to the Graydient bot")
        print("      2. Run (keep the link private, it is a login):")
        print(f'         node {CLI / "dist" / "index.js"} archive login "<magic link>"')


def step_selftest(cli_ok: bool) -> None:
    rc, out = run([sys.executable, str(ROOT / "wf.py"), "--help"])
    record(OK if rc == 0 else FAIL, "Workflow linter CLI (wf.py)", "runs" if rc == 0 else out[-200:])
    if cli_ok:
        rc, out = run(["node", str(CLI / "dist" / "index.js"), "archive", "concept", "--help"])
        record(OK if rc == 0 else FAIL, "graydient CLI (archive concept)", "runs" if rc == 0 else out[-200:])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--yes", "-y", action="store_true", help="install/build without asking")
    args = ap.parse_args()

    print(f"Graydient tooling setup ({platform.system()}, {ROOT})\n")
    step_python_git()
    node_ok = step_node()
    step_browser()
    cli_ok = step_cli(args, node_ok)
    step_hf(args)
    step_graydient(cli_ok)
    step_selftest(cli_ok)

    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    print(f"\nDone: {sum(r[0] == OK for r in results)} ok, {len(warns)} to-do, {len(fails)} blocking.")
    for _, step, detail in fails + warns:
        print(f"  - {step}: {detail}")
    if not fails and not warns:
        print("Everything is ready. Try:  python wf.py search audioldm   |   node cli/dist/index.js archive status")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
