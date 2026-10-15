"""Merge Prime-RL's portable dense-linear LoRA export, one HF shard at a time."""
import hashlib
import json
from pathlib import Path
import shutil


def checkpoint_files(path):
    path = Path(path).resolve(strict=True)
    config = json.loads((path / "config.json").read_text())
    if config.get("quantization_config"):
        raise ValueError("GRPO expects a merged BF16/FP16 checkpoint, not packed quantized weights")
    if (path / "adapter_config.json").exists():
        raise ValueError("Merge the OPSD adapter with its base before starting GRPO")
    index = path / "model.safetensors.index.json"
    names = sorted(set(json.loads(index.read_text())["weight_map"].values())) if index.exists() else ["model.safetensors"]
    for name in names:
        relative = Path(name)
        # HF cache snapshots legitimately symlink shards into ../blobs.
        if relative.is_absolute() or ".." in relative.parts or not (path / relative).is_file():
            raise ValueError("Invalid checkpoint shard path")
    if not (path / "tokenizer_config.json").is_file():
        raise ValueError("Checkpoint needs its OPSD tokenizer and chat template")
    return path, names


def merge_checkpoint(base, adapter, output):
    """Use safetensors + torch; no full model materialization or new model library.

    This portable merge adds the trained adapter to the original dense base.
    As with a conventional QLoRA merge, inference is BF16 rather than NF4.
    """
    import torch
    from safetensors.torch import load_file, save_file

    base, shards = checkpoint_files(base)
    adapter, output = Path(adapter).resolve(strict=True), Path(output).resolve()
    config = json.loads((adapter / "adapter_config.json").read_text())
    if (config.get("peft_type") != "LORA" or config.get("modules_to_save")
            or config.get("bias", "none") != "none" or config.get("use_dora")
            or config.get("use_rslora") or config.get("fan_in_fan_out")
            or config.get("rank_pattern") or config.get("alpha_pattern")):
        raise ValueError("Only the OPSD dense-linear LoRA adapter format is supported")
    rank, alpha = config["r"], config["lora_alpha"]
    if rank <= 0 or alpha <= 0:
        raise ValueError("Invalid adapter rank/alpha")
    weights_path = adapter / "adapter_model.safetensors"
    tensors = load_file(weights_path, device="cpu")
    pairs = {}
    for key, tensor in tensors.items():
        key = key.removeprefix("base_model.model.")
        for kind in ("A", "B"):
            suffix = f".lora_{kind}.weight"
            if key.endswith(suffix):
                pairs.setdefault(key.removesuffix(suffix) + ".weight", {})[kind] = tensor
                break
        else:
            raise ValueError(f"Unexpected adapter key: {key}")
    if not pairs or any(set(pair) != {"A", "B"} for pair in pairs.values()):
        raise ValueError("Adapter contains incomplete LoRA pairs")
    output.mkdir(parents=True, exist_ok=False)
    used = set()
    # An incomplete export never has config.json; launch validation rejects it.
    for name in shards:
        weights = load_file(base / name, device="cpu")
        for key in weights.keys() & pairs.keys():
            a, b = pairs[key]["A"], pairs[key]["B"]
            weight = weights[key]
            if a.ndim != 2 or b.ndim != 2 or a.shape[0] != rank or b.shape[1] != rank:
                raise ValueError(f"Invalid LoRA shape: {key}")
            if weight.shape != (b.shape[0], a.shape[1]):
                raise ValueError(f"Base/adapter shape mismatch: {key}")
            merged = weight.float() + (b.float() @ a.float()) * (alpha / rank)
            if not torch.isfinite(merged).all():
                raise ValueError(f"Nonfinite merged weight: {key}")
            weights[key] = merged.to(weight.dtype).contiguous()
            used.add(key)
        save_file(weights, output / name, metadata={"format": "pt"})
        del weights
    if used != pairs.keys():
        raise ValueError(f"Adapter targets absent from base: {sorted(pairs.keys() - used)}")
    for file in base.iterdir():
        if file.is_file() and file.name != "config.json" and (
                file.suffix in {".json", ".jinja", ".model", ".txt", ".tiktoken"}):
            shutil.copyfile(file, output / file.name)
    provenance = dict(phase="opsd", base=str(base), adapter=str(adapter),
        adapter_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),
        merge="dense base + alpha/r * B@A; BF16/FP16 portable QLoRA export")
    (output / "opsd_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    shutil.copyfile(base / "config.json", output / "config.json")

