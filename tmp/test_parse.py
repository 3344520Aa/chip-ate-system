import sys
sys.path.insert(0, '/home/swoller/chip_ai_system/backend')

from app.services.parsers import parse_file

# 测试ACCO
print("=== 测试 STS8200 ===")
r1 = parse_file('/tmp/ate_test/8200-1-KED1823-09_2026-1-22_6_38_46.csv')
if r1.error:
    print(f"错误: {r1.error}")
else:
    print(f"Tester: {r1.tester}")
    print(f"Test Stage: {r1.test_stage}")
    print(f"Program: {r1.program}")
    print(f"LOT_ID: {r1.lot_id}")
    print(f"Wafer_ID: {r1.wafer_id}")
    print(f"Handler: {r1.handler}")
    print(f"Beginning: {r1.beginning_time}")
    print(f"Bin定义数量: {len(r1.bin_definitions)}")
    print(f"参数数量: {len(r1.param_names)}")
    print(f"数据行数: {len(r1.data)}")
    print(f"数据列: {list(r1.data.columns[:8])}")
    print(f"前3行:\n{r1.data.head(3)}")

print()
print("=== 测试 ETS ===")
r2 = parse_file('/tmp/ate_test/HL5099_WLCSP_V1P8_4X_SKD1476_W01_ETS172206_04132022.csv')
if r2.error:
    print(f"错误: {r2.error}")
else:
    print(f"Tester: {r2.tester}")
    print(f"Test Stage: {r2.test_stage}")
    print(f"Program: {r2.program}")
    print(f"LOT_ID: {r2.lot_id}")
    print(f"Wafer_ID: {r2.wafer_id}")
    print(f"Handler: {r2.handler}")
    print(f"参数数量: {len(r2.param_names)}")
    print(f"数据行数: {len(r2.data)}")
    print(f"数据列: {list(r2.data.columns[:8])}")
    print(f"前3行:\n{r2.data.head(3)}")