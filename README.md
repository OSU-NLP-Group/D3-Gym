# D3-Gym

<p align="center">
  <a href="https://arxiv.org/abs/2604.27977">[Paper]</a> &nbsp;
  <a href="https://huggingface.co/collections/osunlp/d3-gym">[HuggingFace]</a> &nbsp;
  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">[Docker Hub]</a>
</p>
<p align="center">
  <img width="1425" height="668" alt="image" src="https://github.com/user-attachments/assets/d4cffe95-74aa-47f3-9d7b-60f1562b3414" />
</p>

D3-Gym is the first automatically constructed dataset of **verifiable environments** for **Data-Driven Discovery**. It contains 565 tasks derived from 239 real-world multi-disciplinary  scientific repositories.  

Each task includes:
- a natural language instruction,
- an executable environment with pre-installed dependencies,
- input datasets and artifact previews,
- a reference implementation,
- and an automatically generated evaluation script.

---

## Using D3-Gym Environments

All task environments are distributed as Docker images via  <a href="https://hub.docker.com/repository/docker/hananemoussa/d3-gym/general">Docker Hub</a>.

Each image is a self-contained unit representing a single data-driven discovery task. It includes the task specification, datasets and previews, reference outputs, and evaluation script, along with pre-installed dependencies.

To solve a task, provide a `solution.py` that:
- reads the provided datasets, and  
- writes outputs to `pred_results/`.

The evaluation script compares your outputs against the reference and returns a pass/fail decision with a short explanation.

For easier browsing, we also provide an annotation sheet with metadata for all tasks on <a href="https://huggingface.co/datasets/osunlp/D3-Gym">HuggingFace</a>.  


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

## Providing Your Solution or Outputs

~~~bash
# Run and evaluate a solution
docker run --rm \
  -v $(pwd)/solution.py:/task/solution.py:ro \
  hananemoussa/d3-gym:task_151 run_and_eval

# Evaluate precomputed results
docker run --rm \
  -v $(pwd)/my_results:/task/pred_results:ro \
  hananemoussa/d3-gym:task_151 eval

# Interactive debugging session
docker run --rm -it hananemoussa/d3-gym:task_151 shell
~~~

---

## Downstream Use Cases

D3-Gym supports workflows that require executable environments with verifiable evaluation signals for data-driven discovery (e.g. reinforcement learning, self-improvement, etc.).

One use case is generating training trajectories (e.g., reasoning traces and solutions). The trajectories used in our experiments are available on <a href="https://huggingface.co/datasets/osunlp/D3-Gym-Trajectories">HuggingFace</a>. 

---

## Disclaimer

Repositories used in the creation of D3-Gym are under permissive licenses. We provide a full breakdown of licenses below. There are also 39 repositories that do not provide any license information; we assume these permit use for research purposes.

### License Distribution

| License                | Count |
|------------------------|-------|
| MIT                    | 99    |
| GNU (GPL, AGPL, LGPL)  | 43    |
| None                   | 39    |
| BSD                    | 29    |
| Apache                 | 22    |
| CC                     | 4     |
| ISC                    | 1     |
| Custom                 | 2     |
| **Total**              | **239** |

### Custom-Licensed Repositories
- BrainIAC  
- DeepDelta

---

## Citation

If you find our paper or resources useful in your work, please cite us:

```bibtex
@article{d3gym2026,
  title   = {D3-Gym: Constructing Verifiable Environments for Data-Driven Discovery},
  author  = {Hanane Nour Moussa, Yifei Li, Zhuoyang Li, Yankai Yang, Cheng Tang, Tianshu Zhang, Nesreen K. Ahmed, Ali Payani, Ziru Chen, Huan Sun},
  journal = {arXiv preprint arXiv:2604.27977},
  year    = {2026},
  url     = {https://arxiv.org/abs/2604.27977}
}
