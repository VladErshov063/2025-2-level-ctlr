"""
Pipeline for CONLL-U formatting.
"""

# pylint: disable=too-few-public-methods, unused-import, undefined-variable, too-many-nested-blocks, duplicate-code
from __future__ import annotations

import pathlib
import re
import sys
from typing import cast

from core_utils.article.article import Article, ArtifactType
from core_utils.article.io import from_raw, to_cleaned, to_meta
from core_utils.constants import ASSETS_PATH
from core_utils.pipeline import LibraryWrapper, PipelineProtocol, TreeNode
from core_utils.visualizer import visualize

try:
    from networkx import DiGraph
    from networkx.algorithms.isomorphism import DiGraphMatcher
except ImportError:
    print("No libraries installed. Failed to import networkx.")
    sys.exit(1)

try:
    import spacy_udpipe
    from spacy.language import Language
    from spacy.tokens import Doc
    from spacy_conll.parser import ConllParser
except ImportError:
    print("No libraries installed. Failed to import spacy.")
    sys.exit(1)


class EmptyDirectoryError(Exception):
    """
    Raised when dataset directory is empty.
    """

class InconsistentDatasetError(Exception):
    """
    Raised when dataset has missing files, gaps, empty files, etc.
    """

class EmptyFileError(Exception):
    """
    Raised when a required file is empty.
    """


class CorpusManager:
    """
    Work with articles and store them.
    """

    def __init__(self, path_to_raw_txt_data: pathlib.Path) -> None:
        """
        Initialize an instance of the CorpusManager class.

        Args:
            path_to_raw_txt_data (pathlib.Path): Path to raw txt data
        """
        self._path = path_to_raw_txt_data
        self._storage: dict[int, Article] = {}
        self._validate_dataset()
        self._scan_dataset()

    def _check_path_exists_and_not_empty(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Path does not exist: {self._path}")
        if not self._path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self._path}")

        try:
            next(self._path.iterdir())
        except StopIteration as exc:
            raise EmptyDirectoryError(f"Directory is empty: {self._path}") from exc

    def _collect_files(self) -> tuple[dict[int, pathlib.Path], dict[int, pathlib.Path]]:
        raw_files = {}
        meta_files = {}
        pattern_raw = re.compile(r'^(\d+)_raw\.txt$')
        pattern_meta = re.compile(r'^(\d+)_meta\.json$')
        for file_path in self._path.iterdir():
            if not file_path.is_file():
                continue
            name = file_path.name
            raw_match = pattern_raw.match(name)
            meta_match = pattern_meta.match(name)
            if raw_match:
                idx = int(raw_match.group(1))
                raw_files[idx] = file_path
            elif meta_match:
                idx = int(meta_match.group(1))
                meta_files[idx] = file_path
        return raw_files, meta_files

    def _validate_file_sets(self, raw_files: dict, meta_files: dict) -> None:
        if set(raw_files.keys()) != set(meta_files.keys()):
            raise InconsistentDatasetError("Mismatch between raw and meta file ids")
        if not raw_files:
            raise InconsistentDatasetError("No valid raw files found")

    def _validate_ids_sequence(self, raw_files: dict) -> None:
        ids = sorted(raw_files.keys())
        expected = list(range(1, max(ids) + 1))
        if ids != expected:
            raise InconsistentDatasetError(f"Article ids are not consecutive: {ids}")

    def _validate_files_non_empty(self, raw_files: dict, meta_files: dict) -> None:
        for idx, path in raw_files.items():
            if path.stat().st_size == 0:
                raise InconsistentDatasetError(f"Raw file {idx} is empty")
        for idx, path in meta_files.items():
            if path.stat().st_size == 0:
                raise InconsistentDatasetError(f"Meta file {idx} is empty")

    def _validate_dataset(self) -> None:
        """
        Validate folder with assets.
        """
        self._check_path_exists_and_not_empty()
        raw_files, meta_files = self._collect_files()
        self._validate_file_sets(raw_files, meta_files)
        self._validate_ids_sequence(raw_files)
        self._validate_files_non_empty(raw_files, meta_files)

    def _scan_dataset(self) -> None:
        """
        Register each dataset entry.
        """
        pattern = re.compile(r'^(\d+)_raw\.txt$')
        for file_path in self._path.iterdir():
            if not file_path.is_file():
                continue
            match = pattern.match(file_path.name)
            if match:
                article = from_raw(file_path)
                self._storage[article.article_id] = article

    def get_articles(self) -> dict:
        """
        Get storage params.

        Returns:
            dict: Storage params
        """
        return self._storage


class TextProcessingPipeline(PipelineProtocol):
    """
    Preprocess and morphologically annotate sentences into the CONLL-U format.
    """

    def __init__(
        self, corpus_manager: CorpusManager, analyzer: LibraryWrapper | None = None
    ) -> None:
        """
        Initialize an instance of the TextProcessingPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper | None, optional): Analyzer instance. Defaults to None.
        """
        self._corpus = corpus_manager
        self._analyzer = analyzer

    def run(self) -> None:
        """
        Perform basic preprocessing and write processed text to files.
        """
        articles = self._corpus.get_articles()
        for article in articles.values():
            raw_text = article.text
            if not raw_text:
                continue

            cleaned_text = raw_text.lower()
            cleaned_text = re.sub(r'[^\w\s]', '', cleaned_text)
            article.text = cleaned_text
            to_cleaned(article)

            if self._analyzer is not None:
                conll_list = self._analyzer.analyze([raw_text])
                if conll_list:
                    article.set_conllu_info(conll_list[0])
                    self._analyzer.to_conllu(article)


class UDPipeAnalyzer(LibraryWrapper):
    """
    Wrapper for udpipe library.
    """

    _analyzer: Language

    def __init__(self) -> None:
        """
        Initialize an instance of the UDPipeAnalyzer class.
        """
        self._analyzer = self._bootstrap()

    def _bootstrap(self) -> Language:
        """
        Load and set up the UDPipe model.

        Returns:
            Language: Analyzer instance
        """
        current_dir = pathlib.Path(__file__).parent
        model_dir = current_dir / "assets" / "model"
        if not model_dir.exists():
            model_dir = pathlib.Path("assets/model")
        model_files = list(model_dir.glob("*.udpipe"))
        if not model_files:
            raise FileNotFoundError("UDPipe model not found in assets/model/")
        model_path = str(model_files[0])

        nlp = spacy_udpipe.load_from_path(lang='ru', path=model_path)
        conll_config = {
        'conversion_maps': {'XPOS': {'': '_'}},
        'include_headers': True,
        'field_names': {
            'ID': 'ID',
            'FORM': 'FORM',
            'LEMMA': 'LEMMA',
            'UPOS': 'UPOS',
            'XPOS': 'XPOS',
            'FEATS': 'FEATS',
            'HEAD': 'HEAD',
            'DEPREL': 'DEPREL',
            'DEPS': 'DEPS',
            'MISC': 'MISC'
            }
        }
        nlp.add_pipe('conll_formatter', last=True, config=conll_config)
        return nlp

    def analyze(self, texts: list[str]) -> list[str]:
        """
        Process texts into CoNLL-U formatted markup.

        Args:
            texts (list[str]): Collection of texts

        Returns:
            list[str]: List of documents
        """
        results = []
        for text in texts:
            doc = self._analyzer(text)
            results.append(doc._.conll_str)
        return results

    def to_conllu(self, article: Article) -> None:
        """
        Save content to ConLLU format.

        Args:
            article (Article): Article containing information to save
        """
        conll_info = article.get_conllu_info()
        if not conll_info:
            return
        article_dir = article.get_file_path(ArtifactType.CLEANED).parent
        conllu_path = article_dir / f"{article.article_id}_udpipe.conllu"
        conllu_path.parent.mkdir(parents=True, exist_ok=True)
        conllu_path.write_text(conll_info + '\n', encoding='utf-8')

    def from_conllu(self, article: Article) -> Doc:
        """
        Load ConLLU content from article stored on disk.

        Args:
            article (Article): Article to load

        Returns:
            Doc: Document ready for parsing
        """
        article_dir = article.get_file_path(ArtifactType.CLEANED).parent
        conllu_path = article_dir / f"{article.article_id}_udpipe.conllu"
        if not conllu_path.exists():
            raise FileNotFoundError(f"CONLL-U file not found: {conllu_path}")
        content = conllu_path.read_text(encoding='utf-8')
        if not content.strip():
            raise EmptyFileError(f"CONLL-U file is empty: {conllu_path}")
        content = content.rstrip() + '\n'
        parser = ConllParser(self._analyzer)
        doc = parser.parse_conll_text_as_spacy(content)
        return cast(Doc, doc)



class POSFrequencyPipeline:
    """
    Count frequencies of each POS in articles, update meta info and produce graphic report.
    """

    def __init__(self, corpus_manager: CorpusManager, analyzer: LibraryWrapper) -> None:
        """
        Initialize an instance of the POSFrequencyPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper): Analyzer instance
        """
        self._corpus = corpus_manager
        self._analyzer = analyzer

    def _count_frequencies(self, article: Article) -> dict[str, int]:
        """
        Count POS frequency in Article.

        Args:
            article (Article): Article instance

        Returns:
            dict[str, int]: POS frequencies
        """
        doc = self._analyzer.from_conllu(article)
        pos_counter = {}
        for token in doc:
            pos = token.pos_
            pos_counter[pos] = pos_counter.get(pos, 0) + 1
        return pos_counter

    def run(self) -> None:
        """
        Visualize the frequencies of each part of speech.
        """
        articles = self._corpus.get_articles()
        for article in articles.values():
            freq_dict = self._count_frequencies(article)
            article.set_pos_info(freq_dict)
            to_meta(article)

            article_dir = article.get_file_path(ArtifactType.CLEANED).parent
            image_path = article_dir / f"{article.article_id}_image.png"
            visualize(article=article, path_to_save=image_path)


class PatternSearchPipeline(PipelineProtocol):
    """
    Search for the required syntactic pattern.
    """

    def __init__(
        self, corpus_manager: CorpusManager, analyzer: LibraryWrapper, pos: tuple[str, ...]
    ) -> None:
        """
        Initialize an instance of the PatternSearchPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper): Analyzer instance
            pos (tuple[str, ...]): Root, Dependency, Child part of speech
        """
        self._corpus = corpus_manager
        self._analyzer = analyzer
        self._node_labels = pos
        self._pattern_graph: DiGraph | None = None

    def _node_to_dict(self, node: TreeNode) -> dict:
        """
        Convert TreeNode to dictionary recursively.
        """
        return {
            'upos': node.upos,
            'text': node.text,
            'children': [self._node_to_dict(child) for child in node.children]
        }

    def _make_graphs(self, doc: Doc) -> list[DiGraph]:
        """
        Make graphs for a document.

        Args:
            doc (Doc): Document for patterns searching

        Returns:
            list[DiGraph]: Graphs for the sentences in the document
        """
        graphs = []
        for sent in doc.sents:
            g = DiGraph()
            for token in sent:
                g.add_node(token.i, label=token.pos_, text=token.text)
            for token in sent:
                if token.dep_ != "ROOT" and token.head.i != token.i:
                    g.add_edge(token.head.i, token.i, label=token.dep_)
            graphs.append(g)
        return graphs

    def _add_children(
        self, graph: DiGraph, subgraph_to_graph: dict, node_id: int, tree_node: TreeNode
    ) -> None:
        """
        Add children to TreeNode.

        Args:
            graph (DiGraph): Sentence graph to search for a pattern
            subgraph_to_graph (dict): Matched subgraph
            node_id (int): ID of root node of the match
            tree_node (TreeNode): Root node of the match
        """
        if self._pattern_graph is None:
            return
        for child_pattern in self._pattern_graph.successors(node_id):
            child_graph_id = subgraph_to_graph[child_pattern]
            child_upos = cast(str, graph.nodes[child_graph_id]['label'])
            child_text = cast(str, graph.nodes[child_graph_id]['text'])
            child_node = TreeNode(upos=child_upos, text=child_text, children=[])
            tree_node.children.append(child_node)
            self._add_children(graph, subgraph_to_graph, child_pattern, child_node)

    def _process_match(
        self,
        sent_graph: DiGraph,
        subgraph_match: dict,
        target_root_pos: str,
        sent_idx: int,
        matches: dict
    ) -> None:
        """
        Process one isomorphism match and add to matches.
        """
        pat_to_graph = {p: g for g, p in subgraph_match.items()}
        root_pattern = None
        for pat_node in pat_to_graph.keys():
            if self._pattern_graph.nodes[pat_node]['label'] == target_root_pos:
                root_pattern = pat_node
                break
        if root_pattern is None:
            return

        root_graph_id = pat_to_graph[root_pattern]
        root_upos = cast(str, sent_graph.nodes[root_graph_id]['label'])
        root_text = cast(str, sent_graph.nodes[root_graph_id]['text'])
        root_node = TreeNode(upos=root_upos, text=root_text, children=[])

        self._add_children(sent_graph, pat_to_graph, root_pattern, root_node)
        matches.setdefault(sent_idx, []).append(root_node)

    def _find_pattern(self, doc_graphs: list) -> dict[int, list[TreeNode]]:
        """
        Search for the required pattern.

        Args:
            doc_graphs (list): A list of graphs for the document

        Returns:
            dict[int, list[TreeNode]]: A dictionary with pattern matches
        """
        self._pattern_graph = DiGraph()
        for i, pos_tag in enumerate(self._node_labels):
            self._pattern_graph.add_node(i, label=pos_tag)
        for i in range(len(self._node_labels) - 1):
            self._pattern_graph.add_edge(i, i + 1)

        matches: dict[int, list[TreeNode]] = {}
        target_root_pos = self._node_labels[0]

        for sent_idx, sent_graph in enumerate(doc_graphs):
            def node_match(node1_attrs: dict, node2_attrs: dict) -> bool:
                return node1_attrs.get('label') == node2_attrs.get('label')

            matcher = DiGraphMatcher(sent_graph, self._pattern_graph, node_match=node_match)

            for subgraph_match in matcher.subgraph_isomorphisms_iter():
                self._process_match(sent_graph, subgraph_match, target_root_pos, sent_idx, matches)

        return matches

    def run(self) -> None:
        """
        Search for a pattern in documents and writes found information to JSON file.
        """
        articles = self._corpus.get_articles()
        for article in articles.values():
            doc = self._analyzer.from_conllu(article)
            graphs = self._make_graphs(doc)
            pattern_dict = self._find_pattern(graphs)

            serialized_patterns = {}
            for sent_idx, tree_nodes in pattern_dict.items():
                serialized_patterns[str(sent_idx)] = [
                    self._node_to_dict(node) for node in tree_nodes
                    ]

            article.set_patterns_info(serialized_patterns)
            to_meta(article)


def main() -> None:
    """
    Entrypoint for pipeline module.
    """
    try:
        corpus_manager = CorpusManager(ASSETS_PATH)
        analyzer = UDPipeAnalyzer()

        text_pipeline = TextProcessingPipeline(corpus_manager, analyzer)
        text_pipeline.run()

        pos_pipeline = POSFrequencyPipeline(corpus_manager, analyzer)
        pos_pipeline.run()

        pattern_pipeline = PatternSearchPipeline(corpus_manager, analyzer, ("VERB", "NOUN", "ADP"))
        pattern_pipeline.run()

    except (FileNotFoundError, NotADirectoryError, EmptyDirectoryError,
            InconsistentDatasetError, EmptyFileError) as e:
        print(f"Pipeline error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
