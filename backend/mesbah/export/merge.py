from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from transformers import PreTrainedModel

TOKENIZER_FILES: tuple[str, ...] = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "merges.txt",
    "tokenizer.model",
    "chat_template.jinja",
    "generation_config.json",
)
SHARD_SIZE: str = "2GB"


def merge(base: Path, adapter: Path, output: Path) -> Path:
    from peft import PeftModel
    from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM

    config: object = AutoConfig.from_pretrained(base)
    seq2seq: bool = bool(getattr(config, "is_encoder_decoder", False))
    # The checkpoint's own dtype: a merged export is the same size as the model it came from.
    dtype: str = "auto"
    model: PreTrainedModel = (
        AutoModelForSeq2SeqLM.from_pretrained(base, dtype=dtype, low_cpu_mem_usage=True)
        if seq2seq
        else AutoModelForCausalLM.from_pretrained(base, dtype=dtype, low_cpu_mem_usage=True)
    )
    merged: PreTrainedModel = cast(
        "PreTrainedModel", PeftModel.from_pretrained(model, adapter).merge_and_unload()
    )
    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True, max_shard_size=SHARD_SIZE)
    for name in TOKENIZER_FILES:
        if (base / name).is_file():
            shutil.copy2(base / name, output / name)
    return output
