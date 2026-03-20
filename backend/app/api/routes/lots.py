import os
import shutil
import zipfile
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.config import settings
from app.models.lot import Lot
from app.schemas.lot import LotResponse, LotListResponse
from datetime import datetime, timedelta, timezone
from app.services.parsers import parse_file

router = APIRouter(prefix="/lots", tags=["lots"])

UPLOAD_DIR = os.path.expanduser("~/chip_ai_system/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    results = []
    for file in files:
        try:
            result = await _process_upload(file, db)
            results.append(result)
        except Exception as e:
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})
    return {"results": results}


async def _process_upload(file: UploadFile, db: Session):
    filename = file.filename
    ext = os.path.splitext(filename)[-1].lower()
    base_name = os.path.splitext(filename)[0]

    # 重复文件名处理：自动追加数字
    save_path = os.path.join(UPLOAD_DIR, filename)
    counter = 1
    while os.path.exists(save_path):
        new_filename = f"{base_name}_{counter}{ext}"
        save_path = os.path.join(UPLOAD_DIR, new_filename)
        counter += 1
    filename = os.path.basename(save_path)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_size = len(content)

    # 如果是zip，解压找csv
    csv_path = save_path
    if ext == '.zip':
        extract_dir = os.path.join(UPLOAD_DIR, os.path.splitext(filename)[0])
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(save_path, 'r') as z:
            z.extractall(extract_dir)
        # 找第一个csv文件
        csv_files = [
            os.path.join(extract_dir, f)
            for f in os.listdir(extract_dir)
            if f.endswith('.csv')
        ]
        if not csv_files:
            raise HTTPException(status_code=400, detail="ZIP中未找到CSV文件")
        csv_path = csv_files[0]

    # 快速识别tester类型，提取基本元数据
    from app.services.parsers.detector import detect_tester
    tester = detect_tester(csv_path)

    # 创建LOT记录（先存pending状态）
    lot = Lot(
        filename=filename,
        storage_path=save_path,
        file_size=file_size,
        status='pending',
        data_source='manual',
        storage_type='local',
        local_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        upload_date=datetime.now(timezone.utc),
        test_machine=tester,
    )

    # 快速解析表头获取基本信息
    try:
        meta = _quick_parse_meta(csv_path, tester)
        lot.program = meta.get('program')
        lot.lot_id = meta.get('lot_id')
        lot.wafer_id = meta.get('wafer_id')
        lot.handler = meta.get('handler')
        lot.data_type = meta.get('test_stage')
        if meta.get('beginning_time'):
            try:
                lot.test_date = datetime.strptime(
                    meta['beginning_time'], '%Y-%m-%d %H:%M:%S'
                )
            except Exception:
                pass
    except Exception:
        pass

    db.add(lot)
    db.commit()
    db.refresh(lot)

    # 触发异步解析任务（暂时同步处理）
    try:
        _parse_and_save(lot.id, csv_path, db)
    except Exception as e:
        lot.status = 'failed'
        db.commit()

    return {
        "filename": filename,
        "status": lot.status,
        "lot_id": lot.id
    }


def _quick_parse_meta(csv_path: str, tester: str) -> dict:
    """快速读取表头元数据，不解析数据部分"""
    from app.services.parsers.acco_parser import parse_acco
    from app.services.parsers.ets_parser import parse_ets

    if tester in ('STS8200', 'STS8300'):
        result = parse_acco(csv_path, tester)
    elif tester == 'ETS':
        result = parse_ets(csv_path)
    else:
        return {}

    return {
        'program': result.program,
        'lot_id': result.lot_id,
        'wafer_id': result.wafer_id,
        'handler': result.handler,
        'test_stage': result.test_stage,
        'beginning_time': result.beginning_time,
        'ending_time': result.ending_time,
    }

def _parse_and_save(lot_id: int, csv_path: str, db: Session):
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        return

    lot.status = 'processing'
    db.commit()

    try:
        result = parse_file(csv_path)
        print(f"[parse] 解析完成 error={result.error}")

        if result.error:
            raise Exception(result.error)

        # 保存Parquet
        parquet_dir = os.path.join(UPLOAD_DIR, 'parquet')
        os.makedirs(parquet_dir, exist_ok=True)
        parquet_path = os.path.join(parquet_dir, f"lot_{lot_id}.parquet")
        result.data.to_parquet(parquet_path, index=False)
        print(f"[parse] Parquet保存完成 {parquet_path}")

        lot.parquet_path = parquet_path
        lot.die_count = len(result.data)
        lot.station_count = int(result.data['SITE_NUM'].nunique())

        pass_bins = [
            k for k, v in result.bin_definitions.items()
            if v.get('hard_bin') == 1
        ] if result.bin_definitions else [1]

        lot.pass_count = int(result.data['SOFT_BIN'].isin(pass_bins).sum())
        lot.fail_count = lot.die_count - lot.pass_count
        lot.yield_rate = lot.pass_count / lot.die_count if lot.die_count > 0 else 0
        print(f"[parse] 良率计算完成 yield={lot.yield_rate}")

        if lot.program:
            from app.models.product_mapping import ProductMapping
            from app.api.routes.products import extract_program_prefix
            prefix = extract_program_prefix(lot.program)
            if prefix:
                mapping = db.query(ProductMapping).filter(
                    ProductMapping.program_prefix == prefix
                ).first()
                if mapping:
                    lot.product_name = mapping.product_name

        from app.services.stats import save_stats_to_db
        save_stats_to_db(lot.id, result, db, data_range='final')
        print(f"[parse] 统计计算完成")

        lot.status = 'processed'
        lot.finish_date = datetime.now(timezone.utc)
        db.commit()
        print(f"[parse] 全部完成 lot_id={lot_id}")

    except Exception as e:
        import traceback
        print(f"[parse] 错误: {e}")
        traceback.print_exc()
        lot.status = 'failed'
        db.commit()



@router.get("", response_model=LotListResponse)
def get_lots(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    product_name: Optional[str] = None,
    lot_id: Optional[str] = None,
    status: Optional[str] = None,
    data_type: Optional[str] = None,
):
    query = db.query(Lot)
    if product_name:
        query = query.filter(Lot.product_name.ilike(f"%{product_name}%"))
    if lot_id:
        query = query.filter(Lot.lot_id.ilike(f"%{lot_id}%"))
    if status:
        query = query.filter(Lot.status == status)
    if data_type:
        query = query.filter(Lot.data_type == data_type)

    total = query.count()
    items = query.order_by(desc(Lot.upload_date)).offset(
        (page-1)*page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "items": items,
        "page": page,
        "page_size": page_size
    }


@router.delete("")
def delete_lots(data: dict, db: Session = Depends(get_db)):
    ids = data.get("ids", [])
    for lot_id in ids:
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if lot:
            # 删除文件
            if lot.storage_path and os.path.exists(lot.storage_path):
                try:
                    os.remove(lot.storage_path)
                except Exception:
                    pass
            if lot.parquet_path and os.path.exists(lot.parquet_path):
                try:
                    os.remove(lot.parquet_path)
                except Exception:
                    pass
            db.delete(lot)
    db.commit()
    return {"deleted": len(ids)}