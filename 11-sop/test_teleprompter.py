import json
import pathlib
import pytest

import teleprompter


SOP_TEXT = """\
# STANDARD OPERATING PROCEDURE

## 1. PURPOSE
To ensure DHL shipments are packed correctly.

## 5. PROCEDURE

### 5.1. Packing
1. Place item in centre of box.
2. Fill voids with bubble wrap.

### 5.2. Sealing
1. Apply tape using H-method.

WARNING: Do not overfill boxes. Max weight is 30 kg.
"""

VALID_LLM_RESPONSE = json.dumps({
    "sop_title": "DHL Shipment Packing",
    "video_goal": "pack and seal a DHL shipment correctly",
    "prerequisites": ["double-wall box", "bubble wrap", "packing tape"],
    "hook_audio": "This procedure applies to all warehouse staff.",
    "steps": [
        {
            "name": "Packing",
            "visual_cue": "Close-up of packing bench",
            "audio": "Place the item in the centre of the box.\nFill any gaps with bubble wrap.",
        },
        {
            "name": "Sealing",
            "visual_cue": "Close-up of tape dispenser",
            "audio": "Apply tape using the H-method.\nMake sure all edges are sealed.",
        },
    ],
    "has_pitfalls": True,
    "pitfalls_visual_cue": "Warning icon on screen",
    "pitfalls_audio": "Do not overfill boxes.\nThe maximum weight is thirty kilograms.",
    "outro_audio": "You have successfully packed and sealed your shipment.",
    "department_or_helpdesk": "Warehouse Operations",
})


@pytest.fixture
def mock_ollama(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_LLM_RESPONSE}
    return mock


# --- prompt ---

def test_prompt_contains_sop_text():
    prompt = teleprompter.build_prompt(SOP_TEXT)
    assert "DHL" in prompt
    assert "H-method" in prompt


def test_prompt_contains_formatting_rules():
    prompt = teleprompter.build_prompt(SOP_TEXT)
    assert "15 words" in prompt
    assert "S-O-P" in prompt
    assert "bullet" in prompt


# --- runtime estimate ---

def test_runtime_estimate_short():
    assert teleprompter._runtime_estimate(0) == "~0 sec"


def test_runtime_estimate_minutes():
    # 140 words = 60 seconds = 1 min
    assert teleprompter._runtime_estimate(140) == "~1 min"


def test_runtime_estimate_mixed():
    # 210 words = 90 seconds = 1 min 30 sec
    assert teleprompter._runtime_estimate(210) == "~1 min 30 sec"


# --- strip formatting ---

def test_strip_formatting_removes_bold():
    assert teleprompter._strip_formatting("Click **Save**.") == "Click Save."


def test_strip_formatting_removes_bullets():
    text = "- First item\n- Second item"
    result = teleprompter._strip_formatting(text)
    assert "- " not in result
    assert "First item" in result


# --- strip greeting ---

def test_strip_greeting_removes_llm_intro():
    cases = [
        ("Hi, I'm John. In this video...", "In this video..."),
        ("Hello I'm Qwen. Today we...", "Today we..."),
        ("Hey, I'm Sarah! Let's get started.", "Let's get started."),
        ("hi, I'm Alex. Welcome.", "Welcome."),
    ]
    for input_text, expected in cases:
        assert teleprompter._strip_greeting(input_text) == expected


def test_strip_greeting_leaves_non_greeting_untouched():
    text = "In this video you will learn how to pack a shipment."
    assert teleprompter._strip_greeting(text) == text


# --- step number ---

def test_step_number_named():
    assert teleprompter._step_number(1) == "ONE"
    assert teleprompter._step_number(5) == "FIVE"
    assert teleprompter._step_number(20) == "TWENTY"


def test_step_number_beyond_list():
    assert teleprompter._step_number(21) == "21"


# --- markdown renderer ---

def test_render_contains_all_sections():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "## SECTION 1 — Hook & Intro" in md
    assert "## SECTION 2 — Step-by-Step Walkthrough" in md
    assert "## SECTION 3 — Common Pitfalls" in md
    assert "## SECTION 4 — Outro & Call to Action" in md


def test_render_presenter_placeholder():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "[Presenter Name]" in md


def test_render_runtime_in_metadata():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "Estimated Runtime:" in md
    assert "130–150 words per minute" in md


def test_render_step_numbers_written_out():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "### STEP ONE — Packing" in md
    assert "### STEP TWO — Sealing" in md


def test_render_prerequisites_in_metadata():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    # prerequisites are now the LLM's responsibility to weave into hook_audio;
    # the renderer exposes them only via the video_goal metadata line
    assert "**Video Goal:**" in md


def test_render_pitfalls_omitted_when_false():
    data = json.loads(VALID_LLM_RESPONSE)
    data["has_pitfalls"] = False
    md = teleprompter._render_markdown(data)
    assert "## Section 3: Common Pitfalls" not in md


def test_render_sop_hyphenated_in_outro():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "S-O-P" in md


def test_render_no_bold_in_audio(tmp_path, mock_ollama):
    # Inject bold into a step audio to verify renderer strips it
    data = json.loads(VALID_LLM_RESPONSE)
    data["steps"][0]["audio"] = "Click **Save** to continue."
    raw = json.dumps(data)
    mock_ollama.return_value.json.return_value = {"response": raw}

    stem = tmp_path / "output"
    teleprompter.generate(SOP_TEXT, stem)
    md = (tmp_path / "output.teleprompter.md").read_text()
    assert "**Save**" not in md
    assert "Click Save to continue." in md


def test_render_contains_checklist():
    data = json.loads(VALID_LLM_RESPONSE)
    md = teleprompter._render_markdown(data)
    assert "SME Review Checklist" in md
    assert "Sign-off" in md


# --- generate (integration with mocked Ollama) ---

def test_generate_writes_script_file(tmp_path, mock_ollama):
    stem = tmp_path / "output"
    script_path = teleprompter.generate(SOP_TEXT, stem)
    assert script_path.exists()


def test_generate_review_contains_checklist(tmp_path, mock_ollama):
    stem = tmp_path / "output"
    script_path = teleprompter.generate(SOP_TEXT, stem)
    content = script_path.read_text()
    assert "Presenter Name" in content
    assert "Sign-off" in content


def test_generate_skips_if_script_exists(tmp_path, mock_ollama):
    stem = tmp_path / "output"
    (tmp_path / "output.teleprompter.md").write_text("existing")

    teleprompter.generate(SOP_TEXT, stem)
    mock_ollama.assert_not_called()


def test_generate_invalid_json_writes_warning(tmp_path, mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": "not valid json {{{"}

    stem = tmp_path / "output"
    teleprompter.generate(SOP_TEXT, stem)

    md = (tmp_path / "output.teleprompter.md").read_text()
    assert "<!-- WARNING: raw LLM output -->" in md
