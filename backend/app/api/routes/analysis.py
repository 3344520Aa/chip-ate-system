from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
import pandas as pd
import numpy as np
from app.core.database import get_db
from app.models.test_item import TestItem
from app.models.bin_summary import BinSummary
from app.models.lot import Lot

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/lot/{lot_id}/info")
def get_lot_info(lot_id: int, db: Session = Depends(get_db)):
    """获取LOT基本信息"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="LOT不存在")
    return {
        "id": lot.id,
        "filename": lot.filename,
        "program": lot.program,
        "lot_id": lot.lot_id,
        "wafer_id": lot.wafer_id,
        "test_machine": lot.test_machine,
        "handler": lot.handler,
        "data_type": lot.data_type,
        "station_count": lot.station_count,
        "die_count": lot.die_count,
        "pass_count": lot.pass_count,
        "fail_count": lot.fail_count,
        "yield_rate": lot.yield_rate,
        "test_date": lot.test_date,
        "upload_date": lot.upload_date,
    }


@router.get("/lot/{lot_id}/items")
def get_test_items(
    lot_id: int,
    db: Session = Depends(get_db),
    site: int = Query(0),
):
    """获取参数列表（用于参数详情页表格）"""
    items = db.query(TestItem).filter(
        and_(TestItem.lot_id == lot_id, TestItem.site == site)
    ).order_by(TestItem.item_number).all()

    return [
        {
            "id": item.id,
            "item_number": item.item_number,
            "item_name": item.item_name,
            "unit": item.unit,
            "lower_limit": item.lower_limit,
            "upper_limit": item.upper_limit,
            "exec_qty": item.exec_qty,
            "fail_count": item.fail_count,
            "fail_rate": item.fail_rate,
            "yield_rate": item.yield_rate,
            "mean": item.mean,
            "stdev": item.stdev,
            "min_val": item.min_val,
            "max_val": item.max_val,
            "cpu": item.cpu,
            "cpl": item.cpl,
            "cpk": item.cpk,
        }
        for item in items
    ]


@router.get("/lot/{lot_id}/top_fail")
def get_top_fail(
    lot_id: int,
    db: Session = Depends(get_db),
    top_n: int = Query(5),
):
    """获取Top Fail参数（用于右上角柱状图）"""
    # All Sites 的失效数据
    items = db.query(TestItem).filter(
        and_(
            TestItem.lot_id == lot_id,
            TestItem.site == 0,
            TestItem.fail_count > 0
        )
    ).order_by(TestItem.fail_count.desc()).limit(top_n).all()

    # 各Site的Top Fail
    sites = db.query(TestItem.site).filter(
        and_(TestItem.lot_id == lot_id, TestItem.site > 0)
    ).distinct().all()
    site_list = sorted([s[0] for s in sites])

    result = []
    for item in items:
        row = {
            "item_name": item.item_name,
            "fail_count": item.fail_count,
            "fail_rate": item.fail_rate,
            "sites": {}
        }
        # 查各Site的失效数
        for site in site_list:
            site_item = db.query(TestItem).filter(
                and_(
                    TestItem.lot_id == lot_id,
                    TestItem.item_name == item.item_name,
                    TestItem.site == site
                )
            ).first()
            if site_item:
                row["sites"][f"site{site}"] = site_item.fail_count
        result.append(row)

    return {"items": result, "sites": site_list}

@router.get("/lot/{lot_id}/bin_definitions")
def get_bin_definitions(lot_id: int, db: Session = Depends(get_db)):
    """获取Bin定义和Pass Bins"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="LOT不存在")

    bins = db.query(BinSummary).filter(
        and_(BinSummary.lot_id == lot_id, BinSummary.site == 0)
    ).all()

    # 读取Parquet获取bin定义
    if not lot.parquet_path:
        return {"pass_bins": [1, 2]}

    import pandas as pd
    try:
        df = pd.read_parquet(lot.parquet_path)
        all_bins = df['SOFT_BIN'].dropna().unique().astype(int).tolist()
    except Exception:
        all_bins = []

    # 暂时用bin汇总里数量最多的bin作为pass bin判断依据
    # 实际应从parsed.bin_definitions里读hard_bin=1的
    pass_bins = [1, 2]
    return {"pass_bins": pass_bins, "all_bins": all_bins}

@router.get("/lot/{lot_id}/wafer_bin_map")
def get_wafer_bin_map(
    lot_id: int,
    data_range: str = Query("final"),
    sites: str = Query("all"),
    db: Session = Depends(get_db)
):
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot or not lot.parquet_path:
        raise HTTPException(status_code=404, detail="数据不存在")

    import pandas as pd
    df = pd.read_parquet(lot.parquet_path)

    if 'X_COORD' not in df.columns or 'Y_COORD' not in df.columns:
        return {"data": [], "has_map": False}

    df = df.dropna(subset=['X_COORD', 'Y_COORD', 'SOFT_BIN'])

    # Site过滤
    if sites != 'all':
        site_list = [int(s) for s in sites.split(',')]
        df = df[df['SITE_NUM'].isin(site_list)]

    # 找复测坐标
    coord_counts = df.groupby(['X_COORD', 'Y_COORD']).size()
    retest_coords = set(
        f"{int(x)},{int(y)}"
        for (x, y), cnt in coord_counts.items()
        if cnt > 1
    )

    # 按data_range去重
    if data_range == 'final':
        df = df.drop_duplicates(subset=['X_COORD', 'Y_COORD'], keep='last')
    elif data_range == 'original':
        df = df.drop_duplicates(subset=['X_COORD', 'Y_COORD'], keep='first')

    result = []
    for _, row in df.iterrows():
        x = int(row['X_COORD'])
        y = int(row['Y_COORD'])
        result.append({
            "x": x,
            "y": y,
            "bin": int(row['SOFT_BIN']),
            "retest": f"{x},{y}" in retest_coords
        })

    return {"data": result, "has_map": True}


@router.get("/lot/{lot_id}/bin_summary")
def get_bin_summary(
    lot_id: int,
    data_range: str = Query("final"),
    sites: str = Query("all"),
    db: Session = Depends(get_db),
):
    """获取Bin汇总数据"""
    query = db.query(BinSummary).filter(
        and_(
            BinSummary.lot_id == lot_id,
            BinSummary.site == 0,
            BinSummary.data_range == data_range
        )
    ).order_by(BinSummary.count.desc())

    bins_all = query.all()

    # 获取所有site列表
    all_sites_query = db.query(BinSummary.site).filter(
        and_(
            BinSummary.lot_id == lot_id,
            BinSummary.site > 0,
            BinSummary.data_range == data_range
        )
    ).distinct().all()
    all_site_list = sorted([s[0] for s in all_sites_query])

    # 按sites参数过滤
    if sites != 'all':
        site_filter = [int(s) for s in sites.split(',')]
    else:
        site_filter = all_site_list

    result = []
    for b in bins_all:
        row = {
            "bin_number": b.bin_number,
            "bin_name": b.bin_name,
            "all_site_count": b.count,
            "all_site_pct": b.percentage,
            "sites": {}
        }
        for site in site_filter:
            site_bin = db.query(BinSummary).filter(
                and_(
                    BinSummary.lot_id == lot_id,
                    BinSummary.bin_number == b.bin_number,
                    BinSummary.site == site,
                    BinSummary.data_range == data_range
                )
            ).first()
            if site_bin:
                row["sites"][f"site{site}"] = {
                    "count": site_bin.count,
                    "pct": site_bin.percentage
                }
        result.append(row)

    return {"bins": result, "sites": site_filter, "all_sites": all_site_list}


@router.get("/lot/{lot_id}/retest_analysis")
def get_retest_analysis(
    lot_id: int,
    sites: str = Query("all"),
    db: Session = Depends(get_db),
):
    """复测分析：Bin转移情况"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot or not lot.parquet_path:
        raise HTTPException(status_code=404, detail="数据不存在")

    import pandas as pd
    df = pd.read_parquet(lot.parquet_path)

    if 'X_COORD' not in df.columns or 'Y_COORD' not in df.columns:
        return {"has_retest": False, "details": [], "summary": []}

    df = df.dropna(subset=['X_COORD', 'Y_COORD', 'SOFT_BIN'])

    # Site过滤
    if sites != 'all':
        site_list = [int(s) for s in sites.split(',')]
        df = df[df['SITE_NUM'].isin(site_list)]

    # 找复测坐标（出现超过一次）
    coord_groups = df.groupby(['X_COORD', 'Y_COORD'])
    retest_details = []

    for (x, y), group in coord_groups:
        if len(group) < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]

        first_bin = int(first['SOFT_BIN'])
        last_bin = int(last['SOFT_BIN'])
        first_site = int(first['SITE_NUM'])
        last_site = int(last['SITE_NUM'])

        # 获取bin名称
        bin_defs: dict = {}
        if hasattr(lot, '_bin_defs'):
            bin_defs = lot._bin_defs

        retest_details.append({
            "x": int(x),
            "y": int(y),
            "first_site": first_site,
            "first_bin": first_bin,
            "last_site": last_site,
            "last_bin": last_bin,
            "site_changed": first_site != last_site,
            "retest_count": len(group) - 1,
        })

    if not retest_details:
        return {"has_retest": False, "details": [], "summary": [], "totals": {}}

    # 获取pass bins
    bin_defs_data = db.query(BinSummary).filter(
        and_(BinSummary.lot_id == lot_id, BinSummary.site == 0,
             BinSummary.data_range == 'final')
    ).all()

    # 用数量最多的bin判断pass（临时逻辑，后续可从bin定义读）
    pass_bins_query = db.query(BinSummary).filter(
        and_(BinSummary.lot_id == lot_id, BinSummary.site == 0,
             BinSummary.data_range == 'final')
    ).all()

    from app.api.routes.analysis import _get_pass_bins
    pass_bins = _get_pass_bins(lot_id, db)

    def get_direction(fb, lb):
        fb_pass = fb in pass_bins
        lb_pass = lb in pass_bins
        if fb_pass and lb_pass:
            return "pass_pass"
        elif not fb_pass and lb_pass:
            return "fail_pass"
        elif fb_pass and not lb_pass:
            return "pass_fail"
        else:
            return "fail_fail"

    # 转移汇总：按 first_bin → last_bin 分组统计
    from collections import defaultdict
    transfer_counts = defaultdict(int)
    for d in retest_details:
        key = (d['first_bin'], d['last_bin'])
        transfer_counts[key] += 1

    summary = []
    for (fb, lb), cnt in sorted(transfer_counts.items(), key=lambda x: (-x[1], x[0][0])):
        summary.append({
            "from_bin": fb,
            "to_bin": lb,
            "count": cnt,
            "direction": get_direction(fb, lb),
            "no_change": fb == lb,
        })

    # 总计统计
    directions = [get_direction(d['first_bin'], d['last_bin']) for d in retest_details]
    totals = {
        "total_retest_dies": len(retest_details),
        "fail_to_pass": directions.count("fail_pass"),
        "pass_to_fail": directions.count("pass_fail"),
        "fail_to_fail": directions.count("fail_fail"),
        "pass_to_pass": directions.count("pass_pass"),
    }

    return {
        "has_retest": True,
        "details": retest_details[:500],  # 最多返回500条明细
        "summary": summary,
        "totals": totals,
    }


def _get_pass_bins(lot_id: int, db) -> list:
    """从bin_summary推断pass bins"""
    from app.models.bin_summary import BinSummary
    from sqlalchemy import and_
    bins = db.query(BinSummary).filter(
        and_(BinSummary.lot_id == lot_id,
             BinSummary.site == 0,
             BinSummary.data_range == 'final')
    ).order_by(BinSummary.count.desc()).all()
    if not bins:
        return [1, 2]
    # 数量最多的bin通常是pass bin，取占比超过50%的
    total = sum(b.count for b in bins)
    pass_bins = [b.bin_number for b in bins if b.count / total > 0.3]
    return pass_bins if pass_bins else [bins[0].bin_number]


@router.get("/lot/{lot_id}/param_data")
def get_param_data(
    lot_id: int,
    param_name: str = Query(...),
    filter_type: str = Query("all"),
    sigma: float = Query(3.0),
    sites: str = Query("all"),
    data_range: str = Query("final"),
    db: Session = Depends(get_db),
):
    """
    获取单个参数的原始数据（用于直方图/Scatter/WaferMap）
    filter_type: all / robust / filter_by_limit / filter_by_sigma
    sites: all 或 逗号分隔的site编号 如 "1,2"
    data_range: final / original / all
    """
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot or not lot.parquet_path:
        raise HTTPException(status_code=404, detail="数据文件不存在")

    # 读取Parquet
    try:
        df = pd.read_parquet(lot.parquet_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取数据失败: {e}")

    if param_name not in df.columns:
        raise HTTPException(status_code=404, detail=f"参数 {param_name} 不存在")

    # 坐标去重
    if 'X_COORD' in df.columns and 'Y_COORD' in df.columns:
        if data_range == 'final':
            df = df.drop_duplicates(subset=['X_COORD', 'Y_COORD'], keep='last')
        elif data_range == 'original':
            df = df.drop_duplicates(subset=['X_COORD', 'Y_COORD'], keep='first')

    # Site筛选
    if sites != 'all':
        site_list = [int(s) for s in sites.split(',')]
        df = df[df['SITE_NUM'].isin(site_list)]

    # 获取参数的limit
    item = db.query(TestItem).filter(
        and_(
            TestItem.lot_id == lot_id,
            TestItem.item_name == param_name,
            TestItem.site == 0
        )
    ).first()
    ll = item.lower_limit if item else None
    ul = item.upper_limit if item else None
    unit = item.unit if item else ''

    # 应用Filter
    from app.services.stats import apply_filter

    result_data = []

    # 先计算 All Sites (site=0)
    all_values = df[param_name].dropna().values.astype(float)
    filtered_all = apply_filter(all_values, filter_type, ll, ul, sigma)
    from app.services.stats import calc_param_stats
    all_stats = calc_param_stats(filtered_all, ll, ul, len(filtered_all))

    result_data.append({
        "site": 0,
        "histogram": {"counts": [], "edges": []},
        "scatter": [],
        "wafer_map": [],
        "stats": all_stats,
    })

    # 再按 Site 分组
    site_groups = df.groupby('SITE_NUM')



    for site_num, site_df in site_groups:
        values = site_df[param_name].dropna().values.astype(float)
        filtered = apply_filter(values, filter_type, ll, ul, sigma)

        # Scatter数据：测试序号+值
        scatter = []
        for idx, row in site_df.iterrows():
            val = row[param_name]
            if pd.notna(val):
                scatter.append({
                    "idx": int(idx),
                    "val": float(val)
                })

        # WaferMap数据
        wafer_map = []
        if 'X_COORD' in site_df.columns:
            for _, row in site_df.iterrows():
                if pd.notna(row[param_name]) and pd.notna(row.get('X_COORD')) and pd.notna(row.get('Y_COORD')):
                    wafer_map.append({
                        "x": int(row['X_COORD']),
                        "y": int(row['Y_COORD']),
                        "val": float(row[param_name])
                    })

        # 直方图数据：分箱
        if len(filtered) > 0:
            hist, bin_edges = np.histogram(filtered, bins=50)
            histogram = {
                "counts": hist.tolist(),
                "edges": [round(float(e), 6) for e in bin_edges.tolist()]
            }
        else:
            histogram = {"counts": [], "edges": []}

        # 统计数据
        from app.services.stats import calc_param_stats
        stats = calc_param_stats(filtered, ll, ul, len(filtered))

        result_data.append({
            "site": int(site_num),
            "histogram": histogram,
            "scatter": scatter,
            "wafer_map": wafer_map,
            "stats": stats,
        })

    return {
        "param_name": param_name,
        "unit": unit,
        "lower_limit": ll,
        "upper_limit": ul,
        "filter_type": filter_type,
        "data_range": data_range,
        "sites": result_data,
    }