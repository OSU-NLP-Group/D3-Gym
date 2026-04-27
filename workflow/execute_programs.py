#!/usr/bin/env python3
"""Execute gold_program.py for each task inside isolated conda environments."""

import argparse
import json
import os
import shutil
import subprocess
import time
import traceback
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def install_dependencies(task_path: Path, conda_env: str, worker_id: int):
    gold_program = task_path / "gold_program.py"
    if not gold_program.exists():
        return False, "gold_program.py not found"

    tmp_dir = Path(f"/tmp/pipreqs_scan_{worker_id}_{os.getpid()}")
    req_file = Path(f"/tmp/reqs_{worker_id}_{os.getpid()}.txt")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()

    try:
        shutil.copy(gold_program, tmp_dir / "gold_program.py")
        pr = subprocess.run(
            ["pipreqs", str(tmp_dir), f"--savepath={req_file}", "--mode", "no-pin"],
            capture_output=True, timeout=60,
        )
        if pr.returncode != 0:
            stderr = pr.stderr.decode("utf-8", errors="ignore")
            if "No imports found" in stderr:
                return True, ""
            return False, f"pipreqs failed: {stderr[:500]}"

        if not req_file.exists() or not req_file.read_text().strip():
            return True, ""

        reqs = req_file.read_text().strip()
        logging.info(f"  Installing: {reqs.replace(chr(10), ', ')}")

        ir = subprocess.run(
            ["conda", "run", "-n", conda_env, "pip", "install", "-r", str(req_file)],
            capture_output=True, env=os.environ.copy(), timeout=600,
        )
        if ir.returncode != 0:
            stderr = ir.stderr.decode("utf-8", errors="ignore")[:200]
            logging.warning(f"  Some deps failed (continuing): {stderr}")
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Dependency install timeout"
    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        req_file.unlink(missing_ok=True)


def execute_gold_program(task_path: Path, conda_env: str, worker_id: int) -> dict:
    task_name = task_path.name
    gold_results_dir = task_path / "gold_results"
    gold_results_dir.mkdir(exist_ok=True)
    result = {
        "task": task_name, "task_path": str(task_path),
        "success": False, "error": None, "execution_time": 0,
    }
    start = time.time()

    try:
        ok, err = install_dependencies(task_path, conda_env, worker_id)
        if not ok:
            result["error"] = f"Dependency install failed: {err}"
            result["execution_time"] = time.time() - start
            (gold_results_dir / "error.txt").write_text(result["error"])
            return result

        proc = subprocess.run(
            ["conda", "run", "-n", conda_env, "python", "gold_program.py"],
            capture_output=True, text=True, timeout=600, cwd=str(task_path),
        )
        result["execution_time"] = time.time() - start

        if proc.returncode == 0:
            result["success"] = True
            logging.info(f"{task_name}: Execution OK ({result['execution_time']:.1f}s)")
            if proc.stdout:
                (gold_results_dir / "stdout.txt").write_text(proc.stdout)
        else:
            result["error"] = f"Exit code {proc.returncode}"
            if proc.stderr:
                result["error"] += f"\n{proc.stderr[:1000]}"
            (gold_results_dir / "error.txt").write_text(
                f"Exit code: {proc.returncode}\n\nStdout:\n{proc.stdout}\n\nStderr:\n{proc.stderr}"
            )
    except subprocess.TimeoutExpired:
        result["execution_time"] = time.time() - start
        result["error"] = "Timeout (600s)"
        (gold_results_dir / "error.txt").write_text("Execution timeout after 600 seconds\n")
    except Exception as e:
        result["execution_time"] = time.time() - start
        result["error"] = f"Exception: {e}"
        (gold_results_dir / "error.txt").write_text(f"{e}\n{traceback.format_exc()}")

    out_exts = {".png", ".jpg", ".jpeg", ".pdf", ".csv", ".json", ".txt", ".xlsx"}
    for item in task_path.iterdir():
        if (item.is_file() and item.suffix in out_exts
                and time.time() - item.stat().st_mtime < 120
                and item.name not in ("gold_program.py", "task_instruction.txt")):
            shutil.move(str(item), str(gold_results_dir / item.name))

    return result


def setup_conda_environments(n_workers: int, python_version: str = "3.9"):
    logging.info(f"Setting up {n_workers} conda environments (Python {python_version})...")
    common_pkgs = ["numpy", "pandas", "matplotlib", "scipy", "scikit-learn", "pillow"]

    for wid in range(n_workers):
        env_name = f"autosdt-worker-{wid}"
        check = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
        if env_name in check.stdout:
            logging.info(f"  Reusing existing env: {env_name}")
            continue
        logging.info(f"  Creating env: {env_name}")
        subprocess.run(
            ["conda", "create", "-n", env_name, f"python={python_version}", "-y"],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["conda", "run", "-n", env_name, "pip", "install"] + common_pkgs,
            capture_output=True, text=True,
        )
    logging.info("Conda environments ready.")


def main():
    parser = argparse.ArgumentParser(
        description="Execute gold programs in conda environments (Step 2)"
    )
    parser.add_argument("--input-dir", type=str, required=True,
                        help="Directory of filtered task_* folders")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Output directory (only successfully executed tasks)")
    parser.add_argument("--max-workers", type=int, default=8,
                        help="Parallel workers (default: 8)")
    parser.add_argument("--skip-env-setup", action="store_true",
                        help="Reuse existing conda environments")
    parser.add_argument("--python-version", type=str, default="3.9",
                        help="Python version for conda envs (default: 3.9)")
    args = parser.parse_args()

    input_path = Path(args.input_dir).resolve()
    output_path = Path(args.output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    logs_dir = output_path / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / f"execute_gold_{ts}.log"),
            logging.StreamHandler(),
        ],
    )

    task_folders = sorted(
        d for d in input_path.iterdir() if d.is_dir() and d.name.startswith("task_")
    )
    logging.info(f"Found {len(task_folders)} tasks in {input_path}")

    if not args.skip_env_setup:
        setup_conda_environments(args.max_workers, args.python_version)

    start = time.time()
    all_results = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {}
        for idx, tf in enumerate(task_folders):
            wid = idx % args.max_workers
            conda_env = f"autosdt-worker-{wid}"
            futures[pool.submit(execute_gold_program, tf, conda_env, wid)] = tf

        done = 0
        for fut in as_completed(futures):
            tf = futures[fut]
            done += 1
            try:
                res = fut.result()
                all_results.append(res)

                if res["success"]:
                    dest = output_path / tf.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(tf, dest)
                    logging.info(f"[{done}/{len(task_folders)}] {res['task']}: OK — copied")
                else:
                    logging.warning(f"[{done}/{len(task_folders)}] {res['task']}: "
                                    f"FAILED — {res['error'][:120]}")
            except Exception as e:
                logging.error(f"[{done}/{len(task_folders)}] {tf.name}: Exception - {e}")
                all_results.append({
                    "task": tf.name, "task_path": str(tf),
                    "success": False, "error": str(e), "execution_time": 0,
                })

    elapsed = time.time() - start
    success_count = sum(1 for r in all_results if r["success"])

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(task_folders),
        "successful": success_count,
        "failed": len(task_folders) - success_count,
        "elapsed_seconds": round(elapsed, 1),
        "results": [{k: v for k, v in r.items() if k != "task_path"} for r in all_results],
    }
    with open(logs_dir / f"execution_summary_{ts}.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logging.info(f"Done in {elapsed:.1f}s. Succeeded: {success_count}/{len(task_folders)}. "
                 f"Output: {output_path}")


if __name__ == "__main__":
    main()
