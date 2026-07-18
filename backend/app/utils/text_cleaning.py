"""
text_cleaning.py
────────────────
Limpieza/normalización del texto transcrito para mejorar la legibilidad.

- Colapsa espacios y arregla espacios antes de signos de puntuación.
- Elimina muletillas/titubeos aislados ("eh", "em", "mmm", "este…", etc.).
- Colapsa palabras repetidas consecutivas ("el el gato" → "el gato").
- Capitaliza la primera letra de la frase.

Se aplica en dos niveles:
  - "light"  : para transcripciones parciales (en vivo), evita parpadeos.
  - "full"   : para transcripciones finales y correcciones.
"""

from __future__ import annotations

import re

# Muletillas/titubeos en español (y algunas en inglés) que aportan poco.
_FILLERS = {
    "eh", "ehh", "em", "emm", "ehm", "mmm", "mm", "mmmm",
    "uh", "uhm", "uhh", "hmm", "ah", "ahh", "este", "esto",
    "o sea", "pues", "bueno",
}

_MULTISPACE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_REPEAT_PUNCT = re.compile(r"([,.;:!?])\1{1,}")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _collapse_repeats(text: str) -> str:
    """Colapsa palabras idénticas consecutivas (ignora mayúsculas)."""
    out: list[str] = []
    prev_norm: str | None = None
    for token in text.split(" "):
        norm = token.lower().strip(".,;:!?¿¡")
        if norm and norm == prev_norm:
            continue
        out.append(token)
        if norm:
            prev_norm = norm
    return " ".join(out)


def _remove_fillers(text: str) -> str:
    words = text.split(" ")
    kept = [w for w in words if w.lower().strip(".,;:!?¿¡") not in _FILLERS]
    # No dejar la frase vacía si solo eran muletillas.
    return " ".join(kept) if kept else text


def clean_text(text: str | None, level: str = "full") -> str:
    if not text:
        return ""
    result = text.strip()
    result = _MULTISPACE.sub(" ", result)

    if level == "full":
        result = _remove_fillers(result)
        result = _collapse_repeats(result)

    result = _SPACE_BEFORE_PUNCT.sub(r"\1", result)
    result = _REPEAT_PUNCT.sub(r"\1", result)
    result = _MULTISPACE.sub(" ", result).strip()

    if level == "full" and result:
        # Capitaliza la primera letra sin tocar el resto.
        for i, ch in enumerate(result):
            if ch.isalpha():
                result = result[:i] + ch.upper() + result[i + 1 :]
                break
    return result
