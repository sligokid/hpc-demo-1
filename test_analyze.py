import io
import json
import pytest
import requests

import analyze


TRANSCRIPT = "This is a test transcript about Python programming."

VALID_RESPONSE = json.dumps({
    "title": "Python Programming",
    "description": "An introduction to Python.",
    "tags": ["python", "programming"],
    "goals": ["Write a Python script"],
    "skills": ["Python"],
})


# --- prompt construction ---

def test_prompt_contains_transcript():
    prompt = analyze.build_prompt(TRANSCRIPT)
    assert TRANSCRIPT in prompt


def test_prompt_describes_all_five_fields():
    prompt = analyze.build_prompt(TRANSCRIPT)
    for field in ("title", "description", "tags", "goals", "skills"):
        assert field in prompt


# --- happy path ---

def test_happy_path_via_main(tmp_path, capsys, mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_RESPONSE}

    transcript_file = tmp_path / "t.txt"
    transcript_file.write_text(TRANSCRIPT)

    import sys
    sys.argv = ["analyze.py", "--transcript", str(transcript_file), "--model", "llama3"]
    analyze.main()

    out = capsys.readouterr().out
    data = json.loads(out)
    assert set(data.keys()) == {"title", "description", "tags", "goals", "skills"}


# --- --model flag ---

def test_model_flag_sent_in_request(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_RESPONSE}

    analyze.analyze(TRANSCRIPT, "mistral")

    _, kwargs = mock.call_args
    assert kwargs["json"]["model"] == "mistral"


# --- stdin path ---

def test_stdin_path(capsys, mocker, monkeypatch):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": VALID_RESPONSE}

    monkeypatch.setattr("sys.stdin", io.StringIO(TRANSCRIPT))

    import sys
    sys.argv = ["analyze.py", "--transcript", "-", "--model", "llama3"]
    analyze.main()

    out = capsys.readouterr().out
    data = json.loads(out)
    assert set(data.keys()) == {"title", "description", "tags", "goals", "skills"}


# --- error paths ---

def test_empty_transcript_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        analyze.analyze("   ", "llama3")
    assert exc.value.code == 1
    assert "empty" in capsys.readouterr().err


def test_connection_error_exits_1(capsys, mocker):
    mocker.patch("requests.post", side_effect=requests.exceptions.ConnectionError)
    with pytest.raises(SystemExit) as exc:
        analyze.analyze(TRANSCRIPT, "llama3")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ollama serve" in err


def test_http_error_exits_1(capsys, mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = False
    mock.return_value.status_code = 500
    mock.return_value.text = "Internal Server Error"

    with pytest.raises(SystemExit) as exc:
        analyze.analyze(TRANSCRIPT, "llama3")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "500" in err


def test_invalid_json_response_exits_1(capsys, mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.json.return_value = {"response": "not valid json {{{"}

    with pytest.raises(SystemExit) as exc:
        analyze.analyze(TRANSCRIPT, "llama3")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not valid json {{{" in err
