#!/usr/bin/env python3
"""
D3-Gym environment creation workflow.

  python run_d3_creation_workflow.py --input-dir ./matched_tasks --output-dir ./final_tasks
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_step(name: str, cmd: list[str]) -> bool:
    print(f"\n{'=' * 60}")
    print(f"Step: {name}")
    print(f"{'=' * 60}")
    print(f"  {' '.join(cmd)}\n")

    start = time.time()
    result = subprocess.run(cmd, check=False)
    elapsed = time.time() - start

    ok = result.returncode == 0
    tag = "OK" if ok else "FAILED"
    print(f"\n  [{tag}] {name} ({elapsed:.1f}s)")
    return ok


def main():
    p = argparse.ArgumentParser(
        description="D3-Gym env-creation workflow"
    )

    p.add_argument("--start-from", type=int, default=1, choices=[1, 2, 3, 4],
                   help="Start from step N (default: 1)")
    p.add_argument("--stop-at", type=int, default=4, choices=[1, 2, 3, 4],
                   help="Stop after step N (default: 4)")

    p.add_argument("--input-dir", type=str, required=True,
                   help="Input directory of matched task_* folders")
    p.add_argument("--output-dir", type=str, required=True,
                   help="Final output directory")
    p.add_argument("--step1-output", type=str, default=None,
                   help="Override Step 1 output dir (default: <output>/step1_filtered)")
    p.add_argument("--step2-output", type=str, default=None,
                   help="Override Step 2 output dir (default: <output>/step2_executed)")
    p.add_argument("--step3-output", type=str, default=None,
                   help="Override Step 3 output dir (default: <output>/step3_validated)")

    p.add_argument("--filter-workers", type=int, default=16,
                   help="Parallel workers for Step 1 (default: 16)")

    p.add_argument("--exec-workers", type=int, default=8,
                   help="Parallel workers for Step 2 (default: 8)")
    p.add_argument("--skip-env-setup", action="store_true",
                   help="Reuse existing conda environments")
    p.add_argument("--python-version", type=str, default="3.9",
                   help="Python version for conda envs (default: 3.9)")

    p.add_argument("--judge-engine", type=str,
                   default="us.anthropic.claude-sonnet-4-20250514-v1:0",
                   help="LLM engine for gold result judging")
    p.add_argument("--judge-litellm-model", type=str, default=None,
                   help="LiteLLM model name for judge cost tracking")
    p.add_argument("--judge-workers", type=int, default=8,
                   help="Parallel workers for Step 3 (default: 8)")

    p.add_argument("--eval-engine", type=str,
                   default="us.anthropic.claude-sonnet-4-20250514-v1:0",
                   help="LLM engine for eval script generation")
    p.add_argument("--eval-litellm-model", type=str, default=None,
                   help="LiteLLM model name for eval script cost tracking")
    p.add_argument("--eval-workers", type=int, default=4,
                   help="Parallel workers for Step 4 (default: 4)")

    args = p.parse_args()

    output_base = Path(args.output_dir).resolve()
    output_base.mkdir(parents=True, exist_ok=True)

    step1_out = Path(args.step1_output) if args.step1_output else output_base / "step1_filtered"
    step2_out = Path(args.step2_output) if args.step2_output else output_base / "step2_executed"
    step3_out = Path(args.step3_output) if args.step3_output else output_base / "step3_validated"
    step4_out = output_base / "step4_final"

    steps = []

    if args.start_from <= 1 <= args.stop_at:
        cmd = [
            sys.executable, "filter_tasks.py",
            "--input-dir", str(Path(args.input_dir).resolve()),
            "--output-dir", str(step1_out),
            "--max-workers", str(args.filter_workers),
        ]
        steps.append(("Step 1: Filter & Preview", cmd))

    if args.start_from <= 2 <= args.stop_at:
        step2_input = str(step1_out) if args.start_from <= 1 else str(Path(args.input_dir).resolve())
        cmd = [
            sys.executable, "execute_programs.py",
            "--input-dir", step2_input,
            "--output-dir", str(step2_out),
            "--max-workers", str(args.exec_workers),
            "--python-version", args.python_version,
        ]
        if args.skip_env_setup:
            cmd.append("--skip-env-setup")
        steps.append(("Step 2: Execute Gold Programs", cmd))

    if args.start_from <= 3 <= args.stop_at:
        step3_input = str(step2_out) if args.start_from <= 2 else str(Path(args.input_dir).resolve())
        cmd = [
            sys.executable, "judge_results.py",
            "--input-dir", step3_input,
            "--output-dir", str(step3_out),
            "--llm-engine", args.judge_engine,
            "--max-workers", str(args.judge_workers),
        ]
        if args.judge_litellm_model:
            cmd.extend(["--litellm-model-name", args.judge_litellm_model])
        steps.append(("Step 3: Judge Gold Results", cmd))

    if args.start_from <= 4 <= args.stop_at:
        step4_input = str(step3_out) if args.start_from <= 3 else str(Path(args.input_dir).resolve())
        cmd = [
            sys.executable, "generate_eval_scripts.py",
            "--input-dir", step4_input,
            "--output-dir", str(step4_out),
            "--llm-engine-name", args.eval_engine,
            "--max-workers", str(args.eval_workers),
        ]
        if args.eval_litellm_model:
            cmd.extend(["--litellm-model-name", args.eval_litellm_model])
        steps.append(("Step 4: Generate Eval Scripts", cmd))

    print(f"D3-Gym Workflow — steps {args.start_from} to {args.stop_at}")
    total_start = time.time()

    for name, cmd in steps:
        if not run_step(name, cmd):
            print(f"\nPipeline stopped at: {name}")
            sys.exit(1)

    total = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete in {total:.1f}s")
    print(f"Final output: {step4_out}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
