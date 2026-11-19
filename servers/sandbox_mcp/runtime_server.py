import os
import resource
import signal
import subprocess
import tempfile
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class CodeRequest(BaseModel):
    code: str
    language: str

def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    os.setsid()

def _limits_vm():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    resource.setrlimit(resource.RLIMIT_DATA, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    os.setsid()

def _limits_compiler():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    os.setsid()

def _truncate(text: str, limit: int = 20000) -> str:
    if text and len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text or ""

def check_isolation():
    # 1. Try unshare
    try:
        res = subprocess.run(["unshare", "-rn", "true"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, "unshare", None
        unshare_err = res.stderr.strip() or f"exit code {res.returncode}"
    except Exception as e:
        unshare_err = str(e)

    # 2. Try docker
    try:
        res = subprocess.run(["docker", "image", "inspect", "marketplace-sandbox:1"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, "docker", None
        docker_err = res.stderr.strip() or f"exit code {res.returncode}"
    except Exception as e:
        docker_err = str(e)

    return False, "none", f"unshare failed ({unshare_err}); docker image inspect marketplace-sandbox:1 failed ({docker_err})"

ISOLATION_OK, BACKEND, ISOLATION_ERROR = check_isolation()

@app.get("/health")
def health():
    return {"isolation": ISOLATION_OK, "backend": BACKEND, "error": ISOLATION_ERROR}

@app.post("/run")
async def run_code(req: CodeRequest):
    if not ISOLATION_OK:
        raise HTTPException(
            status_code=503,
            detail=f"sandbox isolation unavailable: {ISOLATION_ERROR}"
        )
    code = req.code
    language = req.language

    if language not in ("python", "javascript", "c", "cpp", "java"):
        raise HTTPException(status_code=400, detail="Unsupported language")

    if BACKEND == "docker":
        if language == "python":
            file_name = "temp.py"
            cmd_inner = "python3 temp.py"
            limit = 5
        elif language == "javascript":
            file_name = "temp.js"
            cmd_inner = "node temp.js"
            limit = 5
        elif language == "c":
            file_name = "temp.c"
            cmd_inner = "gcc temp.c -o prog && ./prog"
            limit = 20
        elif language == "cpp":
            file_name = "temp.cpp"
            cmd_inner = "g++ temp.cpp -o prog && ./prog"
            limit = 20
        elif language == "java":
            file_name = "Main.java"
            cmd_inner = "javac Main.java && java -Xmx128m Main"
            limit = 20

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tempdir:
            os.chmod(tempdir, 0o777)
            file_path = os.path.join(tempdir, file_name)
            with open(file_path, "w") as f:
                f.write(code)

            container_name = f"sandbox-{uuid.uuid4().hex}"
            docker_cmd = [
                "docker", "run",
                "--name", container_name,
                "--rm",
                "--network", "none",
                "--memory", "256m",
                "--memory-swap", "256m",
                "--cpus", "1",
                "--pids-limit", "64",
                "--read-only",
                "--tmpfs", "/tmp:rw,size=64m,exec",
                "--security-opt", "no-new-privileges",
                "--cap-drop", "ALL",
                "--user", "10001:10001",
                "-v", f"{tempdir}:/work:rw",
                "-w", "/work",
                "marketplace-sandbox:1",
                "timeout", str(limit),
                "sh", "-c", cmd_inner,
            ]
            subprocess_timeout = limit + 10
            try:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=subprocess_timeout,
                )
                stderr = result.stderr or ""
                if result.returncode == 124:
                    stderr = "Execution timed out."
                elif result.returncode in (-signal.SIGXCPU, -signal.SIGKILL, -9, -24) and not stderr:
                    stderr = "Execution timed out."
                return {"stdout": _truncate(result.stdout), "stderr": _truncate(stderr)}
            except subprocess.TimeoutExpired:
                try:
                    subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=5)
                except Exception:
                    pass
                return {"stdout": "", "stderr": "Execution timed out."}
            except Exception as e:
                return {"stdout": "", "stderr": _truncate(str(e))}

    elif BACKEND == "unshare":
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tempdir:
            sandbox_env = {"PATH": "/usr/bin:/bin", "HOME": tempdir, "LANG": "C.UTF-8"}
            try:
                if language == "python":
                    file_path = os.path.join(tempdir, "temp.py")
                    with open(file_path, "w") as f:
                        f.write(code)
                    result = subprocess.run(
                        ["unshare", "-rn", "python3", file_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=5,
                        preexec_fn=_limits,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                elif language == "javascript":
                    file_path = os.path.join(tempdir, "temp.js")
                    with open(file_path, "w") as f:
                        f.write(code)
                    result = subprocess.run(
                        ["unshare", "-rn", "node", file_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=5,
                        preexec_fn=_limits_vm,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                elif language == "c":
                    file_path = os.path.join(tempdir, "temp.c")
                    with open(file_path, "w") as f:
                        f.write(code)
                    out_path = os.path.join(tempdir, "out")
                    compile_res = subprocess.run(
                        ["gcc", file_path, "-o", out_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=20,
                        preexec_fn=_limits_compiler,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                    if compile_res.returncode != 0:
                        return {"stdout": "", "stderr": _truncate(compile_res.stderr)}
                    result = subprocess.run(
                        ["unshare", "-rn", out_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=5,
                        preexec_fn=_limits,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                elif language == "cpp":
                    file_path = os.path.join(tempdir, "temp.cpp")
                    with open(file_path, "w") as f:
                        f.write(code)
                    out_path = os.path.join(tempdir, "out")
                    compile_res = subprocess.run(
                        ["g++", file_path, "-o", out_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=20,
                        preexec_fn=_limits_compiler,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                    if compile_res.returncode != 0:
                        return {"stdout": "", "stderr": _truncate(compile_res.stderr)}
                    result = subprocess.run(
                        ["unshare", "-rn", out_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=5,
                        preexec_fn=_limits,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                elif language == "java":
                    file_path = os.path.join(tempdir, "Main.java")
                    with open(file_path, "w") as f:
                        f.write(code)
                    compile_res = subprocess.run(
                        ["javac", file_path],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=20,
                        preexec_fn=_limits_compiler,
                        env=sandbox_env,
                        cwd=tempdir,
                    )
                    if compile_res.returncode != 0:
                        return {"stdout": "", "stderr": _truncate(compile_res.stderr)}
                    result = subprocess.run(
                        ["unshare", "-rn", "java", "-cp", tempdir, "Main"],
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=5,
                        preexec_fn=_limits_vm,
                        env=sandbox_env,
                        cwd=tempdir,
                    )

                stderr = result.stderr or ""
                if result.returncode != 0 and stderr.strip().startswith("unshare:"):
                    raise HTTPException(
                        status_code=503,
                        detail=f"sandbox isolation unavailable: {stderr.strip()}"
                    )
                if result.returncode in (-signal.SIGXCPU, -signal.SIGKILL, -9, -24) and not stderr:
                    stderr = "Execution timed out."
                return {"stdout": _truncate(result.stdout), "stderr": _truncate(stderr)}
            except HTTPException:
                raise
            except subprocess.TimeoutExpired:
                return {"stdout": "", "stderr": "Execution timed out."}
            except Exception as e:
                return {"stdout": "", "stderr": _truncate(str(e))}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)
