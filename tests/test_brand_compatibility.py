import io
from contextlib import redirect_stderr

import vllm_optimizer
import vtune
from vllm_optimizer.cli import build_parser, legacy_main


def test_canonical_and_legacy_packages_share_public_api() -> None:
    assert vllm_optimizer.__version__ == "0.1.0a20"
    assert vtune.__version__ == vllm_optimizer.__version__
    assert vtune.Orchestrator is vllm_optimizer.Orchestrator


def test_primary_cli_uses_new_command_name() -> None:
    assert build_parser().prog == "vllm-opt"


def test_legacy_cli_warns_and_keeps_old_command_name() -> None:
    errors = io.StringIO()

    with redirect_stderr(errors):
        status = legacy_main(["validate"])

    assert status == 2
    assert build_parser("vtune").prog == "vtune"
    assert "deprecated" in errors.getvalue()
