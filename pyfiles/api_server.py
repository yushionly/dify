import json
import datetime
import oracledb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import timedelta
import collections

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

# 数据库配置
DB_CONFIG = {
    "user": "csm",
    "password": "csm",
    "dsn": "10.2.49.108:1521/orcl"
}

# 设备类型映射 (基于 gen_report.py 的补充)
DEVICE_TYPE_MAP = {
    50: "ZPW-2000", 23: "道岔", 25: "轨道电路", 26: "信号机", 
    16: "列控", 6: "联锁", 24: "电源", 65: "TSRS", 
    52: "RBC", 15: "列控中心", 5: "微机监测", 33: "防灾",
    44: "GSM-R", 27: "电源屏", 1: "计算机联锁", 90: "道岔"
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

@app.post("/get_alarm_stats")
def get_stats(req: ReportRequest):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 转换日期字符为 Unix 时间戳 (因为数据库 createtime 是 NUMBER 类型)
        # 假设输入是 'YYYY-MM-DD'，对应 UTC 0点
        start_dt = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(req.end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
        
        # 强制使用 UTC 时区以生成标准的 Unix Timestamp
        start_ts = int(start_dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        end_ts = int(end_dt.replace(tzinfo=datetime.timezone.utc).timestamp())

        # 1. 核心聚合查询：增加 devicetype 和 alarmdes 字段
        # 注意：为了性能，尽量不要全表扫，这里依赖 createtime 索引
        sql_raw = """
            SELECT telename, alarmlevel, devicetype, alarmdes, count(*) as cnt 
            FROM ALARM 
            WHERE createtime >= :1 
              AND createtime < :2
            GROUP BY telename, alarmlevel, devicetype, alarmdes
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
        
        # 表4：重点车间排名
        workshop_stats = collections.defaultdict(int)

        # 全局统计
        total_alarms = 0
        
        # ================= 数据处理循环 =================
        for telename, level, dtype, des, cnt in rows:
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
            is_external_power = "外电网" in str(des)
            
            # 2. 设备类型归类
            dtype_name = DEVICE_TYPE_MAP.get(dtype, "其他")
            
            # --- 填充表1 (站段统计) ---
            s_stat = table1_stats[section]
            s_stat["total"] += cnt
            if level == 1: s_stat["level1"] += cnt
            elif level == 2: s_stat["level2"] += cnt
            elif level == 3: s_stat["level3"] += cnt
            if not is_external_power:
                s_stat["total_no_ext"] += cnt

            # --- 填充表2 (监测自诊断) ---
            # 逻辑：如果是微机监测(5) 或 包含特定关键字
            if dtype == 5 or "监测" in str(des):
                t2_row = table2_stats[section]
                t2_row["total"] += cnt
                # 细分逻辑 (关键词需根据实际调整)
                if "通信" in str(des) or "状态" in str(des): t2_row["self_alarm"] += cnt
                elif "模拟量" in str(des): t2_row["elec_char"] += cnt
                elif "无表示" in str(des): t2_row["switch_no_rep"] += cnt
                else: t2_row["other"] += cnt
            
            # --- 填充表3 (外部接口) ---
            # 逻辑：非监测类报警
            else:
                t3_row = table3_stats[section]
                t3_row["total"] += cnt
                # 细分逻辑
                if dtype in [24, 27]: t3_row["power"] += cnt
                elif dtype in [50]: t3_row["zpw2000"] += cnt
                elif dtype in [15, 16, 52, 51]: t3_row["atp"] += cnt # 列控
                elif dtype in [1, 6]: t3_row["interlock"] += cnt
                elif "缺口" in str(des): t3_row["gap"] += cnt
                else: t3_row["other"] += cnt

            # --- 填充表4 (车间统计) ---
            workshop_stats[f"{section} - {workshop}"] += cnt

        # ================= 格式化输出 =================
        
        # 格式化表1
        table1_output = []
        for section, data in table1_stats.items():
            table1_output.append({
                "name": section,
                # station_count / turnout_count 暂时置 0，因为 station_map.json 结构里可能没有统计这些
                "station_count": 0, 
                "turnout_count": 0, 
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

        # 格式化表4 (排序)
        sorted_workshops = sorted(workshop_stats.items(), key=lambda x: x[1], reverse=True)
        table4_output = [{"name": k, "count": v} for k, v in sorted_workshops[:5]] # 取前5

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
        try:
            import os
            # 确保保存到脚本所在目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_filename = os.path.join(script_dir, "api_output.json")
            
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=4)
            print(f"API output saved to {output_filename}")
        except Exception as io_err:
            print(f"Error saving API output to file: {io_err}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
