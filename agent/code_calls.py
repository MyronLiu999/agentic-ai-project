"""Code that calls the tools (Milestone 2, Part 1 task 4; owner: myron, M3).

    run_program(run_key, code, registry) -> dict
        runs the model's short program in a process of its own; returns {"result", "calls"} when it finishes,
        or {"error", "calls"} (with "line" where the program's own line is known) when it raises, runs too
        long or reaches for what it may not. The run_program tool turns an error into a failed call whose
        repair text is that message, so the model can fix the program.

The program can reach nothing but our tools (Lecture 3, slides 26-27):
  - it runs as `python -I` (no user site, no environment variables, no current folder on the path), with an
    empty environment, in a scratch folder of its own under the sandbox's state folder, removed afterwards;
  - an audit hook, installed before the program's first line and impossible to remove, refuses every socket,
    every subprocess and native-library load, and every file opened outside the scratch folder (the Python
    installation itself stays readable, so `import json` works);
  - its only way out is call(name, args), which goes back over its stdin/stdout to this process, where the
    registry handles it as a code caller: validation, the policy hook, a key on every write, the call record;
  - only the value it assigns to `result` comes back: none of the results along the way, and nothing it
    prints, enters the model's context.

Switches: code_calls.<use_case>, off | on (agent/tools.py offers run_program where one is on).
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid

TIMEOUT_S = 30.0          # wall clock for one program
MAX_CALLS = 200           # tool calls one program may make

_BOOT = r'''
import builtins, io, json, os, sys, traceback

_in, _out = sys.stdin, sys.stdout
sys.stdout = io.StringIO()          # what the program prints never reaches the protocol, or the model
SCRATCH = os.path.realpath(os.getcwd())
READABLE = sorted({os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix,
                                                 sys.base_exec_prefix) if p})

def _inside(path, roots):
    path = os.path.normcase(path)
    return any(path == os.path.normcase(r) or path.startswith(os.path.normcase(r) + os.sep) for r in roots)

_NETWORK = ("socket.", "urllib.", "http.", "ftplib.", "smtplib.", "telnetlib.", "webbrowser.")
_DENIED_PREFIXES = _NETWORK + ("subprocess.", "os.system", "os.exec", "os.spawn", "os.posix_spawn",
                               "os.startfile", "os.fork", "os.kill", "ctypes.", "winreg.", "_winapi.", "msvcrt.")
_PATH_EVENTS = {"os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chdir", "os.symlink",
                "os.link", "os.truncate", "os.listdir", "os.scandir", "shutil.rmtree", "shutil.copyfile",
                "shutil.move", "glob.glob"}

def _audit(event, args):
    if event.startswith(_DENIED_PREFIXES):
        what = "network access" if event.startswith(_NETWORK) else event
        raise PermissionError(f"{what} is not allowed in a program: it can reach only call(name, args)")
    if event == "open":
        path, mode = args[0], (args[1] if len(args) > 1 else "r")
        if isinstance(path, int) or path is None:
            return
        real = os.path.realpath(os.fsdecode(path))
        writing = mode is not None and any(c in str(mode) for c in "wax+")
        if _inside(real, [SCRATCH]) or (not writing and _inside(real, READABLE)):
            return
        raise PermissionError(f"files outside the program's scratch folder are not allowed: {path}")
    if event in _PATH_EVENTS:
        for value in args:
            if isinstance(value, (str, bytes, os.PathLike)):
                real = os.path.realpath(os.fsdecode(value))
                if not _inside(real, [SCRATCH]):
                    raise PermissionError(f"files outside the program's scratch folder are not allowed: {value}")

def _send(message):
    _out.write(json.dumps(message) + "\n")
    _out.flush()

def call(name, args=None):
    """Call one of this request's tools through the registry; returns its envelope {ok, output, is_error, error}."""
    _send({"call": str(name), "args": args if args is not None else {}})
    line = _in.readline()
    if not line:
        raise RuntimeError("the registry closed the program's channel")
    return json.loads(line)

code = json.loads(_in.readline())["code"]
sys.addaudithook(_audit)
namespace = {"__name__": "__program__", "call": call, "result": None}
try:
    exec(compile(code, "<program>", "exec"), namespace)
    value = namespace.get("result")
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        _send({"error": "result must be JSON: numbers, strings, lists, objects, true/false or null"})
    else:
        _send({"final": value})
except BaseException as exc:
    line = None
    for frame in traceback.extract_tb(exc.__traceback__):
        if frame.filename == "<program>":
            line = frame.lineno
    if isinstance(exc, SyntaxError) and exc.filename == "<program>":
        line = exc.lineno
    _send({"error": f"{type(exc).__name__}: {exc}"[:500], "line": line})
'''


def _trace(run_key, calls: int, error: str | None) -> None:
    try:
        from agent import events
        from harness import runtime
        runtime.trace().event(events.CODE_CALL, run_key=run_key, calls=calls, error=error)
    except Exception:
        pass


def _disclosed(name: str, args: dict) -> dict:
    """A send a program makes passes disclosure.with_disclosure before the registry, like every other send
    (Part 2, task 8): code adds the line, never the program's author."""
    from agent import disclosure
    field = disclosure.SENDS.get(name)
    if field and isinstance(args.get(field), str):
        return {**args, field: disclosure.with_disclosure(args[field])}
    return args


def _scratch_root():
    from harness.paths import state_dir
    return state_dir() / "scratch"


def run_program(run_key, code, registry) -> dict:
    """Run one program; every call it makes is `registry.call(name, args, "code")`."""
    from agent.registry import CODE

    folder = _scratch_root() / f"program-{uuid.uuid4().hex[:12]}"
    folder.mkdir(parents=True, exist_ok=True)
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]     # Windows needs it to start any process
    proc = subprocess.Popen([sys.executable, "-I", "-c", _BOOT], cwd=str(folder), env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8")
    lines: queue.Queue = queue.Queue()

    def read():
        for raw in iter(proc.stdout.readline, ""):
            lines.put(raw)
        lines.put(None)

    threading.Thread(target=read, daemon=True, name="program-reader").start()
    calls, outcome = 0, None
    try:
        proc.stdin.write(json.dumps({"code": str(code)}) + "\n")
        proc.stdin.flush()
        deadline = time.monotonic() + TIMEOUT_S
        while outcome is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                outcome = {"error": f"the program ran past {TIMEOUT_S:.0f} s and was stopped"}
                break
            try:
                raw = lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if raw is None:
                outcome = {"error": "the program ended without a result"}
                break
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if "call" in message:
                calls += 1
                if calls > MAX_CALLS:
                    reply = {"ok": False, "output": None, "is_error": True,
                             "error": {"type": "call_limit", "kind": "protocol",
                                       "message": f"a program may make at most {MAX_CALLS} calls"}}
                else:
                    name = str(message["call"])
                    args = _disclosed(name, message.get("args") if isinstance(message.get("args"), dict) else {})
                    reply = registry.call(name, args, CODE)
                proc.stdin.write(json.dumps(reply, default=str) + "\n")
                proc.stdin.flush()
            elif "final" in message:
                outcome = {"result": message["final"]}
            elif "error" in message:
                outcome = {"error": str(message["error"])}
                if message.get("line"):
                    outcome["line"] = int(message["line"])
    except (BrokenPipeError, OSError) as exc:
        outcome = {"error": f"the program's channel broke: {type(exc).__name__}"}
    finally:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except Exception:
                pass
        shutil.rmtree(folder, ignore_errors=True)
    outcome["calls"] = min(calls, MAX_CALLS)
    _trace(run_key, outcome["calls"], outcome.get("error"))
    return outcome
