import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from litellm import model_cost

logger = logging.getLogger(__name__)


class CostTracker:

    def __init__(self, model_name: str, step_name: str = "unknown"):
        self.step_name = step_name
        self.litellm_model_name = model_name
        self._lock = threading.Lock()
        self._total_cost = 0.0
        self._details: list[dict] = []

        if model_name in model_cost:
            self._cost_info = model_cost[model_name]
            logger.info(f"Cost tracking enabled for model: {model_name}")
        else:
            self._cost_info = None
            logger.warning(f"Model '{model_name}' not in litellm model_cost.")

    def track(self, prompt_tokens: int, completion_tokens: int,
              task_name: str = None) -> float:
        if self._cost_info is None:
            return 0.0
        cost = (
            self._cost_info["input_cost_per_token"] * prompt_tokens
            + self._cost_info["output_cost_per_token"] * completion_tokens
        )
        with self._lock:
            self._total_cost += cost
            self._details.append({
                "task": task_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "timestamp": datetime.now().isoformat(),
            })
        return cost

    def save_report(self, output_path: Path):
        logs_dir = output_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report = {
            "step": self.step_name,
            "litellm_model_name": self.litellm_model_name,
            "total_cost_usd": self._total_cost,
            "total_calls": len(self._details),
            "total_prompt_tokens": sum(d["prompt_tokens"] for d in self._details),
            "total_completion_tokens": sum(d["completion_tokens"] for d in self._details),
            "timestamp": datetime.now().isoformat(),
            "details": self._details,
        }
        cost_file = logs_dir / f"cost_{ts}.json"
        with open(cost_file, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(
            f"Cost report: {cost_file}  "
            f"(${self._total_cost:.6f} for {len(self._details)} calls)"
        )
