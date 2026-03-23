from app.services.parsers.detector import detect_tester
from app.services.parsers.acco_parser import parse_acco
from app.services.parsers.ets_parser import parse_ets
from app.services.parsers.base import ParsedData

def parse_file(filepath: str) -> ParsedData:
    """统一入口：detector 识别类型，所有格式走 acco_parser 适配"""
    tester = detect_tester(filepath)
    return parse_acco(filepath, tester)         