"""
Final project implementation.
"""
import re
import sys
from pathlib import Path

from lab_6_pipeline.pipeline import UDPipeAnalyzer

PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main(corpus_path: Path, dist_path: Path) -> None:
    """
    Generate conllu file for provided corpus of texts.

    Args:
        corpus_path (Path): Path to folder containing text files.
        dist_path (Path): Path to folder for saving auto_annotated.conllu.
    """
    if not corpus_path.exists() or not corpus_path.is_dir():
        raise FileNotFoundError(f"Corpus directory does not exist: {corpus_path}")

    txt_files = sorted(corpus_path.glob("*.txt"))
    if not txt_files:
        raise ValueError(f"No .txt files found in {corpus_path}")

    texts = [f.read_text(encoding="utf-8") for f in txt_files]

    analyzer = UDPipeAnalyzer()
    raw_result = analyzer.analyze(texts)

    if isinstance(raw_result, list):
        conllu = "\n\n".join(raw_result)
    else:
        conllu = str(raw_result)

    if not conllu.strip():
        raise ValueError("UDPipe analysis returned empty result")

    new_lines = []
    sent_counter = 1
    for line in conllu.splitlines():
        if line.startswith("# sent_id ="):
            new_lines.append(f"# sent_id = {sent_counter}")
            sent_counter += 1
        else:
            new_lines.append(line)
    conllu = "\n".join(new_lines)

    conllu = re.sub(r'\n{3,}', '\n\n', conllu)
    conllu = conllu.rstrip() + '\n\n'

    dist_path.mkdir(exist_ok=True, parents=True)
    (dist_path / "auto_annotated.conllu").write_text(conllu, encoding="utf-8")


if __name__ == "__main__":
    main(Path(__file__).parent / "assets" / "articles", Path(__file__).parent / "dist")
