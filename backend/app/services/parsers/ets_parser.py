import re
import os
import pandas as pd
from app.services.parsers.base import ParsedData


def parse_ets(filepath: str) -> ParsedData:
    """解析 ETS 格式数据"""
    result = ParsedData(tester='ETS')

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            raw_lines = f.readlines()
    except Exception as e:
        result.error = f"文件读取失败: {e}"
        return result

    # ── 第一步：解析表头 ────────────────────────────────────
    header_row_idx = None

    for i, line in enumerate(raw_lines[:300]):
        cols = [c.strip() for c in line.split(',')]

        # Program：包含 .pgs 的行
        if '.pgs' in line.lower() and i < 30:
            for col in cols:
                if '.pgs' in col.lower():
                    parts = col.replace('\\', '/').split('/')
                    fname = parts[-1].strip()
                    result.program = fname
                    break

        # LOT_ID
        if 'Datalog for Lot Number' in line:
            result.lot_id = cols[1].strip() if len(cols) > 1 else ''

        # WAFER_ID
        if 'Datalog for SubLot Number' in line:
            result.wafer_id = cols[1].strip() if len(cols) > 1 else ''

        # Handler
        if 'Handler/Prober ID' in line:
            handler_raw = cols[1].strip() if len(cols) > 1 else ''
            result.handler = re.sub(r'\.dll$', '', handler_raw, flags=re.IGNORECASE)
       
        # Program：包含 .pgs 的行，ETS备用取Test Name第二列
        if cols[0] == 'Data Sheet File' :
            if len(cols) > 1 and cols[1].strip():
               # result.program = cols[1].strip()
                parts = cols[1].strip().split('\\')
                fname = parts[-1].strip() if parts else stripped
                result.program = fname


        # Header行：找 "Test Name"
        if cols[0] == 'Test Number':
            header_row_idx = i - 1  # Test Name 行
            #test_number_row_idx = i
            break

    if header_row_idx is None:
        result.error = "未找到 Test Name 行"
        return result

    # ── 第二步：解析参数行 ─────────────────────────────────
    header_line = [c.strip() for c in raw_lines[header_row_idx].split(',')]     # Test Name行
    ll_line     = [c.strip() for c in raw_lines[header_row_idx + 2].split(',')]  # Lower Limit
    ul_line     = [c.strip() for c in raw_lines[header_row_idx + 3].split(',')]  # Upper Limit
    unit_line   = [c.strip() for c in raw_lines[header_row_idx + 4].split(',')]  # Units
    coord_line  = [c.strip() for c in raw_lines[header_row_idx + 5].split(',')]  # Site#/Bin/XCoord/YCoord

    # 数据从 header_row_idx + 5 开始
    data_start_row = header_row_idx + 5

    # 从 header+5 行找关键列
    site_col = next((i for i, h in enumerate(coord_line) if 'site' in h.lower()), None)
    bin_col = next((i for i, h in enumerate(coord_line) if h.lower() == 'bin'), None)
    x_col = next((i for i, h in enumerate(coord_line) if 'xcoord' in h.lower()), None)
    y_col = next((i for i, h in enumerate(coord_line) if 'ycoord' in h.lower()), None)
    # Serial# 直接丢弃

    if site_col is None or bin_col is None:
        result.error = "未找到 Site 或 Bin 列"
        return result

    # 数据起始列
    data_start_col = max(filter(None, [site_col, bin_col, x_col, y_col])) + 1

    # 提取参数名、单位、上下限（从header_line）
    for i in range(data_start_col, len(header_line)):
        pname = header_line[i].strip()
        if not pname:
            continue
        result.param_names.append(pname)
        result.param_units[pname] = unit_line[i] if i < len(unit_line) else ''
        try:
            result.param_ll[pname] = float(ll_line[i]) if i < len(ll_line) and ll_line[i] else None
        except ValueError:
            result.param_ll[pname] = None
        try:
            result.param_ul[pname] = float(ul_line[i]) if i < len(ul_line) and ul_line[i] else None
        except ValueError:
            result.param_ul[pname] = None

    # ── 第三步：找数据起始行（Test Number行之后跳过空行）──────
    data_start_row = header_row_idx + 5
    while data_start_row < len(raw_lines):
        line = raw_lines[data_start_row].strip()
        cols_check = line.split(',')
        first_val = cols_check[site_col].strip() if site_col < len(cols_check) else ''
        if first_val.lstrip('-').isdigit():
            break
        data_start_row += 1

    # ── 第四步：读取数据 ────────────────────────────────────
    try:
        df = pd.read_csv(
            filepath,
            skiprows=data_start_row,
            header=None,
            on_bad_lines='skip',
            dtype=str,
            encoding='utf-8',
            encoding_errors='ignore'
        )
    except Exception as e:
        result.error = f"数据读取失败: {e}"
        return result

    # 重命名关键列
    rename_map = {}
    if site_col is not None:
        rename_map[site_col] = 'SITE_NUM'
    if bin_col is not None:
        rename_map[bin_col] = 'SOFT_BIN'
    if x_col is not None:
        rename_map[x_col] = 'X_COORD'
    if y_col is not None:
        rename_map[y_col] = 'Y_COORD'

    # 给参数列命名
    for i in range(data_start_col, len(header_line)):
        if i < df.shape[1]:
            pname = header_line[i].strip()
            if pname:
                rename_map[i] = pname

    df = df.rename(columns=rename_map)

    # 确保统一列存在
    for col in ['SITE_NUM', 'SOFT_BIN', 'X_COORD', 'Y_COORD']:
        if col not in df.columns:
            df[col] = None

    # 转换数值类型
    for col in ['SITE_NUM', 'SOFT_BIN', 'X_COORD', 'Y_COORD']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    for pname in result.param_names:
        if pname in df.columns:
            df[pname] = pd.to_numeric(df[pname], errors='coerce')

    df = df.dropna(subset=['SITE_NUM'])
    df = df.reset_index(drop=True)

    has_coords = x_col is not None and df['X_COORD'].notna().any()

    from app.services.parsers.detector import detect_test_stage
    result.test_stage = detect_test_stage(os.path.basename(filepath), has_coords)

    final_cols = ['SITE_NUM', 'SOFT_BIN']
    if has_coords:
        final_cols += ['X_COORD', 'Y_COORD']
    final_cols += [p for p in result.param_names if p in df.columns]
    result.data = df[final_cols]

    return result