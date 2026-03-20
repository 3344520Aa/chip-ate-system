from app.services.parsers.detector import detect_tester
from app.services.parsers.acco_parser import parse_acco
from app.services.parsers.ets_parser import parse_ets
from app.services.parsers.base import ParsedData


def parse_file(filepath: str) -> ParsedData:
    """统一入口：自动识别并解析"""
    tester = detect_tester(filepath)

    if tester in ('STS8200', 'STS8300'):
        return parse_acco(filepath, tester)
    elif tester == 'ETS':
        return parse_ets(filepath)
    else:
        result = ParsedData()
        result.error = f"未识别的数据格式: {tester}"
        return result