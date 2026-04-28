# D3-Gym

<p align="center">
  <a href="https://arxiv.org/abs/XXXX.XXXXX">[Paper]</a> &nbsp;
  <a href="https://huggingface.co/datasets/PLACEHOLDER">[HuggingFace]</a> &nbsp;
  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">[Docker Hub]</a>
</p>

D3-Gym is the first automatically constructed dataset composed of verifiable environments for Data-Driven Discovery. D3-Gym comprises 565 tasks sourced from 239 real scientific repositories across four disciplines (bioinformatics, computational chemistry, geographic information science, and psychology and cognitive neuroscience). Each task is equipped with a natural language instruction, an executable environment with pre-installed dependencies, input dataset and artifact previews, a reference code solution, and an automatically synthesized evaluation script. 

<img width="875" height="418" alt="image" src="https://github.com/user-attachments/assets/febdd151-ab66-4c1e-a1e9-db109b65e068" />

## Using D3-Gym Environments

D3-Gym provides 565 self-contained Docker environments, each packaging a
data-driven discovery task composed of a task instruction, datasets and file dependencies along with their previews, reference solution and output, and an evaluation script. You write a `solution.py` that reads the task's dataset and writes
results to `pred_results/`; the evaluation script evaluates the solution and returns a pass/fail verdict. 

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

Each image represents a data-driven discovery task with the following structure:

```
/task/
  task_instruction.txt          # what to solve
  benchmark/datasets/           # input data (CSV, JSON, images, etc.)
  *_preview.txt                 # dataset schema previews
  eval_script.py                # evaluation logic (compares pred vs gold)
  gold_results/                 # reference outputs
  pred_results/                 # your solution writes here
  entrypoint.sh                 # routes commands
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
# Run + evaluate 
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
