# D3-Gym

<p align="center">
  <a href="https://arxiv.org/abs/XXXX.XXXXX">[Paper]</a> &nbsp;
  <a href="https://huggingface.co/datasets/PLACEHOLDER">[HuggingFace]</a> &nbsp;
  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">[Docker Hub]</a>
</p>

D3-Gym is the first automatically constructed dataset of **verifiable environments** for **Data-Driven Discovery**. It contains 565 tasks derived from 239 real-world scientific repositories across four domains: bioinformatics, computational chemistry, geographic information science, and psychology and cognitive neuroscience.

Each task includes:
- a natural language instruction,
- an executable environment with pre-installed dependencies,
- input datasets and artifact previews,
- a reference implementation,
- and an automatically generated evaluation script.

<p align="center">
  <img width="875" height="418" alt="image" src="https://github.com/user-attachments/assets/febdd151-ab66-4c1e-a1e9-db109b65e068" />
</p>

---

## Using D3-Gym Environments

All task environments are distributed as Docker images via  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">Docker Hub</a>.

Each image is a self-contained unit representing a single data-driven discovery task. It includes the task specification, datasets and previews, reference outputs, and evaluation script, along with pre-installed dependencies.

To solve a task, provide a `solution.py` that:
- reads the provided datasets, and  
- writes outputs to `pred_results/`.

The evaluation script compares your outputs against the reference and returns a pass/fail decision with a short explanation.

For easier browsing, we also provide an annotation sheet with metadata for all tasks on <a href="https://huggingface.co/datasets/hananour/D3-Gym">HuggingFace</a>.  


---

## Quick Start

Pull a task image and inspect it:

~~~bash
docker pull hananemoussa/d3-gym:task_1
docker run --rm hananemoussa/d3-gym:task_1 inspect
~~~

Run your solution and evaluate:

~~~bash
docker run --rm \
  -v $(pwd)/solution.py:/task/solution.py:ro \
  hananemoussa/d3-gym:task_1 run_and_eval
~~~

---

## Environment Structure

Each Docker image exposes the following directory layout:

~~~
/task/
  task_instruction.txt     # task description
  datasets/                # input data (CSV, JSON, images, etc.)
  *_preview.txt            # dataset schema previews
  eval_script.py           # evaluation logic
  gold_results/            # reference outputs
  pred_results/            # expected location for your outputs
  entrypoint.sh            # command routing
~~~

---

## Available Commands

| Command        | Description                                      | Requires                  |
|----------------|--------------------------------------------------|---------------------------|
| `run`          | Execute `solution.py`                            | Provide solution file     |
| `eval`         | Evaluate existing `pred_results/`                | Provide results directory |
| `run_and_eval` | Run solution and evaluate results               | Provide solution file     |
| `inspect`      | Display task instructions and dataset listing   | Nothing                   |
| `shell`        | Open an interactive shell                       | `-it` flag                |
| `help`         | Show usage information                          | Nothing                   |

---

## Providing Your Solution or Outputs

~~~bash
# Run and evaluate a solution
docker run --rm \
  -v $(pwd)/solution.py:/task/solution.py:ro \
  hananemoussa/d3-gym:task_1 run_and_eval

# Evaluate precomputed results
docker run --rm \
  -v $(pwd)/my_results:/task/pred_results:ro \
  hananemoussa/d3-gym:task_1 eval

# Interactive debugging session
docker run --rm -it hananemoussa/d3-gym:task_1 shell
~~~

---

## Downstream Use Cases

D3-Gym supports workflows that require executable environments with verifiable evaluation signals for data-driven discovery.

One primary use case is generating training trajectories (e.g., reasoning traces and solutions). The trajectories used in our experiments are available on <a href="https://huggingface.co/datasets/hananour/D3-Gym-Trajectories">HuggingFace</a>. 

---

## Cite Our Work

If you find this work useful, please cite our paper:

[Insert placeholder arXiv]
