import os
import xml.etree.ElementTree as ET

# 模拟 api_server.py 中的逻辑
ALARM_CATEGORY_MAP = {}
SELF_DIAG_ALARM_NAMES = set()

def load_alarm_config():
    try:
        config_path = r"d:\chengxu\dify\docker\pyfiles\alarmconfig.xml"
        
        if not os.path.exists(config_path):
            print(f"Warning: {config_path} not found.")
            return

        tree = ET.parse(config_path)
        root = tree.getroot()

        for alarm in root.findall("Alarm"):
            name = alarm.get("name")
            if not name: continue
            
            subalarms = alarm.findall("SubAlarm")
            
            # 判断父级类别
            category = None
            if name == "道岔无表示报警":
                category = "switch_no_rep"
            elif "电气特性超限" in name:
                category = "elec_char"
            elif "智能分析" in name:
                category = "smart_diag"
            
            if not subalarms:
                # 规则：未配置 SubAlarm 的属于监测系统自身报警 (归为 Other)
                SELF_DIAG_ALARM_NAMES.add(name)
            else:
                # 配置了 SubAlarm 的，如果是指定类别，则将其子项加入映射
                if category:
                    for sub in subalarms:
                        filename = sub.get("filename")
                        if filename:
                            # 从文件名提取有意义的描述部分
                            base = os.path.basename(filename)
                            name_part = os.path.splitext(base)[0]
                            ALARM_CATEGORY_MAP[name_part] = category
                            
                            if "_" in name_part:
                                parts = name_part.split("_", 1)
                                if len(parts) > 1:
                                    ALARM_CATEGORY_MAP[parts[1]] = category

        print("ALARM_CATEGORY_MAP = " + str(ALARM_CATEGORY_MAP))
        print("SELF_DIAG_ALARM_NAMES = " + str(SELF_DIAG_ALARM_NAMES))

    except Exception as e:
        print(f"Error loading alarmconfig.xml: {e}")

load_alarm_config()
