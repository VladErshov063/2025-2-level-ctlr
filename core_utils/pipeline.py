"""
Interface definitions for text processing pipelines.
"""

# pylint: disable=too-few-public-methods, unused-argument
from dataclasses import dataclass
from typing import Protocol

from spacy import Language
from spacy.tokens import Doc

from core_utils.article.article import Article


class PipelineProtocol(Protocol):
    """
    Interface definition for pipeline.
    """

    def run(self) -> None:
        """
        Key API method.
        """


class LibraryWrapper(Protocol):
    """
    Interface definition for text analyzers.
    """

    _analyzer: Language

    def _bootstrap(self) -> Language:
        """
        Bootstrap analyzer with required models and settings.

        Returns:
            Language: Instance of analyzer.
        """

    def analyze(self, texts: list[str]) -> list[str]:
        """
        Analyze given texts.

        Args:
            texts (list[str]): Texts to analyze.

        Returns:
            list[str]: Collection of processed documents.
        """

    def to_conllu(self, article: Article) -> None:
        """
        Write ConLLU content to a file.

        Args:
            article (Article): Article to save
        """

    def from_conllu(self, article: Article) -> Doc:
        """
        Load ConLLU content from article stored on disk.

        Args:
            article (Article): Article to load

        Returns:
            Doc: Document ready for parsing
        """


@dataclass
class TreeNode:
    """
    Interface definition for node in the graph.
    """

    upos: str
    text: str
    children: list["TreeNode"]
