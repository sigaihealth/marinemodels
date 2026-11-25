"""Control a private Qwen3-32B llama.cpp process in the user's Jupyter workspace."""
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent
RUNTIME = ROOT / "runtime"
MODEL = ROOT / "Qwen3-32B-Q4_K_M.gguf"
KEY = ROOT / ".api-key"
STATE = ROOT / ".server-state.json"
LOG = ROOT / "server.log"
HOST, PORT = "127.0.0.1", 18732


def identity(pid):
    """Identify this session leader across PID reuse and workspace restarts."""
    try:
        if os.getsid(pid) != pid or os.getpgid(pid) != pid:
            return None
        proc = Path("/proc") / str(pid)
        if proc.exists():
            args = (proc / "cmdline").read_bytes().split(b"\x00")
            if [os.fsencode(SCRIPT), b"_serve"] != args[1:3]:
                return None
            fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            return [socket.gethostname(), boot, fields[19]]
        # POSIX fallback also permits lifecycle tests on local macOS.
        signature = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "lstart=,command="], text=True,
            env={**os.environ, "LC_ALL": "C"}, stderr=subprocess.DEVNULL
        ).strip()
        if signature.endswith(f"{SCRIPT} _serve"):
            return [socket.gethostname(), signature]
    except (OSError, subprocess.CalledProcessError):
        pass
    return None


def running_pid():
    if STATE.exists():
        record = json.loads(STATE.read_text())
        pid = record["pid"]
        if pid > 1 and record["identity"] and identity(pid) == record["identity"]:
            return pid
    return None


def listen_address_available():
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, PORT))
        except OSError:
            return False
    return True


def serve():
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(RUNTIME) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    args = [str(RUNTIME / "llama-server"), "-m", str(MODEL), "--alias", "Qwen3-32B",
            "--host", HOST, "--port", str(PORT), "--api-key-file", str(KEY),
            "--device", "CUDA0", "-ngl", "99", "-c", "8192", "-np", "1",
            "--jinja", "--chat-template-kwargs", '{"enable_thinking":false}']
    return subprocess.run(args, cwd=ROOT, env=env).returncode


def start():
    if running_pid():
        print("Qwen3-32B is already running or loading.")
        return
    if not listen_address_available():
        raise RuntimeError(f"{HOST}:{PORT} is occupied by another process.")
    if not (RUNTIME / "llama-server").is_file() or not MODEL.is_file():
        raise RuntimeError("The CUDA runtime or model is missing from this directory.")
    if not KEY.exists():
        with KEY.open("x") as stream:
            stream.write(secrets.token_hex(32) + "\n")
    if KEY.stat().st_mode & 0o077 or not KEY.read_text().strip():
        raise RuntimeError("The local key must be nonempty and accessible only to its owner.")
    with LOG.open("ab", buffering=0) as log:
        print(time.strftime("\nStarting Qwen3-32B at %Y-%m-%d %H:%M:%S"), file=sys.stderr)
        job = subprocess.Popen([sys.executable, str(SCRIPT), "_serve"], cwd=ROOT,
                               start_new_session=True, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT)
    try:
        mark = identity(job.pid)
        if not mark:
            raise RuntimeError(f"The launcher did not initialize. See {LOG.name}.")
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pid": job.pid, "identity": mark}))
        tmp.replace(STATE)
    except BaseException:
        if job.poll() is None:
            os.killpg(job.pid, signal.SIGTERM)
        raise
    for _ in range(20):
        if job.poll() is not None:
            raise RuntimeError(f"The GPU server exited ({job.returncode}). See {LOG.name}.")
        if not listen_address_available():
            break
        time.sleep(.1)
    print(f"Started Qwen3-32B (PID {job.pid}). The notebook will check model readiness.")


def stop():
    pid = running_pid()
    if not pid:
        print("No managed Qwen3-32B server is running.")
        return
    os.killpg(pid, signal.SIGTERM)
    for _ in range(100):
        if not running_pid():
            break
        time.sleep(.1)
    if running_pid() == pid:
        os.killpg(pid, signal.SIGKILL)
    STATE.unlink(missing_ok=True)
    print("Stopped the managed Qwen3-32B server.")


def main():
    os.umask(0o077)
    if sys.argv[1:] == ["_serve"]:
        return serve()
    if sys.argv[1:] not in (["start"], ["stop"]):
        raise RuntimeError("Use start.sh or stop.sh.")
    with (ROOT / ".service.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (start if sys.argv[1] == "start" else stop)()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
