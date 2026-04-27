# D3-Gym

<p align="center">
  <a href="https://arxiv.org/abs/XXXX.XXXXX">[Paper]</a> &nbsp;
  <a href="https://huggingface.co/datasets/PLACEHOLDER">[HuggingFace]</a> &nbsp;
  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">[Docker Hub]</a>
</p>

## Introduction

*TODO*

## Using D3-Gym Environments

D3-Gym provides 308 self-contained Docker environments, each packaging a
data-driven discovery task with its dataset, evaluation script, and reference
outputs. You write a `solution.py` that reads the task's dataset and writes
results to `pred_results/`; the built-in evaluator compares your outputs against
the gold reference and returns a pass/fail verdict.

### Quick start

Pull a task image and read its instructions:

```bash
docker pull hananemoussa/d3-gym:task_1
docker run --rm hananemoussa/d3-gym:task_1 inspect
```

Write your solution, then run and evaluate:

```bash
docker run --rm \
  -v $(pwd)/solution.py:/task/solution.py:ro \
  hananemoussa/d3-gym:task_1 run_and_eval
```

### Container layout

Each image has the following structure inside `/task/`:

```
/task/
  task_instruction.txt          # what to solve
  benchmark/datasets/           # input data (CSV, JSON, images, etc.)
  *_preview.txt                 # dataset schema previews (optional)
  eval_script.py                # evaluation logic (compares pred vs gold)
  gold_results/                 # reference outputs
  pred_results/                 # your solution writes here
  entrypoint.sh                 # routes commands
```

### Writing a solution

Your `solution.py` runs from `/task/` as the working directory. Read input data
from `benchmark/datasets/`, compute your results, and write output files to
`pred_results/`. The exact filenames expected are task-specific -- check the task
instruction and dataset previews via `inspect`.

```python
import pandas as pd
import os

df = pd.read_csv("benchmark/datasets/data.csv")

# ... your analysis ...

os.makedirs("pred_results", exist_ok=True)
df_result.to_csv("pred_results/output.csv", index=False)
```

### Available actions

| Action | Description | Requires |
|--------|-------------|----------|
| `run` | Execute `solution.py` | Mount solution |
| `eval` | Evaluate existing `pred_results/` | Mount results dir |
| `run_and_eval` | Run solution then evaluate | Mount solution |
| `inspect` | Print task instruction and dataset file listing | Nothing |
| `shell` | Interactive bash session | `-it` flag |
| `help` | Print usage | Nothing |

### Mounting your solution

```bash
# Run + evaluate (most common)
docker run --rm \
  -v $(pwd)/solution.py:/task/solution.py:ro \
  hananemoussa/d3-gym:task_1 run_and_eval

# Evaluate pre-computed results
docker run --rm \
  -v $(pwd)/my_results:/task/pred_results:ro \
  hananemoussa/d3-gym:task_1 eval

# Interactive debugging
docker run --rm -it hananemoussa/d3-gym:task_1 shell
```

### Reading evaluation output

The evaluation script prints a result line and a reason:

```
=== Running evaluation ===
Result: True
Reason: Overall MAE = 0.031 (threshold < 0.20)
```

A passing task prints `Result: True`; a failing one prints `Result: False` with
an explanation. To check programmatically:

```python
import subprocess

result = subprocess.run(
    ["docker", "run", "--rm",
     "-v", "solution.py:/task/solution.py:ro",
     "hananemoussa/d3-gym:task_1", "run_and_eval"],
    capture_output=True, text=True
)
passed = "Result: True" in result.stdout
```

### Batch evaluation

Loop over all 308 tasks:

```bash
for i in $(seq 1 308); do
  echo "=== task_$i ==="
  docker run --rm \
    -v $(pwd)/solutions/task_${i}.py:/task/solution.py:ro \
    hananemoussa/d3-gym:task_$i run_and_eval
done
```
