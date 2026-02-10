import xml.etree.ElementTree as ET

file_path = "./Stations.xml"  # 你的文件路径

# 先用二进制读取，然后解码（解决多字节编码问题）
with open(file_path, 'rb') as f:
    xml_bytes = f.read()
    # 从XML声明中可以看到编码是 gb2312
    xml_content = xml_bytes.decode('utf-8', errors='ignore')

# 从字符串解析XML
root = ET.fromstring(xml_content)

# 生成 station_map
station_map = {}

for sta in root.findall('Sta'):
    # 获取属性值，并去除首尾空格
    telename = sta.get('telename', '').strip()
    name = sta.get('name', '').strip()
    workshop = sta.get('Workshop', '').strip()
    ele_section = sta.get('EleSection', '').strip()
    
    # 只添加有电报码的车站
    if telename:
        station_map[telename] = {
            "name": name,
            "workshop": workshop,
            "ele_section": ele_section
        }

# 打印结果查看
print(f"共解析 {len(station_map)} 个车站")
print("\n前5个示例：")
for i, (code, info) in enumerate(station_map.items()):
    if i >= 5:
        break
    print(f'    "{code}": {info},')

# 如果需要保存到文件
import json
with open('station_map.json', 'w', encoding='utf-8') as f:
    json.dump(station_map, f, ensure_ascii=False, indent=2)

print("\n已保存到 station_map.json")