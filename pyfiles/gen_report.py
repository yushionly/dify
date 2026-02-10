import json
import collections

# 1. Load Station Map
try:
    with open(r'd:\tools\dify\docker\pyfiles\station_map.json', 'r', encoding='utf-8') as f:
        station_map = json.load(f)
except Exception as e:
    print(f"Error loading station_map: {e}")
    station_map = {}

# 2. Device Type Map (Common types)
device_type_map = {
    50: "ZPW-2000",
    23: "道岔",
    25: "轨道电路",
    26: "信号机",
    16: "列控",
    6: "联锁",
    24: "电源",
    65: "TSRS",
    52: "RBC", 
    15: "列控中心",
    5: "微机监测",
    33: "防灾",
    44: "GSM-R",
    111: "其他",
    51: "RBC",
    40: "调度集中",
    101: "临时限速",
    91: "安全门",
    1: "计算机联锁",
    27: "电源屏",
    3: "轨道电路",
    90: "道岔",
    4: "信号机"
}

# 3. Raw Data (Pasted from SQL Output)
# Format: (Code, Count)
station_counts_raw = [
    ("NCD", 33968), ("LPB", 29413), ("HGZ", 16216), ("NDD", 12408), ("XQB", 12260),
    ("P21", 10963), ("YXZ", 9944), ("HCX", 9654), ("YAZ", 9306), ("ZZZ", 8542),
    ("NJZ", 8433), ("NCX", 7851), ("SHX", 7523), ("FZN", 7222), ("YAN", 7133),
    ("GXS", 7064), ("XMF", 7036), ("FZZ", 6927), ("FIS", 6625), ("NXC", 6438),
    ("LSA", 6395), ("ZAZ", 6026), ("SMB", 5749), ("SRG", 5492), ("SJZ", 5289),
    ("FNY", 4787), ("ZXZ", 4564), ("HRS", 4460), ("CG6", 4360), ("XCS", 4346),
    ("CBZ", 4335), ("JBZ", 4043), ("JNB", 3976), ("PTF", 3918), ("BJZ", 3901),
    ("CG2", 3807), ("QCZ", 3793), ("YTH", 3700), ("YTB", 3684), ("DWZ", 3630),
    ("DTC", 3612), ("JLZ", 3554), ("NFZ", 3544), ("LHS", 3482), ("ZPS", 3378),
    ("ZLY", 3370), ("LSP", 3313), ("XTZ", 3305), ("XXF", 3294), ("YJS", 3264)
]

device_counts_raw = [
    (50, 648303), (23, 69073), (25, 39995), (26, 30579), (16, 23258), (6, 15404),
    (24, 15076), (65, 11648), (52, 9181), (15, 7541), (5, 5155), (33, 4481),
    (44, 3868), (111, 1762), (51, 1695), (40, 1525), (101, 1334), (91, 1242)
]

alarm_level_counts = {1: 189526, 2: 411069, 3: 301395}
external_cnt = 8757
total_alarms = sum(alarm_level_counts.values())
internal_cnt = total_alarms - external_cnt

top_alarm_des = [
    ("(检修状态:天窗修)", 50956),
    ("与CAND总线通信异常(检修状态:天窗修)", 9329),
    ("与CANE总线通信异常(检修状态:天窗修)", 9329),
    ("道岔电流定反位对比时间超标0.15秒，达到0.16秒", 8397),
    ("设备工作状态异常(检修状态:天窗修)", 8324),
    ("区段逻辑状态故障占用(检修状态:天窗修)", 7032),
    ("道岔电流定反位对比时间超标0.15秒，达到0.2秒", 5676),
    ("站内电码化功出电压模拟量超下限（0.00）", 5486),
    ("0.00,超下限报警", 4280),
    ("256.00,超上限报警", 3893),
    ("破封按钮", 3441),
    ("站内电码化功出载频模拟量超下限（0.00）", 3287),
    ("区段逻辑状态故障占用", 3179),
    ("1225-U灯丝断丝", 3144),
    ("道岔电流定反位对比时间超标0.15秒，达到0.24秒", 2897),
    ("道岔转换时间过长动作时间与标准曲线相差1秒以上。", 2622),
    ("计算机联锁系统报警", 2553),
    ("ZPW-2000系统报警(检修状态:天窗修)", 2458),
    ("破封按钮报警(检修状态:天窗修)", 2397)
]

# 4. Processing
workshop_counts = collections.defaultdict(int)
ele_section_counts = collections.defaultdict(int)

mapped_stations = []
for code, count in station_counts_raw:
    clean_code = code.strip()
    info = station_map.get(clean_code, {})
    name = info.get('name', clean_code)
    workshop = info.get('workshop', '未知车间')
    section = info.get('ele_section', '未知电务段')
    
    workshop_counts[workshop] += count
    ele_section_counts[section] += count
    mapped_stations.append((name, count))

mapped_devices = []
for dtype, count in device_counts_raw:
    dname = device_type_map.get(dtype, f"Type {dtype}")
    mapped_devices.append((dname, count))

# 5. Generate Report Markdown

report = f"""# AI智能分析报告

## 1. 报警总体情况
**统计周期**: 2025-04-01 至 2025-05-01 (估算: 4月数据)
**报警总量**: {total_alarms} 条
**报警分级**:
- 一级报警: {alarm_level_counts.get(1,0)} 条
- 二级报警: {alarm_level_counts.get(2,0)} 条
- 三级报警: {alarm_level_counts.get(3,0)} 条

**内外网分布**:
- 内部报警: {internal_cnt} 条
- 外部报警: {external_cnt} 条

## 2. 信号车间报警分布 (Top Workshops)
| 车间名称 | 报警数量 |
| :--- | :--- |
"""
for ws, count in sorted(workshop_counts.items(), key=lambda x: x[1], reverse=True):
    report += f"| {ws} | {count} |\n"

report += """
## 3. 车站报警排行 (Top 10)
| 车站名称 | 报警数量 |
| :--- | :--- |
"""
for name, count in mapped_stations[:10]:
    report += f"| {name} | {count} |\n"

report += """
## 4. 设备类型报警分布
| 设备类型 | 报警数量 |
| :--- | :--- |
"""
for name, count in mapped_devices:
    report += f"| {name} | {count} |\n"

report += """
## 5. 高频报警内容 (Top 20)
| 报警内容 | 数量 |
| :--- | :--- |
"""
for desc, count in top_alarm_des:
    # Escape pipes in description
    safe_desc = desc.replace("|", "\|").replace("\n", " ")
    report += f"| {safe_desc} | {count} |\n"

print(report)
