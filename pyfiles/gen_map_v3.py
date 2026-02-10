import os
import xml.etree.ElementTree as ET

# 模拟 api_server.py 中的逻辑
ALARM_TYPE_MAP = {}
SELF_DIAG_ALARM_TYPES = set()

def load_alarm_config():
    global ALARM_TYPE_MAP, SELF_DIAG_ALARM_TYPES
    try:
        config_path = r"d:\chengxu\dify\docker\pyfiles\alarmconfig.xml"
        
        if not os.path.exists(config_path):
            print(f"Warning: {config_path} not found.")
            return

        # Read file content with correct encoding
        with open(config_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        # Strip encoding declaration just in case
        content = content.replace('encoding="gb2312"', '')
        
        root = ET.fromstring(content)

        for alarm in root.findall("Alarm"):
            name = alarm.get("name")
            type_hex = alarm.get("type")
            
            if not name or not type_hex: continue
            
            try:
                type_val = int(type_hex, 16)
            except ValueError:
                continue
            
            subalarms = alarm.findall("SubAlarm")
            
            # 判断是否有子报警
            if not subalarms:
                SELF_DIAG_ALARM_TYPES.add(type_val)
            else:
                # 判断是否属于特殊分类
                category = None
                if name == "道岔无表示报警":
                    category = "switch_no_rep"
                elif "电气特性超限" in name:
                    category = "elec_char"
                elif "智能分析" in name:
                    category = "smart_diag"
                
                if category:
                    ALARM_TYPE_MAP[type_val] = category

        print("ALARM_TYPE_MAP = " + str(ALARM_TYPE_MAP))
        print("SELF_DIAG_ALARM_TYPES = " + str(SELF_DIAG_ALARM_TYPES))

    except Exception as e:
        import traceback
        traceback.print_exc()

load_alarm_config()
