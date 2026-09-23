"""Agent promptlari: hammasi xatosiz to'ldiriladi va JSON sxema kalitlarini o'z ichiga oladi."""
from __future__ import annotations

import json
import re

import pytest

from engine.agents import prompt_loader

ALL_KW = {
    "brand_profile": {"name": "Neta", "pronoun": "siz"},
    "taste": ["RAD: juda uzun"],
    "references": [{"t": "0-3", "role": "hook", "text": "Nega ...?"}],
    "plan_item": {"aida": "attention"},
    "brief": "15% chegirma",
    "script": {"hooks": ["a", "b", "c"]},
    "previous_reviews": "yo'q",
    "address_form": '"siz"',
    "allowed_loanwords": "skidka",
}

SCHEMA_KEYS = {
    "writer": ["hooks", "body", "cta", "tts_text", "display_text", "scenes", "img_prompt",
               "duration_s", "subtitle"],
    "uz_critic": ["score", "reasons", "fixes"],
    "brand_critic": ["score", "reasons", "fixes"],
    "hook_critic": ["score", "best_hook_idx", "reasons", "fixes"],
    "vision_qa": ["pass", "issues", "frame", "issue"],
}
RUBRIC_POINTS = {
    "uz_critic": ["3 ball", "2 ball", "1 ball"],
    "brand_critic": ["4 ball", "3 ball"],
    "hook_critic": ["4 ball", "3 ball"],
}


@pytest.mark.parametrize("name", sorted(SCHEMA_KEYS))
def test_prompt_renders_and_has_schema(name):
    text = prompt_loader.render(name, **ALL_KW)
    leftover = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", text))
    assert not leftover, f"{name}: to'ldirilmagan joy-belgilar {leftover}"
    # oxirgi JSON sxema qatori — yaroqli JSON va kerakli kalitlar bilan
    schema_line = [ln for ln in text.splitlines() if ln.startswith("{")][-1]
    schema = json.loads(schema_line)
    flat = json.dumps(schema)
    for key in SCHEMA_KEYS[name]:
        assert f'"{key}"' in flat, f"{name}: {key} yo'q"
    for pts in RUBRIC_POINTS.get(name, []):
        assert pts in text
    assert text.splitlines()[0].startswith("# Rol:")


def test_placeholders_are_known():
    known = set(ALL_KW)
    for name in SCHEMA_KEYS:
        assert prompt_loader.placeholders(name) <= known, name


def test_render_missing_keys_and_stray_braces_do_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", tmp_path)
    prompt_loader.load.cache_clear()
    (tmp_path / "t.md").write_text('A {x} B {missing} C {"k": [1, {}]} D { } E {0} }{',
                                   encoding="utf-8")
    try:
        out = prompt_loader.render("t", x={"a": "ʻ"})
    finally:
        prompt_loader.load.cache_clear()
    assert out.startswith('A {\n "a": "ʻ"\n} B {missing} C {"k": [1, {}]} D { } E {0} }{')


def test_empty_values_render_as_dash():
    text = prompt_loader.render("writer", taste=[], references=None, brief="")
    assert "Ega didi" in text and "—" in text


def test_writer_previous_reviews_placeholder_present():
    assert "previous_reviews" in prompt_loader.placeholders("writer")
    assert "brief" in prompt_loader.placeholders("writer")
