#!/usr/bin/env python3
"""Generate eval scripts via a planner+coder LLM pipeline."""

import argparse
import json
import shutil
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from string import Template
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.base_engine import LLMEngine
from utils import CostTracker, extract_code, get_preview_files_content, get_gold_results_content


log_dir = Path("planner_coder_logs")
log_dir.mkdir(exist_ok=True)
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"eval_script_gen_{_ts}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_cost_tracker: CostTracker = None

_all_plans = []
_plans_lock = threading.Lock()
_plans_file = log_dir / f"evaluation_plans_{_ts}.json"


PLANNER_PROMPT = Template("""\
You are an expert in scientific data analysis and evaluation methodology. \
Your task is to analyze a data-driven discovery task and produce a concrete \
evaluation plan that a coding agent will implement.

Inputs Provided:
- Task Description: the natural-language instruction defining the analysis.
- Dataset Information: the dataset path, folder structure, and schema previews.
- Expected Output Files: the list of files the gold program produces.
- Gold Result Files: the actual content of the reference outputs.

Instructions. Produce a structured evaluation plan covering:

1. Task Type. Classify the task (e.g., classification, regression, clustering, \
visualization, statistical analysis, simulation).

2. Evaluation Metrics. Specify which metric(s) are appropriate and justify why:
   - Classification: if the dataset is imbalanced, prefer F1-score, balanced \
accuracy, AUROC, or AUPRC over accuracy.
   - Regression: consider MAE, RMSE, R^2, or domain-specific error metrics.
   - Statistical analysis: consider p-values, effect sizes, confidence intervals.
   - Clustering: consider silhouette score, Davies-Bouldin index, or \
domain-specific quality measures.
   - Other: specify domain-appropriate criteria.

3. Success Thresholds. Define specific threshold values for each metric, \
grounded in domain standards and task complexity.

4. Special Considerations. Note any domain-specific requirements such as \
handling of missing data, biological versus statistical significance, \
cross-validation needs, or output format constraints.

5. Evaluation Steps. Provide a clear 3-5 step evaluation procedure that the \
coding agent should follow.

Output Requirements. The plan must be concise, unambiguous, and specify \
exactly one evaluation strategy. Avoid presenting multiple alternatives or \
optional branches.

---

[Task Description]
${task_instruction}

[Dataset Information]
Dataset path: ${dataset_path}
Dataset folder tree:
${dataset_folder_tree}
Dataset preview:
${dataset_preview}

[Expected Output Files]
${output_fnames}

[Gold Result Files Content]
${gold_results_listing}
""")


CODER_PROMPT = Template("""\
You are a Python coding assistant. Your task is to generate an evaluation \
script for a scientific computing benchmark, following the evaluation plan \
provided by an expert and the conventions specified below.

Inputs Provided:
- Evaluation Plan: the structured plan produced by the evaluation planner.
- Task Instruction: the natural-language description of the analysis task.
- Dataset Information: the dataset path, folder structure, and schema previews.
- Expected Output Files: the list of files the gold program produces in pred_results/.
- Gold Result Files: the reference output contents in gold_results/.

Conventions. The generated script must adhere to the following:

1. Directory layout (hardcoded paths):
   - Predicted results: ./pred_results/
   - Gold results: ./benchmark/eval_programs/gold_results/

2. Function signature: Define a top-level eval() function taking no parameters. \
It returns a tuple (result, message) where result is a boolean (True/False) \
indicating pass/fail and message is a string with details.

3. Visual evaluation (for tasks producing plots or images): use an LLM-as-a-judge \
approach to compare the predicted and gold visual outputs.

4. Main block:
   if __name__ == "__main__":
       ok, msg = eval()
       print(ok, msg)

5. Error handling: Wrap the body of eval() in a try/except so that unexpected \
errors return (False, f"Error: {e}") rather than crashing.

6. File existence checks: Verify that both predicted and gold files exist \
before loading. Return (False, "Missing file: ...") if any file is absent.

Output Format. Respond with ONLY the Python source code for the evaluation \
script. Do not include any explanation or markdown formatting.

---

[Evaluation Plan]
${evaluation_plan}

[Task Instruction]
${task_instruction}

[Dataset Information]
Dataset path: ${dataset_path}
Dataset folder tree:
${dataset_folder_tree}
Dataset preview:
${dataset_preview}

[Expected Output Files]
${output_fnames}

[Gold Result Files]
${gold_results_listing}
""")


def get_evaluation_plan(engine: LLMEngine, task_info: dict, task_name: str) -> str:
    prompt = PLANNER_PROMPT.substitute(**task_info)
    messages = [{"role": "user", "content": prompt}]
    response, ptok, ctok, _ = engine.respond(messages, temperature=0.1, top_p=0.95)
    logger.info(f"Planner: {ptok} prompt + {ctok} completion tokens")
    _cost_tracker.track(ptok, ctok, task_name)
    return response.strip()


def generate_eval_script(engine: LLMEngine, task_info: dict, plan: str, task_name: str) -> str:
    prompt = CODER_PROMPT.substitute(evaluation_plan=plan, **task_info)
    messages = [{"role": "user", "content": prompt}]
    response, ptok, ctok, _ = engine.respond(messages, temperature=0.1, top_p=0.95, max_tokens=8192)
    logger.info(f"Coder: {ptok} prompt + {ctok} completion tokens")
    _cost_tracker.track(ptok, ctok, task_name)
    return extract_code(response)


def process_task(task_folder: Path, output_path: Path, llm_engine_name: str) -> dict:
    task_name = task_folder.name
    result = {"task_name": task_name, "success": False, "error": None}

    try:
        dest = output_path / task_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(task_folder, dest)

        instr_file = dest / "task_instruction.txt"
        if not instr_file.exists():
            result["error"] = "Missing task_instruction.txt"
            return result
        task_instruction = instr_file.read_text(encoding="utf-8").strip()

        eval_path = dest / "eval_script.py"
        if eval_path.exists():
            result["success"] = True
            result["skipped"] = True
            return result

        dataset_preview = get_preview_files_content(dest)
        dataset_folder_tree = "(not available)"
        tree_file = dest / "dataset_folder_tree.txt"
        if tree_file.exists():
            dataset_folder_tree = tree_file.read_text(encoding="utf-8").strip()

        pred_results = dest / "pred_results"
        output_fnames_list = sorted(f.name for f in pred_results.iterdir() if f.is_file()) if pred_results.exists() else []
        output_fnames_str = "\n".join(f"pred_results/{fn}" for fn in output_fnames_list) or "(not available)"

        gold_dir = dest / "benchmark" / "eval_programs" / "gold_results"
        gold_content = get_gold_results_content(gold_dir, output_fnames_list)

        task_info = {
            "task_instruction": task_instruction,
            "dataset_path": ".",
            "dataset_folder_tree": dataset_folder_tree,
            "dataset_preview": dataset_preview,
            "output_fnames": output_fnames_str,
            "gold_results_listing": gold_content,
        }

        engine = LLMEngine(llm_engine_name)

        logger.info(f"[{task_name}] Planning...")
        plan = get_evaluation_plan(engine, task_info, task_name)

        with _plans_lock:
            _all_plans.append({
                "task_name": task_name,
                "timestamp": datetime.now().isoformat(),
                "task_instruction": task_instruction,
                "evaluation_plan": plan,
            })
            with open(_plans_file, "w") as f:
                json.dump(_all_plans, f, indent=2)

        logger.info(f"[{task_name}] Generating eval script...")
        code = generate_eval_script(engine, task_info, plan, task_name)
        eval_path.write_text(code, encoding="utf-8")
        logger.info(f"[{task_name}] Saved eval_script.py ({len(code)} chars)")

        if eval_path.stat().st_size == 0:
            result["error"] = "Generated eval_script.py is empty"
            return result

        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[{task_name}] {e}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate evaluation scripts via planner+coder LLM (Step 3)"
    )
    parser.add_argument("--input-dir", type=str, required=True,
                        help="Directory of validated task_* folders")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Output directory with eval scripts added")
    parser.add_argument("--llm-engine-name", type=str,
                        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
                        help="LLM engine for both planner and coder")
    parser.add_argument("--litellm-model-name", type=str, default=None,
                        help="LiteLLM model name for cost tracking")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()

    global _cost_tracker
    _cost_tracker = CostTracker(
        args.litellm_model_name or args.llm_engine_name,
        step_name="generate_eval_scripts",
    )

    input_path = Path(args.input_dir).resolve()
    output_path = Path(args.output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    task_folders = sorted(
        d for d in input_path.iterdir() if d.is_dir() and d.name.startswith("task_")
    )
    logger.info(f"Found {len(task_folders)} tasks. Workers: {args.max_workers}")

    start = time.time()
    success, skipped = 0, 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futs = {
            pool.submit(process_task, tf, output_path, args.llm_engine_name): tf
            for tf in task_folders
        }
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                res = fut.result()
                if res["success"]:
                    if res.get("skipped"):
                        skipped += 1
                        logger.info(f"[{done}/{len(task_folders)}] {res['task_name']}: Skipped")
                    else:
                        success += 1
                        logger.info(f"[{done}/{len(task_folders)}] {res['task_name']}: Success")
                else:
                    logger.error(f"[{done}/{len(task_folders)}] {res['task_name']}: "
                                 f"Failed - {res['error']}")
            except Exception as e:
                logger.error(f"[{done}/{len(task_folders)}] Exception: {e}")

    elapsed = time.time() - start
    logger.info(f"Done in {elapsed:.1f}s. Success: {success}, Skipped: {skipped}, "
                f"Failed: {len(task_folders) - success - skipped}")
    print(f"Eval scripts saved to: {output_path}")
    _cost_tracker.save_report(output_path)


if __name__ == "__main__":
    main()
