from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import httpx2
import pytest

from mesbah.export.__main__ import main, modelfile
from mesbah.export.contract import ExportConfig, ExportContractError, ExportStatus
from mesbah.export.converter import ConverterUnavailable, converter

if TYPE_CHECKING:
    from torch import Tensor

TINY: str = "trl-internal-testing/tiny-Qwen3ForCausalLM"


def config(tmp_path: Path, **fields: object) -> ExportConfig:
    values: dict[str, object] = {
        "kind": "gguf",
        "base_path": str(tmp_path / "base"),
        "output_dir": str(tmp_path / "out"),
        "status_path": str(tmp_path / "status.json"),
        "tools_dir": str(tmp_path / "tools"),
        **fields,
    }
    return ExportConfig.from_json(values)


def test_the_config_round_trips(tmp_path: Path) -> None:
    written: ExportConfig = config(tmp_path, adapter_path="/a", out_type="q8_0", name="polite")
    written.write(tmp_path / "config.json")

    assert ExportConfig.read(tmp_path / "config.json") == written


def test_a_bad_kind_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ExportContractError):
        config(tmp_path, kind="onnx")


def test_the_modelfile_names_the_gguf_and_the_prompt(tmp_path: Path) -> None:
    text: str = modelfile(config(tmp_path, system_prompt="Answer in Arabic."))

    assert text.splitlines() == ["FROM ./model.gguf", 'SYSTEM """Answer in Arabic."""']


def test_a_tampered_converter_is_refused(tmp_path: Path) -> None:
    def tampered(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"print('not llama.cpp')")

    with (
        httpx2.Client(transport=httpx2.MockTransport(tampered)) as client,
        pytest.raises(ConverterUnavailable, match="pinned digest"),
    ):
        converter(tmp_path, client)
    assert not (tmp_path / "llama.cpp-b9000" / "convert_hf_to_gguf.py").exists()


def test_a_config_that_cannot_be_read_fails_cleanly(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{")

    assert main(["--config", str(tmp_path / "config.json")]) == 1


@pytest.mark.ml
def test_merging_gives_the_same_model_as_peft(tmp_path: Path) -> None:
    torch: ModuleType = pytest.importorskip("torch")
    from huggingface_hub import snapshot_download
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM

    from mesbah.export.merge import merge

    base: Path = Path(snapshot_download(TINY))
    torch.manual_seed(0)
    model: PeftModel = get_peft_model(
        AutoModelForCausalLM.from_pretrained(base), LoraConfig(r=4, target_modules="all-linear")
    )
    for name, parameter in model.named_parameters():
        if "lora_B" in name:
            torch.nn.init.normal_(parameter, std=0.5)
    model.save_pretrained(tmp_path / "adapter")
    tokens: Tensor = torch.tensor([[1, 2, 3, 4, 5]])
    expected: Tensor = (
        PeftModel.from_pretrained(
            AutoModelForCausalLM.from_pretrained(base, dtype="auto"), tmp_path / "adapter"
        )
        .merge_and_unload()(tokens)
        .logits
    )

    merged: Path = merge(base, tmp_path / "adapter", tmp_path / "merged")

    actual: Tensor = AutoModelForCausalLM.from_pretrained(merged, dtype="auto")(tokens).logits
    assert actual.dtype == expected.dtype
    assert torch.allclose(actual, expected)
    assert (merged / "tokenizer.json").exists()


@pytest.mark.ml
def test_a_version_becomes_a_gguf_file(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from huggingface_hub import snapshot_download

    base: Path = Path(snapshot_download(TINY))
    written: ExportConfig = config(tmp_path, base_path=str(base), system_prompt="Be brief.")
    written.write(tmp_path / "config.json")
    try:
        converter(Path(written.tools_dir))
    except ConverterUnavailable as error:
        pytest.skip(f"llama.cpp's converter cannot be fetched here: {error}")

    exit_code: int = main(["--config", str(tmp_path / "config.json")])

    status: ExportStatus = ExportStatus.read(tmp_path / "status.json")
    assert exit_code == 0, status.error_detail
    assert status.output is not None and status.output.endswith("model.gguf")
    sys.path.insert(0, str(tmp_path / "tools" / "llama.cpp-b9000" / "gguf-py"))
    os.environ.pop("NO_LOCAL_GGUF", None)
    from gguf import GGUFReader

    reader: GGUFReader = GGUFReader(status.output)
    assert len(reader.tensors) > 0
    assert (tmp_path / "out" / "Modelfile").read_text().startswith("FROM ./model.gguf")
