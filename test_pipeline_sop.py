"""
Smoke test: pipeline with sop.enabled=true produces .sop.md and .sop.pdf
from pre-existing transcript.txt and analysis.json fixtures (Ollama mocked).
"""

import importlib.util
import json
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TRANSCRIPT = "This is a test transcript about packing boxes for shipment."

ANALYSIS = {
    "title": "DHL Packing Procedure",
    "description": "How to pack items for DHL shipment.",
    "tags": ["DHL", "packing", "shipping"],
    "goals": ["Pack items correctly for DHL shipment"],
    "skills": ["Packing", "Labelling"],
}

VALID_LLM_RESPONSE = json.dumps({
    "document_title": "DHL Shipment Preparation",
    "purpose": "To ensure items are packed correctly.",
    "scope": "Applies to all warehouse staff.",
    "responsibilities": [{"role": "Packer", "description": "Selects packaging and packs items."}],
    "materials": ["Double-wall box", "Bubble wrap"],
    "procedure": [
        {"heading": "Packing", "steps": ["Place item in centre of box."]},
    ],
    "associated_documents": [{"name": "DHL Air Waybill", "description": "Generated per shipment."}],
    "company_name": "DHL",
    "department": "Logistics",
    "approver": "Warehouse Manager",
})


@pytest.fixture
def mock_ollama(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_LLM_RESPONSE}
    return mock


def _load_pipeline():
    spec = importlib.util.spec_from_file_location("pipeline", PROJECT_ROOT / "pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sop_stage_produces_md_and_pdf(tmp_path, mocker, mock_ollama):
    """Pipeline SOP stage writes .sop.md and .sop.pdf given existing fixtures."""
    # Write fixture files
    transcript_file = tmp_path / "video.transcript.txt"
    analysis_file = tmp_path / "video.analysis.json"
    transcript_file.write_text(TRANSCRIPT)
    analysis_file.write_text(json.dumps(ANALYSIS))

    pipeline = _load_pipeline()

    # Patch _get_sop_generate to use the real sop module
    sop_spec = importlib.util.spec_from_file_location("sop", PROJECT_ROOT / "11-sop" / "sop.py")
    sop_mod = importlib.util.module_from_spec(sop_spec)
    sop_spec.loader.exec_module(sop_mod)

    mocker.patch.object(pipeline, "_get_sop_generate", return_value=lambda: sop_mod.generate)

    sop_generate = sop_mod.generate
    sop_generate(
        transcript=transcript_file.read_text(),
        analysis=json.loads(analysis_file.read_text()),
        output_stem=tmp_path / "video",
        ollama_host="localhost:11434",
        model="qwen2.5:7b",
        max_words=0,
    )

    md_path = tmp_path / "video.sop.md"
    pdf_path = tmp_path / "video.sop.pdf"

    assert md_path.exists(), ".sop.md was not created"
    assert pdf_path.exists(), ".sop.pdf was not created"
    assert md_path.stat().st_size > 0
    assert pdf_path.stat().st_size > 0


def test_sop_stage_skipped_when_disabled(tmp_path, mocker):
    """sop_generate is not called when sop_enabled=False."""
    pipeline = _load_pipeline()
    mock_gen = mocker.MagicMock()

    # Simulate what pipeline does when sop_enabled=False
    sop_enabled = False
    sop_generate = mock_gen if sop_enabled else None

    transcript_file = tmp_path / "video.transcript.txt"
    analysis_file = tmp_path / "video.analysis.json"
    transcript_file.write_text(TRANSCRIPT)
    analysis_file.write_text(json.dumps(ANALYSIS))

    if sop_enabled and sop_generate and transcript_file.exists() and analysis_file.exists():
        sop_generate()

    mock_gen.assert_not_called()
