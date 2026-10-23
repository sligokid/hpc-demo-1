import json
import pathlib
import pytest
import yaml

import sop


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
    "responsibilities": [
        {"role": "Packer", "description": "Selects packaging and packs items."},
    ],
    "materials": ["Double-wall box", "Bubble wrap", "Packing tape"],
    "procedure": [
        {
            "heading": "Packing",
            "steps": ["Place item in centre of box.", "Fill voids with bubble wrap."],
        },
        {
            "heading": "Sealing",
            "steps": ["Apply tape using H-method."],
        },
    ],
    "associated_documents": [
        {"name": "DHL Air Waybill", "description": "Generated per shipment."},
    ],
})


@pytest.fixture
def config_file(tmp_path):
    cfg = {
        "company_name": "Test Corp",
        "department": "Logistics",
        "approver": "Jane Smith",
    }
    path = tmp_path / "sop_config.yaml"
    path.write_text(yaml.dump(cfg))
    return path


@pytest.fixture
def mock_ollama(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_LLM_RESPONSE}
    return mock


# --- prompt construction ---

def test_prompt_contains_transcript():
    template = (pathlib.Path(__file__).parent / "sop_template.md").read_text()
    prompt = sop.build_prompt(TRANSCRIPT, ANALYSIS, template)
    assert TRANSCRIPT in prompt


def test_prompt_contains_analysis_title():
    template = (pathlib.Path(__file__).parent / "sop_template.md").read_text()
    prompt = sop.build_prompt(TRANSCRIPT, ANALYSIS, template)
    assert "DHL Packing Procedure" in prompt


def test_prompt_contains_goals():
    template = (pathlib.Path(__file__).parent / "sop_template.md").read_text()
    prompt = sop.build_prompt(TRANSCRIPT, ANALYSIS, template)
    assert "Pack items correctly for DHL shipment" in prompt


def test_prompt_contains_template():
    template = (pathlib.Path(__file__).parent / "sop_template.md").read_text()
    prompt = sop.build_prompt(TRANSCRIPT, ANALYSIS, template)
    assert "## 5. PROCEDURE" in prompt


# --- truncation ---

def test_prompt_truncates_when_max_words_set():
    long = " ".join([f"word{i}" for i in range(5000)])
    template = ""
    prompt = sop.build_prompt(long, ANALYSIS, template, max_words=100)
    assert "[transcript truncated]" in prompt


def test_prompt_no_truncation_when_max_words_zero():
    long = " ".join([f"word{i}" for i in range(5000)])
    template = ""
    prompt = sop.build_prompt(long, ANALYSIS, template, max_words=0)
    assert "[transcript truncated]" not in prompt
    assert "word4999" in prompt


# --- markdown output ---

def test_markdown_contains_all_section_headings(tmp_path, config_file, mock_ollama):
    stem = tmp_path / "output"
    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    md = (tmp_path / "output.sop.md").read_text()
    for heading in ["## 1. PURPOSE", "## 2. SCOPE", "## 3. RESPONSIBILITIES",
                    "## 4. MATERIALS", "## 5. PROCEDURE",
                    "## 6. ASSOCIATED DOCUMENTS", "## 7. REVISION HISTORY"]:
        assert heading in md


def test_markdown_contains_org_fields(tmp_path, config_file, mock_ollama):
    stem = tmp_path / "output"
    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    md = (tmp_path / "output.sop.md").read_text()
    assert "Test Corp" in md
    assert "Jane Smith" in md
    assert "[Insert Document Number]" in md


def test_markdown_contains_llm_content(tmp_path, config_file, mock_ollama):
    stem = tmp_path / "output"
    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    md = (tmp_path / "output.sop.md").read_text()
    assert "To ensure items are packed correctly." in md
    assert "Applies to all warehouse staff." in md
    assert "Double-wall box" in md
    assert "### 5.1. Packing" in md
    assert "### 5.2. Sealing" in md


# --- skip if done ---

def test_skip_if_both_files_exist(tmp_path, config_file, mock_ollama):
    stem = tmp_path / "output"
    (tmp_path / "output.sop.md").write_text("existing md")
    (tmp_path / "output.sop.pdf").write_bytes(b"existing pdf")

    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    mock_ollama.assert_not_called()


def test_does_not_skip_if_only_md_exists(tmp_path, config_file, mock_ollama):
    stem = tmp_path / "output"
    (tmp_path / "output.sop.md").write_text("existing md")

    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    mock_ollama.assert_called_once()


# --- invalid JSON response ---

def test_invalid_json_writes_warning_header(tmp_path, config_file, mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": "not valid json {{{"}

    stem = tmp_path / "output"
    sop.generate(TRANSCRIPT, ANALYSIS, stem, config_file)

    md = (tmp_path / "output.sop.md").read_text()
    assert "<!-- WARNING: raw LLM output -->" in md
    assert "not valid json {{{" in md


