#!/usr/bin/env python3
"""Validate tasks for real data and generate dataset previews via Claude Code headless."""

import argparse
import json
import os
import shutil
import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

FILTER_PROMPT_TEMPLATE = """\
You are a coding agent with access to the local file system. You are given a \
candidate task consisting of a Python program (gold_program.py) and its \
associated data files. Your objective is twofold: (1) determine whether this \
task uses only real data and real library dependencies, with no mock, stub, or \
simulated logic; and (2) if the task is valid, generate dataset preview files \
for downstream use.

Phase 1: Task Validation
Carry out the following steps to determine task validity:

1. Identify Data Files. Inspect the Python program and extract every file path \
that it attempts to open, read, load, or process. For each path:
   - Verify whether the file exists on the current file system.
   - Read a small portion of the file to confirm it contains real, meaningful \
data (not empty, not placeholder, not all zeros, not constant meaningless \
values, not randomly generated toy content).
   If all referenced data files exist and contain valid data, set dummy_data = 0; \
otherwise set dummy_data = 1.

2. Check for Mock or Simulated Logic. Analyze the program for any of the following:
   - Mock objects or unittest.mock usage (e.g., Mock(), MagicMock, patch).
   - Custom stub or fake class implementations replacing real libraries.
   - Synthetic data generation used as primary input instead of loading from files.
   - Hardcoded dummy values pretending to be real data.
   - try-except blocks catching ImportError and defining mock replacements.
   - Any workaround for missing dependencies that bypasses the real library.
   If the program contains any such logic, set has_mock = 1; otherwise set has_mock = 0.

3. Render Verdict. If dummy_data == 0 and has_mock == 0, set valid = 1; \
otherwise set valid = 0. If valid = 0, skip Phase 2 and proceed directly to the output.

Phase 2: Dataset Preview Generation (only if valid = 1).
For each data file referenced by the program, generate a preview file showing \
only the raw data schema:
   - For CSV or tabular data: the header row plus 3-5 example rows.
   - For JSON: a snippet showing the structure with 1-2 entries.
   - For text files: the first few lines of raw content.
   - For binary or image files: a brief factual description (e.g., "PNG images, 224x224, RGB").
Each preview must follow the format:
[START Preview of <file_path>]
<raw data snippet>
[END Preview of <file_path>]
Do not include explanations, analysis, or task-solving guidance in previews.

Output Format. Return exactly the following four lines at the end of your response:

#### dummy_data: 0 or 1
#### has_mock: 0 or 1
#### valid: 0 or 1
#### response: <concise explanation>
"""

def call_claude_headless(prompt: str, cwd: str, timeout: int = 300) -> str:
    cmd = [
        "claude", "-p",
        "--output-format", "text",
        "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep",
        "--permission-mode", "acceptEdits",
    ]
    env = os.environ.copy()
    env["CLAUDE_CODE_USE_BEDROCK"] = "1"
    env["AWS_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

    try:
        proc = subprocess.run(
            cmd, input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=timeout, cwd=cwd, env=env,
        )
    except subprocess.TimeoutExpired:
        return f"[claude-exception] Timeout after {timeout}s"
    except Exception as e:
        return f"[claude-exception] {e}"

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore")[:500]
        stdout = proc.stdout.decode("utf-8", errors="ignore")[:500]
        return f"[claude-error] rc={proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"

    return proc.stdout.decode("utf-8", errors="ignore")


def parse_filter_response(response: str) -> dict:
    result = {"dummy_data": None, "has_mock": None, "valid": None, "response": ""}
    for line in response.split("\n"):
        if line.startswith("#### dummy_data:"):
            try: result["dummy_data"] = int(line.split(":")[-1].strip())
            except ValueError: pass
        elif line.startswith("#### has_mock:"):
            try: result["has_mock"] = int(line.split(":")[-1].strip())
            except ValueError: pass
        elif line.startswith("#### valid:"):
            try: result["valid"] = int(line.split(":")[-1].strip())
            except ValueError: pass
        elif line.startswith("#### response:"):
            result["response"] = line.split(":", 1)[-1].strip()

    if result["valid"] is None and result["dummy_data"] is not None and result["has_mock"] is not None:
        result["valid"] = 1 if result["dummy_data"] == 0 and result["has_mock"] == 0 else 0
    return result


def process_task(task_path: Path, output_path: Path) -> dict:
    task_name = task_path.name
    info = {"task": task_name, "valid": False, "error": None}

    logging.info(f"[{task_name}] Filtering...")
    raw = call_claude_headless(FILTER_PROMPT_TEMPLATE, cwd=str(task_path))

    if raw.startswith("[claude-error]") or raw.startswith("[claude-exception]"):
        info["error"] = f"Filter agent error: {raw[:300]}"
        logging.error(f"[{task_name}] {info['error']}")
        return info

    parsed = parse_filter_response(raw)
    info["filter_result"] = parsed

    if parsed["valid"] != 1:
        info["error"] = f"Filtered out: {parsed['response']}"
        logging.info(f"[{task_name}] Invalid (dummy_data={parsed['dummy_data']}, "
                     f"has_mock={parsed['has_mock']})")
        return info

    info["valid"] = True

    dest = output_path / task_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(task_path, dest)
    logging.info(f"[{task_name}] Valid — copied to output")

    return info


def main():
    parser = argparse.ArgumentParser(
        description="Filter tasks and generate dataset previews (Step 1)"
    )
    parser.add_argument("--input-dir", type=str, required=True,
                        help="Directory of task_* folders (already matched)")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Output directory for valid tasks with previews")
    parser.add_argument("--max-workers", type=int, default=16,
                        help="Parallel workers (default: 16)")
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
            logging.FileHandler(logs_dir / f"filter_tasks_{ts}.log"),
            logging.StreamHandler(),
        ],
    )

    task_folders = sorted(
        d for d in input_path.iterdir() if d.is_dir() and d.name.startswith("task_")
    )
    logging.info(f"Found {len(task_folders)} tasks in {input_path}")

    start = time.time()
    all_results = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {
            pool.submit(process_task, tf, output_path): tf
            for tf in task_folders
        }
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                res = fut.result()
                all_results.append(res)
                status = "VALID" if res["valid"] else "INVALID"
                logging.info(f"[{done}/{len(task_folders)}] {res['task']}: {status}")
            except Exception as e:
                tf = futures[fut]
                logging.error(f"[{done}/{len(task_folders)}] {tf.name}: Exception - {e}")
                all_results.append({"task": tf.name, "valid": False, "error": str(e)})

    elapsed = time.time() - start
    valid_count = sum(1 for r in all_results if r.get("valid"))

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(task_folders),
        "valid": valid_count,
        "invalid": len(task_folders) - valid_count,
        "elapsed_seconds": round(elapsed, 1),
        "results": all_results,
    }
    with open(logs_dir / f"filter_results_{ts}.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logging.info(f"Done in {elapsed:.1f}s. Valid: {valid_count}/{len(task_folders)}. "
                 f"Output: {output_path}")


if __name__ == "__main__":
    main()
