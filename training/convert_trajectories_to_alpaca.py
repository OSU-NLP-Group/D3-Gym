#!/usr/bin/env python3
"""
Convert successful trajectory JSONLs to Alpaca format with thinking traces.

This script processes teacher or student trajectory files and creates training data
in Alpaca format suitable for fine-tuning with thinking mode enabled.

The output format includes:
- instruction: The standard system prompt
- input: The task-specific instruction
- output: <think>{reasoning}</think>\n\n{code}
"""

import json
from pathlib import Path
from typing import Dict


SYSTEM_PROMPT_PREFIX = """You are an expert Python programming assistant that helps scientist users to write high-quality code to solve their tasks.
Given a user request, you are expected to write a complete program that accomplishes the requested task and save any outputs in the correct format.
Please wrap your program in a code block that specifies the script type, python. For example:
```python
print("Hello World!")
```"""


def convert_trajectory_to_alpaca(trajectory: Dict) -> Dict:
    """
    Convert a single trajectory to Alpaca format.

    Args:
        trajectory: Dict with keys 'instruction', 'thinking', 'response'

    Returns:
        Dict with keys 'instruction', 'input', 'output'
    """
    full_instruction = trajectory['instruction']

    if full_instruction.startswith(SYSTEM_PROMPT_PREFIX):
        task_input = full_instruction[len(SYSTEM_PROMPT_PREFIX):].strip()
    else:
        lines = full_instruction.split('\n')
        prefix_lines = SYSTEM_PROMPT_PREFIX.split('\n')

        task_start_idx = 0
        for i, line in enumerate(lines):
            if i < len(prefix_lines):
                if line.strip() != prefix_lines[i].strip():
                    task_input = full_instruction
                    break
            else:
                task_start_idx = i
                break
        else:
            task_input = ""

        if task_start_idx > 0:
            task_input = '\n'.join(lines[task_start_idx:]).strip()

    thinking = trajectory.get('thinking', '').strip()
    response = trajectory['response'].strip()

    if thinking:
        output = f"<think>\n{thinking}\n</think>\n\n{response}"
    else:
        output = response

    return {
        "instruction": SYSTEM_PROMPT_PREFIX,
        "input": task_input,
        "output": output
    }


def process_trajectories(input_path: str, output_file: str):
    """
    Process trajectory JSONL file(s) and create Alpaca format dataset.

    Args:
        input_path: Path to a single JSONL file or a folder containing JSONL files
        output_file: Path to output Alpaca JSON file
    """
    input_p = Path(input_path)
    if not input_p.exists():
        print(f"ERROR: Path not found: {input_path}")
        return

    if input_p.is_file():
        jsonl_files = [input_p]
        print(f"Processing single file: {input_path}")
    else:
        jsonl_files = list(input_p.glob("*.jsonl"))
        if not jsonl_files:
            print(f"WARNING: No JSONL files found in {input_path}")
            return
        print(f"Found {len(jsonl_files)} JSONL files in {input_path}")

    alpaca_data = []
    total_trajectories = 0
    skipped_trajectories = 0

    for jsonl_file in sorted(jsonl_files):
        print(f"  Processing {jsonl_file.name}...")

        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    trajectory = json.loads(line)
                    total_trajectories += 1

                    if 'instruction' not in trajectory or 'response' not in trajectory:
                        print(f"    WARNING: Skipping line {line_num} - missing required fields")
                        skipped_trajectories += 1
                        continue

                    alpaca_entry = convert_trajectory_to_alpaca(trajectory)
                    alpaca_data.append(alpaca_entry)

                except json.JSONDecodeError as e:
                    print(f"    ERROR: Failed to parse JSON on line {line_num}: {e}")
                    skipped_trajectories += 1
                except Exception as e:
                    print(f"    ERROR: Failed to process line {line_num}: {e}")
                    skipped_trajectories += 1

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(alpaca_data, f, indent=2, ensure_ascii=False)

    print(f"\nConversion complete!")
    print(f"  Total trajectories processed: {total_trajectories}")
    print(f"  Successfully converted: {len(alpaca_data)}")
    print(f"  Skipped: {skipped_trajectories}")
    print(f"  Output saved to: {output_file}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert trajectory JSONL files to Alpaca format with thinking traces")
    parser.add_argument("--input", type=str, required=True, help="Path to JSONL file or folder of JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Path to output Alpaca JSON file")
    args = parser.parse_args()
    process_trajectories(args.input, args.output)
