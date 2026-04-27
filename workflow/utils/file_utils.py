import base64
import re
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff",
              ".pdf", ".svg", ".eps"}
BINARY_EXTS = {
    ".npy", ".npz", ".pt", ".pth", ".pkl", ".pickle",
    ".h5", ".hdf5", ".parquet", ".mat",
    ".gz", ".zip", ".traj", ".pic", ".model",
}
VISUAL_TEXT_EXTS = {".html"}

MAX_TEXT_CHARS = 20_000


def extract_code(response: str) -> str:
    text = response.strip()
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def load_text(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    data = path.read_text(encoding="utf-8", errors="ignore")
    return data[:max_chars] + "\n...[truncated]..." if len(data) > max_chars else data


def get_preview_files_content(task_folder: Path) -> str:
    parts = []
    for fp in sorted(task_folder.iterdir()):
        if fp.name.endswith("_preview.txt"):
            try:
                parts.append(f"\n--- {fp.name} ---\n{fp.read_text(encoding='utf-8')}\n")
            except Exception as e:
                parts.append(f"\n--- {fp.name} (Error: {e}) ---\n")
    return "".join(parts)


def _is_text_file(filepath: Path, check_bytes: int = 8192) -> bool:
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(check_bytes)
        return b"\x00" not in chunk
    except Exception:
        return False


def _format_gold_file(gold_file: Path, rel_path: str) -> str:
    ext = gold_file.suffix.lower()
    size = gold_file.stat().st_size

    if ext in IMAGE_EXTS:
        return (f"\n--- {rel_path} (image/plot, {size} bytes) ---\n"
                "[Visual output file - use visual judge for comparison]\n")

    if ext in VISUAL_TEXT_EXTS:
        return (f"\n--- {rel_path} (interactive visualization, {size} bytes) ---\n"
                "[HTML visual output - use visual judge for comparison]\n")

    if ext in BINARY_EXTS:
        header = f"\n--- {rel_path} (binary data, {size} bytes) ---\n"
        if ext in {".npy", ".npz"}:
            try:
                import numpy as np
                if ext == ".npy":
                    arr = np.load(gold_file, allow_pickle=False)
                    sample = (f"Values: {arr.tolist()}\n" if arr.size <= 20
                              else f"Sample: {arr.flat[:10].tolist()}...\n")
                    return header + f"NumPy array: shape={arr.shape}, dtype={arr.dtype}\n" + sample
                else:
                    data = np.load(gold_file)
                    return header + f"NumPy archive keys: {list(data.keys())}\n"
            except Exception as e:
                return header + f"[Could not read: {e}]\n"
        return header

    if not _is_text_file(gold_file):
        return f"\n--- {rel_path} (binary data, {size} bytes) ---\n"

    try:
        content = gold_file.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")
        if len(lines) > 100:
            content = "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more lines)"
        if size > 50_000:
            content = content[:50_000] + f"\n... [truncated, {size} bytes total]"
        return f"\n--- {rel_path} ---\n{content}\n"
    except Exception as e:
        return f"\n--- {rel_path} (Error: {e}) ---\n"


def get_gold_results_content(gold_dir: Path, output_fnames: list) -> str:
    if not gold_dir or not gold_dir.exists() or not output_fnames:
        return "(not available)"

    parts = []
    matched_basenames = {Path(fname).name for fname in output_fnames}

    for fname in output_fnames:
        basename = Path(fname).name
        gold_file = gold_dir / basename
        if not gold_file.exists():
            continue
        parts.append(_format_gold_file(gold_file, basename))

    for gold_file in sorted(gold_dir.rglob("*")):
        if not gold_file.is_file():
            continue
        rel = gold_file.relative_to(gold_dir)
        if len(rel.parts) < 2:
            continue
        if rel.name in matched_basenames:
            continue
        parts.append(_format_gold_file(gold_file, str(rel)))

    return "".join(parts) or "(no matching gold result files found)"
