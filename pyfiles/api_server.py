import json
import datetime
import oracledb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import timedelta
import collections
import os
import xml.etree.ElementTree as ET
import re

# Attempt to initialize Oracle Instant Client (Thick mode)
# This is required for connecting to older Oracle databases (e.g. 11g) that Thin mode doesn't support.
try:
    # Try explicit path first (User specific path detected during support)
    explicit_lib_dir = r"C:\oracle\instantclient_19_29"
    try:
        oracledb.init_oracle_client(lib_dir=explicit_lib_dir)
        print(f"Successfully initialized Oracle config from {explicit_lib_dir}")
    except Exception:
        # Fallback to PATH lookup
        oracledb.init_oracle_client()
        print("Successfully initialized Oracle config from PATH")
except Exception as e:
    print(f"Warning: Failed to enable python-oracledb Thick mode: {e}")
    print("If you encounter 'DPY-3010', please install Oracle Instant Client and add it to PATH.")

app = FastAPI()

# Alarm Description Map: (type, subtype) -> description
ALARM_DESC_MAP = {}

def load_alarm_config():
    global ALARM_DESC_MAP
    try:
        # Try multiple paths
        paths = [
            r"d:\chengxu\dify\docker\pyfiles\alarmconfig.xml",
            "alarmconfig.xml"
        ]
        
        config_path = None
        for p in paths:
            if os.path.exists(p):
                config_path = p
                break
        
        if not config_path:
            print("Warning: alarmconfig.xml not found.")
            return

        with open(config_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Simple cleaning of encoding attr
        content = content.replace('encoding="gb2312"', '')
        
        root = ET.fromstring(content)
        
        for alarm in root.findall("Alarm"):
            type_hex = alarm.get("type")
            if not type_hex: continue
            try:
                alarm_type = int(type_hex, 16)
            except:
                continue
            
            # Map subalarms
            for sub in alarm.findall("SubAlarm"):
                subtype_str = sub.get("subtype")
                filename = sub.get("filename", "")
                
                if subtype_str and filename:
                    try:
                        subtype = int(subtype_str)
                        # Clean filename: remove extension
                        desc = os.path.splitext(filename)[0]
                        ALARM_DESC_MAP[(alarm_type, subtype)] = desc
                    except:
                        pass
            
            # Map main alarm type default
            main_subtype_str = alarm.get("subtype")
            if main_subtype_str:
                 try:
                    main_subtype = int(main_subtype_str)
                    main_name = alarm.get("name")
                    if main_name:
                         ALARM_DESC_MAP[(alarm_type, main_subtype)] = main_name
                 except:
                     pass

    except Exception as e:
        print(f"Error loading alarm config: {e}")

load_alarm_config()

# 数据库配置
DB_CONFIG = {
    "user": "csm",
    "password": "csm",
    "dsn": "10.2.49.108:1521/orcl"
}

# 设备类型映射 (基于 gen_report.py 的补充)
DEVICE_TYPE_MAP = {
    1: "道岔",
    2: "股道",
    3: "灯或按钮",
    4: "信号机",
    5: "外电网",
    6: "电源屏",
    7: "绝缘节",
    8: "文本",
    9: "计轴设备",
    10: "空调设备",
    11: "烟感设备",
    12: "门禁设备",
    13: "电缆绝缘设备",
    14: "电源漏流设备",
    15: "25Hz轨道电路",
    16: "移频轨道电路",
    17: "环境监控设备",
    18: "UPS设备",
    19: "站联设备",
    20: "防灾设备",
    21: "半自动闭塞设备",
    22: "轨道送端电流设备",
    23: "转辙机",
    24: "联锁",
    25: "列控",
    26: "ZPW2000",
    27: "TDCS/CTC",
    28: "断路器",
    29: "祥元接口分机",
    30: "CAN分机",
    31: "室内设备",
    32: "RBC设备",
    33: "TSRS设备",
    34: "ATP设备",
    35: "RBCPri设备",
    36: "有源应答器",
    37: "进路",
    38: "临时限速",
    39: "CAN板卡设备",
    40: "灯丝设备",
    41: "外电网通讯设备",
    42: "异物继电器通讯设备",
    43: "电源屏状态图设备",
    44: "高压不对称轨道电路",
    45: "RBC外电网",
    46: "RBC电源屏",
    47: "RBC外电网通讯",
    48: "RBC电源屏状态图",
    49: "空调状态图设备",
    50: "互联互通",
    51: "道岔缺口",
    52: "站内电码化",
    53: "驼峰设备",
    54: "ATS设备",
    55: "故障诊断专家系统",
    56: "减速器",
    57: "铁科ECC联锁设备",
    58: "CXG-SY设备",
    59: "CIPS设备",
    60: "短信报警设备",
    61: "ZC设备",
    62: "郑州三方设备",
    63: "防雷",
    64: "全电子联锁",
    65: "室外监测",
    66: "蓄电池组在线均衡系统",
    67: "检修屏蔽",
    68: "联锁8K",
    69: "CCS",
    70: "应答器",
    71: "STP",
    72: "区间监督",
    73: "NMS设备",
    74: "恒毅兴防雷分线柜",
    75: "脱轨器",
    76: "DMS",
    77: "LMD",
    78: "机车信号远程监测",
    79: "电缆成端",
    80: "安全监督",
    81: "AZD",
    82: "主机PC",
    83: "TIS",
    84: "其它设备",
    85: "信号旗",
    86: "绝缘漏流",
    87: "电缆监测",
    0xfe: "车站设备"
}

# 报警分类映射表 (Type based)
# "道岔无表示报警" (0x96=150) -> switch_no_rep
# "电气特性超限报警" (0x71=113) -> elec_char
# "电气特性智能分析" (0x36=54) -> elec_char
# "道岔动作智能分析" (0x90=144) -> other
# "安全监督" (0xCF=207) -> safety (安全监督)
ALARM_TYPE_MAP = {
    150: 'switch_no_rep', 
    113: 'elec_char', 
    54: 'elec_char', 
    144: 'other',
    207: 'safety'
}

# 监测系统自诊断报警 (无子报警)
# 包含: 163(故障通知), 132(破封), 135(灯丝), 136(熔丝), 124(采集机)
# 外电网相关(67, 139, 140, 133) 因属于自身逻辑判断(含SubAlarm), 归为表2
SELF_DIAG_ALARM_TYPES = {
    163, 132, 135, 136, 124, 67, 139, 140, 133
}

# 表3 外部接口报警类型映射
TABLE3_ALARM_MAP = {
    # Power: 210(电源屏), 237(UPS) -- 移除了 67, 139, 140, 133 (外电网)
    "power": {210, 237},
    # ZPW2000: 50(ZPW)
    "zpw2000": {50},
    # ATP: 201(列控), 209(CTC)
    "atp": {201, 209},
    # Interlock: 200(联锁)
    "interlock": {200},
    "dcqk": {138}, # 138(道岔缺口)
    # Track Monitor: 219(室外监测)
    "track_monitor": {219}
}

# 加载基础数据映射
try:
    with open('station_map.json', 'r', encoding='utf-8') as f:
        STATION_MAP = json.load(f)
except Exception as e:
    print(f"Warning: station_map.json load failed: {e}")
    STATION_MAP = {}

class ReportRequest(BaseModel):
    start_date: str
    end_date: str

def get_db_connection():
    return oracledb.connect(**DB_CONFIG)

def get_table2_category(alarmtype):
    """根据 alarmtype 判断是否属于表2 (监测自诊断) 及其分类"""
    # 1. Check mapped types
    if alarmtype in ALARM_TYPE_MAP:
        return ALARM_TYPE_MAP[alarmtype]
        
    # 2. Check general self-diag types
    if alarmtype in SELF_DIAG_ALARM_TYPES:
        return "other"
        
    return None

def get_table3_category(alarmtype):
    """根据 alarmtype 判断是否属于表3 (外部接口) 及其分类"""
    for cat, types in TABLE3_ALARM_MAP.items():
        if alarmtype in types:
            return cat
    return None

def save_debug_json(data: Dict[str, Any], filename_part: str):
    try:
        # 确保保存到脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_filename = os.path.join(script_dir, f"api_output_{filename_part}.json")
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"API output saved to {output_filename}")
    except Exception as io_err:
        print(f"Error saving API output to file: {io_err}")

@app.post("/get_alarm_stats")
def get_stats(req: ReportRequest):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 转换日期字符为 Unix 时间戳
        start_dt = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(req.end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
        start_ts = int(start_dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        end_ts = int(end_dt.replace(tzinfo=datetime.timezone.utc).timestamp())

        # 1. 聚合查询：增加 alarmtype (对应 XML 中的 type)
        sql_raw = """
            SELECT telename, alarmlevel, devicetype, alarmdes, alarmtype, count(*) as cnt 
            FROM ALARM 
            WHERE createtime >= :1 
              AND createtime < :2
            GROUP BY telename, alarmlevel, devicetype, alarmdes, alarmtype
        """
        cursor.execute(sql_raw, [start_ts, end_ts])
        rows = cursor.fetchall()

        # ================= 数据初始化 =================
        # 表1：各站段报警统计表
        table1_stats = collections.defaultdict(lambda: {
            "total": 0, "level1": 0, "level2": 0, "level3": 0, "total_no_ext": 0
        })
        
        # 表2：监测系统自诊断报警
        table2_stats = collections.defaultdict(lambda: collections.defaultdict(int))

        # 表3：外部接口系统报警
        table3_stats = collections.defaultdict(lambda: collections.defaultdict(int))
        
        # 表4：重点车间排名 (按段分组)
        workshop_stats = collections.defaultdict(lambda: collections.defaultdict(int))

        # 全局统计
        total_alarms = 0
        
        # ================= 数据处理循环 =================
        for telename, level, dtype, des, atype, cnt in rows:
            telename = telename.strip()
            total_alarms += cnt
            
            # --- 获取基础信息 ---
            info = STATION_MAP.get(telename, {})
            section = info.get("ele_section", "未知电务段")
            workshop = info.get("workshop", "未知车间")
            
            # 过滤未知数据，保证表格整洁
            if section == "未知电务段": continue

            # --- 逻辑判定 ---
            # 1. 外电网判定 (简单的关键词匹配)
            des_str = str(des) if des else ""
            is_external_power = "外电网" in des_str
            
            # 2. 设备类型归类
            # dtype_name = DEVICE_TYPE_MAP.get(dtype, "其他")
            
            # --- 填充表1 (站段统计) ---
            s_stat = table1_stats[section]
            s_stat["total"] += cnt
            if level == 1: s_stat["level1"] += cnt
            elif level == 2: s_stat["level2"] += cnt
            elif level == 3: s_stat["level3"] += cnt
            if not is_external_power:
                s_stat["total_no_ext"] += cnt

            # --- 填充表2 (监测自诊断) ---
            t2_cat = get_table2_category(atype)
            
            if t2_cat:
                t2_row = table2_stats[section]
                t2_row["total"] += cnt
                # 分类统计
                if t2_cat == "elec_char": t2_row["elec_char"] += cnt
                elif t2_cat == "switch_no_rep": t2_row["switch_no_rep"] += cnt
                elif t2_cat == "safety": t2_row["safety"] += cnt
                else: t2_row["other"] += cnt
            
            # --- 余下逻辑 (表3 或 监测兜底) ---
            else:
                t3_cat = get_table3_category(atype)
                
                # Gap / Track Monitor special check
                if not t3_cat:
                    if dtype == 51 or "缺口" in str(des):
                        t3_cat = "gap"
                    elif dtype == 65:
                        t3_cat = "track_monitor"

                if t3_cat:
                    t3_row = table3_stats[section]
                    t3_row["total"] += cnt
                    t3_row[t3_cat] += cnt
                
                # 监测相关报警归为表2 other (兜底)
                elif "监测" in des_str:
                     t2_row = table2_stats[section]
                     t2_row["total"] += cnt
                     t2_row["other"] += cnt
                     
                # 其余归为表3 other
                else:
                    t3_row = table3_stats[section]
                    t3_row["total"] += cnt
                    t3_row["other"] += cnt

            # --- 填充表4 (车间统计) ---
            workshop_stats[section][workshop] += cnt

        # ================= 格式化输出 =================
        
        # 站段基础数据配置 (车站数, 道岔换算组数)
        SECTION_BASE_INFO = {
            "南昌电务段": {"stations": 327, "turnouts": 114047},
            "福州电务段": {"stations": 363, "turnouts": 127723},
            "南昌高铁基础设施段": {"stations": 89, "turnouts": 28964}
        }

        # 格式化表1
        table1_output = []
        for section, data in table1_stats.items():
            # 获取该段的基础配置，没有则默认为 0
            base_info = SECTION_BASE_INFO.get(section, {"stations": 0, "turnouts": 0})
            
            table1_output.append({
                "name": section,
                "station_count": base_info["stations"], 
                "turnout_count": base_info["turnouts"], 
                **data
            })

        # 格式化表2
        table2_output = []
        for section, data in table2_stats.items():
            table2_output.append({
                "name": section,
                "count": data["total"],
                "breakdown": data
            })
            
        # 格式化表3
        table3_output = []
        for section, data in table3_stats.items():
            table3_output.append({
                "name": section,
                "count": data["total"],
                "breakdown": data
            })

        # 格式化表4 (每个站段取前3)
        table4_output = []
        for section, w_dict in workshop_stats.items():
            # 对该段的车间按报警数倒序排列
            sorted_ws = sorted(w_dict.items(), key=lambda x: x[1], reverse=True)
            # 取前3名
            top3 = sorted_ws[:3]
            for w_name, w_count in top3:
                table4_output.append({
                    "name": f"{section} - {w_name}",
                    "count": w_count
                })
        
        # 可选：最后再对 table4_output 整体排序，或者保持按段分组顺序
        # 这里按总数排序一下以保证原来的风格，或者直接就这样
        table4_output.sort(key=lambda x: x["count"], reverse=True)

        # Top 10 隐患 (用于文本分析)
        sql_top = """
            SELECT alarmdes, count(*) as cnt
            FROM ALARM
            WHERE createtime >= :1 
              AND createtime < :2
            GROUP BY alarmdes
            ORDER BY cnt DESC
        """
        # Ensure older Oracle versions compatibility by not complicating (limit dealt with in python if needed, or rownum)
        # However, LIMIT/FETCH FIRST is nicer. Let's start with getting all and slicing in python to be safe for 11g,
        # or use ROWNUM.
        
        # Using ROWNUM for 11g compatibility:
        sql_top = """
            SELECT * FROM (
                SELECT alarmdes, count(*) as cnt
                FROM ALARM
                WHERE createtime >= :1 
                  AND createtime < :2
                GROUP BY alarmdes
                ORDER BY cnt DESC
            ) WHERE ROWNUM <= 10
        """
        cursor.execute(sql_top, [start_ts, end_ts])
        top_faults = [{"issue": row[0], "count": row[1]} for row in cursor.fetchall()]

        # 趋势数据 (简单实现)
        trend = {"status": "未知", "growth": "0%"} # 待实现：需要查上周

        result_data = {
            "period": f"{req.start_date} 至 {req.end_date}",
            "overview": {"total": total_alarms},
            "table1_station_stats": table1_output,
            "table2_self_diagnosis": table2_output,
            "table3_external_interface": table3_output,
            "table4_workshop_rank": table4_output,
            "top_issues": top_faults,
            "trend": trend
        }

        # 将输出写入文件，以便调试查看
        save_debug_json(result_data, "part1_overview")

        return result_data

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_detail = str(e)
        # Check if we are in Thin mode and the error looks like a version support issue
        if "DPY-3010" in error_detail and oracledb.is_thin_mode():
            error_detail += " [HINT: You are currently using python-oracledb in THIN mode which does not support this old Oracle database version. Please install Oracle Instant Client on this Windows machine and add it to PATH to enable THICK mode.]"
            
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        if conn: conn.close()

# --- New Report Endpoints (Option 1) ---

@app.post("/report/part1_overview")
def report_part1_overview(req: ReportRequest):
    """
    Generate Part 1: Alarm Overview (Reuses existing get_stats logic)
    """
    return get_stats(req)

@app.post("/report/part2_hazards")
def report_part2_hazards(req: ReportRequest):
    """
    Generate Part 2: Key Hazards Analysis (Excluding Skylight)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Time calc
        start_dt = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(req.end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
        start_ts = int(start_dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        end_ts = int(end_dt.replace(tzinfo=datetime.timezone.utc).timestamp())

        # Define Skylight Filter: maintanceflag != 0 means skylight. 
        # So Valid/Hazard = (maintanceflag = 0 OR maintanceflag IS NULL)
        valid_condition = "AND (maintanceflag = 0 OR maintanceflag IS NULL)"

        # 1. Overview: Total and Unhandled
        # User specified logic: 
        # - processstatus != 0 means processed. So 0 or NULL means unhandled.
        # - restoretime is available for recovery info if needed, but 'unhandled' usually refers to process status.
        total_valid = 0
        unhandled_count = -1
        
        try:
            sql_overview = f"""
                SELECT 
                    count(*) as total,
                    sum(case when processstatus = 0 or processstatus is null then 1 else 0 end) as unhandled
                FROM ALARM
                WHERE createtime >= :1 AND createtime < :2
                {valid_condition}
            """
            cursor.execute(sql_overview, [start_ts, end_ts])
            row = cursor.fetchone()
            if row:
                total_valid = row[0]
                unhandled_count = row[1] if row[1] is not None else 0
        except Exception as e:
            # Fallback if processstatus column missing
            print(f"Warning: 'processstatus' query failed: {e}")
            sql_fallback = f"""
                SELECT count(*) FROM ALARM 
                WHERE createtime >= :1 AND createtime < :2 {valid_condition}
            """
            cursor.execute(sql_fallback, [start_ts, end_ts])
            total_valid = cursor.fetchone()[0]

        retention_rate = 0.0
        if total_valid > 0 and unhandled_count >= 0:
            retention_rate = round((unhandled_count / total_valid) * 100, 2)

        # 2. Detailed Analysis by Category
        # We fetch aggregated data and categorize in Python to ensure flexibility
        # Updated SQL to include alarmtype, alarmsubtype and devicename for better grouping
        sql_details = f"""
            SELECT devicetype, alarmdes, telename, alarmtype, alarmsubtype, devicename, count(*) as cnt
            FROM ALARM
            WHERE createtime >= :1 AND createtime < :2
            {valid_condition}
            GROUP BY devicetype, alarmdes, telename, alarmtype, alarmsubtype, devicename
        """
        cursor.execute(sql_details, [start_ts, end_ts])
        rows = cursor.fetchall()
        
        # Categorization Logic
        # Updated based on user provided constants
        categories = {
            "switch": {"ids": [1, 23, 51]},
            "signal": {"ids": [4, 40, 3]},
            "track": {"ids": [15, 16, 26, 9, 44, 65, 7, 22]},
            "control": {"ids": [24, 25, 27, 32, 33, 34, 54, 61, 64, 68, 21, 19, 57, 58, 59, 71]}, 
            "power": {"ids": [5, 6, 14, 18, 28, 66, 43]}
        }
        
        # Structure: category -> { "alarms": { generic_name: { count: int, specifics: { des: int } } }, "stations": { name: int } }
        category_data = {k: {"alarms": {}, "stations": collections.defaultdict(int)} for k in categories}

        for dtype, des, station, atype, asubtype, devname, cnt in rows:
            station = station.strip() if station else "Unknown"
            des = des.strip() if des else "Unknown"
            devname = devname.strip() if devname else ""
            
            target_cat = "other"
            for cat_key, cat_cfg in categories.items():
                if dtype in cat_cfg["ids"]:
                    target_cat = cat_key
                    break
            
            if target_cat != "other":
                # Track Station
                category_data[target_cat]["stations"][station] += cnt
                
                # Determine Generic Alarm Name
                # Type safe conversion
                try: at = int(atype) if atype is not None else 0
                except: at = 0
                try: ast = int(asubtype) if asubtype is not None else 0
                except: ast = 0
                
                gen_name = None
                # Try exact match (type, subtype)
                if (at, ast) in ALARM_DESC_MAP:
                     gen_name = ALARM_DESC_MAP[(at, ast)]
                
                if not gen_name:
                    # If we can't map it, force using a cleaned version of des or just des
                    # Attempt to strip device prefix "Device#Msg"
                    if "#" in des:
                        try:
                            gen_name = des.split("#", 1)[1]
                        except:
                            gen_name = des
                    else:
                        gen_name = des
                
                # Update stats
                c_alarms = category_data[target_cat]["alarms"]
                if gen_name not in c_alarms:
                    c_alarms[gen_name] = {"count": 0, "specifics": collections.defaultdict(int)}
                
                c_alarms[gen_name]["count"] += cnt
                
                # Create a specific identifier: Station DeviceName (AlarmDescription)
                st_name = STATION_MAP.get(station, {}).get("name", station)
                
                # Construct unique device identifier string
                # If devname is present, use it. Otherwise rely on des.
                identifier_parts = [st_name]
                if devname:
                    identifier_parts.append(devname)
                
                # Only add description if it's not redundant or if devname is missing 
                # (sometimes des contains the device name, sometimes not)
                # To be safe, include des details.
                identifier_parts.append(f"({des})")
                
                specific_key = " ".join(identifier_parts)
                
                c_alarms[gen_name]["specifics"][specific_key] += cnt
        
        # Format Output
        category_analysis = {}
        for cat_key, stat_obj in category_data.items():
            
            # Top Stations
            top_st = []
            for k, v in sorted(stat_obj["stations"].items(), key=lambda x: x[1], reverse=True)[:6]:
                 # Map Code to Name
                 st_name = STATION_MAP.get(k, {}).get("name", k)
                 top_st.append({"name": st_name, "count": v})

            # Top Alarm Types
            sorted_alarms = sorted(stat_obj["alarms"].items(), key=lambda x: x[1]["count"], reverse=True)[:10]
            
            top_al = []
            for aname, adata in sorted_alarms:
                # Top devices (specific alarmdes)
                top_specs = sorted(adata["specifics"].items(), key=lambda x: x[1], reverse=True)[:5]
                fmt_specs = [{"dev_desc": k, "count": v} for k, v in top_specs]
                
                top_al.append({
                    "name": aname,
                    "count": adata["count"],
                    "top_devices": fmt_specs
                })

            category_analysis[cat_key] = {
                "top_alarm_types": top_al,
                "top_faulty_stations": top_st
            }

        result = {
            "period": f"{req.start_date} to {req.end_date}",
            "overview": {
                "total_valid_alarms": total_valid,
                "unhandled_alarms": unhandled_count,
                "retention_rate": f"{retention_rate}%"
            },
            "categories": category_analysis
        }
        save_debug_json(result, "part2_hazards")
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

@app.post("/report/part3_trends")
def report_part3_trends(req: ReportRequest):
    """
    Generate Part 3: Trend Analysis (Detailed for Report Section 3)
    Includes: Cycle Comparison, Workshop Rankings (Red/Black/Green), Device Trends
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Date Calculations
        curr_s = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        curr_e_incl = datetime.datetime.strptime(req.end_date, "%Y-%m-%d")
        curr_e_excl = curr_e_incl + datetime.timedelta(days=1)
        
        curr_s_ts = int(curr_s.replace(tzinfo=datetime.timezone.utc).timestamp())
        curr_e_ts = int(curr_e_excl.replace(tzinfo=datetime.timezone.utc).timestamp())
        
        days_count = (curr_e_incl - curr_s).days + 1
        
        # Previous Period
        duration = curr_e_excl - curr_s
        
        # 智能识别自然月逻辑：如果开始日期是1号，且结束日期（excl）也是1号，则认为是整月比较
        # 这种情况下，上一周期应取自然月的前几个月，而不是简单的减去天数
        prev_s = None
        prev_e_excl = curr_s

        if curr_s.day == 1 and curr_e_excl.day == 1:
            try:
                # 计算跨越的月数
                num_months = (curr_e_excl.year - curr_s.year) * 12 + (curr_e_excl.month - curr_s.month)
                if num_months > 0:
                    # 计算前一周期的起始时间： curr_s 减去 num_months
                    # 公式：Month = month - 1 - delta, Year = year + month // 12, Month = month % 12 + 1
                    m_new = curr_s.month - 1 - num_months
                    y_new = curr_s.year + m_new // 12
                    m_new = m_new % 12 + 1
                    prev_s = datetime.datetime(y_new, m_new, 1)
            except Exception as e:
                print(f"Error in month calculation: {str(e)}, falling back to day diff")
        
        # 如果不是整月或计算失败，使用按天平移
        if prev_s is None:
            prev_s = curr_s - duration
        
        prev_s_ts = int(prev_s.replace(tzinfo=datetime.timezone.utc).timestamp())
        prev_e_ts = int(prev_e_excl.replace(tzinfo=datetime.timezone.utc).timestamp())

        # 2. Data Fetching Helper
        def fetch_period_data(t_start, t_end):
            data = {}
            
            # A. Global Stats (Total, Skylight, Non-Skylight, Processed)
            # maintanceflag != 0 -> Skylight
            # processstatus != 0 -> Processed (Fixed typo: processtatus -> processstatus)
            try:
                sql_global = """
                    SELECT 
                        count(*) as total,
                        sum(case when maintanceflag != 0 then 1 else 0 end) as skylight,
                        sum(case when maintanceflag = 0 or maintanceflag is null then 1 else 0 end) as non_skylight,
                        sum(case when processstatus != 0 then 1 else 0 end) as processed
                    FROM ALARM
                    WHERE createtime >= :1 AND createtime < :2
                """
                cursor.execute(sql_global, [t_start, t_end])
                row = cursor.fetchone()
                data["global"] = {
                    "total": row[0],
                    "skylight": row[1] or 0,
                    "non_skylight": row[2] or 0,
                    "processed": row[3] or 0
                }
            except Exception as e:
                print(f"Global stats query failed: {e}")
                data["global"] = {"total": 0, "skylight": 0, "non_skylight": 0, "processed": 0}

            # B. Workshop Stats (Group by Station -> Map to Workshop later)
            try:
                sql_station = """
                    SELECT telename, count(*), sum(case when processstatus != 0 then 1 else 0 end)
                    FROM ALARM
                    WHERE createtime >= :1 AND createtime < :2
                    GROUP BY telename
                """
                cursor.execute(sql_station, [t_start, t_end])
                data["stations"] = cursor.fetchall() # list of (name, total, processed)
            except Exception:
                data["stations"] = []

            # C. Device Type Stats
            try:
                sql_device = """
                    SELECT devicetype, count(*)
                    FROM ALARM
                    WHERE createtime >= :1 AND createtime < :2
                    GROUP BY devicetype
                """
                cursor.execute(sql_device, [t_start, t_end])
                data["devices"] = cursor.fetchall()
            except Exception:
                data["devices"] = []
                
            return data

        curr_data = fetch_period_data(curr_s_ts, curr_e_ts)
        prev_data = fetch_period_data(prev_s_ts, prev_e_ts)

        # 3. Processing Section 1: Cycle Indicators
        def calc_kpi(c_data, p_data, days):
             # Access inner "global" dict
            c = c_data["global"]
            p = p_data["global"]
            
            def safe_rate(num, denom): return round((num / denom * 100), 1) if denom > 0 else 0.0
            def daily_avg(total, d): return round(total / d, 1) if d > 0 else 0
            
            # Growth format
            def growth(curr, prev):
                if prev == 0: return "100.0%" if curr > 0 else "0.0%"
                diff = ((curr - prev) / prev) * 100
                return f"{diff:+.1f}%"

            return {
                "daily_avg_total": {
                    "curr": daily_avg(c["total"], days),
                    "prev": daily_avg(p["total"], days),
                    "growth": growth(daily_avg(c["total"], days), daily_avg(p["total"], days))
                },
                "skylight_count": {
                    "curr": c["skylight"], 
                    "prev": p["skylight"],
                    "growth": growth(c["skylight"], p["skylight"])
                },
                "non_skylight_count": {
                    "curr": c["non_skylight"],
                    "prev": p["non_skylight"],
                    "growth": growth(c["non_skylight"], p["non_skylight"])
                },
                "process_rate": {
                    "curr": f"{safe_rate(c['processed'], c['total'])}%",
                    "prev": f"{safe_rate(p['processed'], p['total'])}%",
                    "diff_pp": f"{safe_rate(c['processed'], c['total']) - safe_rate(p['processed'], p['total']):+.1f} pp"
                }
            }

        kpi_stats = calc_kpi(curr_data, prev_data, days_count)

        # 4. Processing Section 2: Workshop Analysis
        def aggregate_workshops(station_rows):
            ws_stats = collections.defaultdict(lambda: {"total": 0, "processed": 0})
            for row in station_rows:
                st_name = row[0].strip() if row[0] else "Unknown"
                cnt = row[1]
                proc = row[2] or 0
                
                info = STATION_MAP.get(st_name, {})
                ws_name = info.get("workshop", "Unknown Workshop")
                
                ws_stats[ws_name]["total"] += cnt
                ws_stats[ws_name]["processed"] += proc
            return ws_stats

        curr_ws = aggregate_workshops(curr_data["stations"])
        prev_ws = aggregate_workshops(prev_data["stations"])

        # Compare and List
        ws_comparison = []
        all_workshops = set(list(curr_ws.keys()) + list(prev_ws.keys()))
        
        for ws in all_workshops:
            if ws == "Unknown Workshop": continue
            
            c = curr_ws.get(ws, {"total": 0, "processed": 0})
            p = prev_ws.get(ws, {"total": 0, "processed": 0})
            
            if c["total"] == 0 and p["total"] == 0: continue
            
            c_rate = (c["processed"] / c["total"] * 100) if c["total"] > 0 else 0.0
            p_rate = (p["processed"] / p["total"] * 100) if p["total"] > 0 else 0.0
            
            ws_comparison.append({
                "workshop": ws,
                "total_alarms": c["total"],
                "curr_rate": round(c_rate, 1),
                "prev_rate": round(p_rate, 1),
                "diff_pp": round(c_rate - p_rate, 1)
            })

        # Sort lists for Red/Black/Green boards
        # Red: Lowest processing rate (with some volume > 0)
        valid_ws = [w for w in ws_comparison if w["total_alarms"] > 0]
        
        # Sort by rate ascending (Lowest first)
        lowest_rate_list = sorted(valid_ws, key=lambda x: x["curr_rate"])[:5]
        
        # Sort by rate drop (Biggest drop first -> most negative diff)
        biggest_drop_list = sorted(valid_ws, key=lambda x: x["diff_pp"])[:5]
        
        # Sort by rate descending (Best first)
        best_rate_list = sorted(valid_ws, key=lambda x: x["curr_rate"], reverse=True)[:5]
        
        # Sort by growth in rate (Best improvement)
        best_improvement_list = sorted(valid_ws, key=lambda x: x["diff_pp"], reverse=True)[:5]


        # 5. Processing Section 3: Device Trends
        def aggregate_devices(device_rows):
             # Cats: switch, signal, track, control, power
            cats = {"switch": 0, "signal": 0, "track": 0, "control": 0, "power": 0, "other": 0}
            
            # Helper set for fast lookup
            # Using the same Mapping as Part 2 roughly
            mapping_sets = {
                "switch": {1, 23, 51},
                "signal": {4, 40, 3},
                "track": {15, 16, 26, 9, 44, 65, 7, 22},
                "control": {24, 25, 27, 32, 33, 34, 54, 61, 64, 68, 21, 19, 57, 58, 59, 71}, 
                "power": {5, 6, 14, 18, 28, 66, 43}
            }

            for row in device_rows:
                dtype = row[0]
                cnt = row[1]
                
                found = False
                for cat_name, id_set in mapping_sets.items():
                    if dtype in id_set:
                        cats[cat_name] += cnt
                        found = True
                        break
                
                if not found:
                    cats["other"] += cnt
                    
            return cats

        curr_dev = aggregate_devices(curr_data["devices"])
        prev_dev = aggregate_devices(prev_data["devices"])
        
        device_trends = []
        for cat in ["switch", "signal", "track", "control", "power"]:
            c_cnt = curr_dev[cat]
            p_cnt = prev_dev[cat]
            
            trend_pct = "0%"
            if p_cnt > 0:
                trend_pct = f"{((c_cnt - p_cnt)/p_cnt * 100):+.1f}%"
            elif c_cnt > 0:
                trend_pct = "+100%"
                
            device_trends.append({
                "device_type": cat,
                "curr_count": c_cnt,
                "prev_count": p_cnt,
                "trend": trend_pct
            })


        result = {
            "period": f"{req.start_date} to {req.end_date}",
            "kpi_comparison": kpi_stats,
            "workshop_analysis": {
                "red_board_candidates": {
                    "lowest_process_rate": lowest_rate_list,
                    "biggest_quality_drop": biggest_drop_list
                },
                "green_board_candidates": {
                    "highest_process_rate": best_rate_list,
                    "best_improvement": best_improvement_list
                },
                "full_ranking": sorted(ws_comparison, key=lambda x: x["curr_rate"]) 
            },
            "device_trends": device_trends
        }
        
        save_debug_json(result, "part3_trends")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

@app.post("/report/part4_skylight")
def report_part4_skylight(req: ReportRequest):
    """
    Generate Part 4: Skylight (Maintenance) Alarm Analysis
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        start_dt = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(req.end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
        start_ts = int(start_dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        end_ts = int(end_dt.replace(tzinfo=datetime.timezone.utc).timestamp())

        # 1. Statistics Calculation
        total_period_alarms = 0
        total_skylight_alarms = 0
        processed_skylight_alarms = 0
        
        try:
            # A. Total Alarms in Period (for Ratio)
            cursor.execute("SELECT count(*) FROM ALARM WHERE createtime >= :1 AND createtime < :2", [start_ts, end_ts])
            total_period_alarms = cursor.fetchone()[0]

            # B. Skylight Stats (maintanceflag != 0)
            # Count Total & Processed (processstatus != 0)
            sql_skylight = """
                SELECT 
                    count(*) as total,
                    sum(case when processstatus != 0 then 1 else 0 end) as processed
                FROM ALARM
                WHERE createtime >= :1 AND createtime < :2 AND maintanceflag != 0
            """
            cursor.execute(sql_skylight, [start_ts, end_ts])
            row = cursor.fetchone()
            if row:
                total_skylight_alarms = row[0]
                processed_skylight_alarms = row[1] or 0
        except Exception as e:
            print(f"Part 4 Stats Query Error: {e}")

        # Ratios
        skylight_ratio = 0.0
        if total_period_alarms > 0:
            skylight_ratio = round((total_skylight_alarms / total_period_alarms) * 100, 2)
            
        process_rate = 0.0
        if total_skylight_alarms > 0:
            process_rate = round((processed_skylight_alarms / total_skylight_alarms) * 100, 2)

        # 2. Top Involved Devices (Top 3)
        top_devices_list = []
        try:
            sql_dev = """
                SELECT devicetype, count(*) as cnt
                FROM ALARM
                WHERE createtime >= :1 AND createtime < :2 AND maintanceflag != 0
                GROUP BY devicetype
                ORDER BY cnt DESC
            """
            # Limit 3
            sql_dev_lim = f"SELECT * FROM ({sql_dev}) WHERE ROWNUM <= 3"
            cursor.execute(sql_dev_lim, [start_ts, end_ts])
            
            for r in cursor.fetchall():
                d_name = DEVICE_TYPE_MAP.get(r[0], f"Unknown({r[0]})")
                top_devices_list.append(d_name)
        except Exception:
            pass

        # 3. Deep Analysis Data (Top Issues with Station info)
        # Grouping by (alarmdes, telename) helps identify issues like "Zhaoan Station 2X2 Switch"
        detailed_issues = []
        try:
            sql_deep = """
                SELECT alarmdes, telename, devicetype, count(*) as cnt
                FROM ALARM
                WHERE createtime >= :1 AND createtime < :2 AND maintanceflag != 0
                GROUP BY alarmdes, telename, devicetype
                ORDER BY cnt DESC
            """
            # Fetch Top 15 for analysis context
            sql_deep_lim = f"SELECT * FROM ({sql_deep}) WHERE ROWNUM <= 15"
            cursor.execute(sql_deep_lim, [start_ts, end_ts])
            
            for r in cursor.fetchall():
                d_name = DEVICE_TYPE_MAP.get(r[2], "Unknown")
                st_code = r[1].strip() if r[1] else ""
                st_name = STATION_MAP.get(st_code, {}).get("name", st_code)
                detailed_issues.append({
                    "description": r[0],
                    "station": st_name,
                    "device": d_name,
                    "count": r[3]
                })
        except Exception:
            pass

        result = {
            "period": f"{req.start_date} to {req.end_date}",
            "stats": {
                "total_period_alarms": total_period_alarms,
                "total_skylight_alarms": total_skylight_alarms,
                "skylight_ratio_percent": f"{skylight_ratio}%",
                "processed_skylight_alarms": processed_skylight_alarms,
                "process_rate_percent": f"{process_rate}%"
            },
            "main_involved_devices": top_devices_list,
            "detailed_issues_for_analysis": detailed_issues
        }
        
        save_debug_json(result, "part4_skylight")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Fallback 
        err_res = {"error": str(e)}
        save_debug_json(err_res, "part4_skylight_error")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
