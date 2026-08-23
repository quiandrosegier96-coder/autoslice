"""Ordered parser registry; specific parsers should be registered before core."""

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.parsers.base import ThreeMFParser


class ParserRegistry:
    def __init__(self, parsers: tuple[ThreeMFParser, ...] = ()) -> None:
        self._parsers = list(parsers)

    def register(self, parser: ThreeMFParser) -> None:
        self._parsers.append(parser)

    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        candidates = [(parser.can_parse(container).confidence, parser) for parser in self._parsers]
        if not candidates:
            raise ValueError("No 3MF parsers are registered.")
        confidence, parser = max(candidates, key=lambda item: item[0])
        if confidence <= 0:
            raise ValueError("No registered parser recognizes this 3MF package.")
        return parser.parse(container)


def default_parser_registry() -> ParserRegistry:
    from app.threemf.parsers.anycubic import AnycubicParser
    from app.threemf.parsers.bambu import BambuParser
    from app.threemf.parsers.core import CoreThreeMFParser
    from app.threemf.parsers.cura import CuraParser
    from app.threemf.parsers.orca import OrcaParser
    from app.threemf.parsers.prusa import PrusaParser

    return ParserRegistry((AnycubicParser(), OrcaParser(), PrusaParser(), CuraParser(), BambuParser(), CoreThreeMFParser()))
