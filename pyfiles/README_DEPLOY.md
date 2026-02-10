# 现场部署说明书 - 铁路信号报警周报生成服务

**注意：由于现场无网络环境，请务必先在有网机器上完成【1. 离线包准备】，然后将整个文件夹拷贝至现场服务器。**

## 1. 离线包准备 (在有网机器上操作)

请创建一个文件夹（例如 `Dify_Deploy_Package`），并将以下内容准备齐全：

1.  **Python 安装包**:
    *   下载 Windows 离线安装包 (例如 `python-3.11.x-amd64.exe`)。
    *   [下载地址](https://www.python.org/downloads/windows/)
2.  **Oracle Instant Client**:
    *   下载 `instantclient-basic-windows.x64-19.18.0.0.0dbru.zip`。
    *   [下载地址](https://www.oracle.com/database/technologies/instant-client/winx64-64-downloads.html)
3.  **Python 依赖包 (.whl 文件)**:
    *   在当前 `pyfiles` 目录下打开命令行，执行以下命令将依赖下载到 `packages` 文件夹：
        ```powershell
        # 创建存放依赖包的目录
        mkdir packages
        # 下载依赖但不安装
        pip download -d ./packages -r requirements.txt
        ```
4.  **程序代码**:
    *   将本目录下的所有文件 (`api_server.py`, `station_map.json`, `packages/` 目录等) 一并拷贝。

## 2. 现场环境部署 (在现场离线服务器上操作)

### 2.1 安装 Python
1.  运行准备好的 `python-3.xx.x-amd64.exe` 安装包。
2.  **重要**: 安装首页务必勾选 **"Add Python to PATH"**，然后点击 "Install Now"。

### 2.2 安装 Oracle Instant Client
1.  将 `instantclient-basic-....zip` 解压到固定目录，例如: `C:\oracle\instantclient_19_18`。
2.  **配置环境变量** (必须步骤):
    *   右键 "此电脑" -> "属性" -> "高级系统设置" -> "环境变量"。
    *   在 **"系统变量"** 中找到 `Path`，点击 "编辑"。
    *   新建一条，填入解压路径: `C:\oracle\instantclient_19_18`。
    *   **确定保存后，必须重启电脑或重新打开命令行窗口。**

### 2.3 离线安装 Python 依赖
在部署目录（包含 `packages` 文件夹的目录）下打开命令行，执行：
```powershell
pip install --no-index --find-links=./packages -r requirements.txt
```

## 3. 服务配置

### 3.1 修改数据库连接
打开 `api_server.py`，找到 `DB_CONFIG` 部分，修改为现场实际的数据库信息：

```python
# 数据库配置
DB_CONFIG = {
    "user": "csm",             # 数据库用户名
    "password": "csm",         # 数据库密码
    "dsn": "10.2.49.108:1521/orcl" # 格式: IP:端口/服务名(SID)
}
```

### 3.2 (可选) 指定 Oracle 客户端路径
如果配置环境变量后仍然报错 `DPY-3010` 或 `Library not found`，可以直接修改代码指定路径。
在 `api_server.py` 开头部分：
```python
try:
    # 修改此处为现场实际的路径
    explicit_lib_dir = r"C:\oracle\instantclient_19_18" 
    oracledb.init_oracle_client(lib_dir=explicit_lib_dir)
...
```

## 4. 启动服务

### 4.1 临时启动（测试用）
在目录下运行：
```powershell
python api_server.py
```
若看到 `Uvicorn running on http://0.0.0.0:8000` 则启动成功。

### 4.2 设为开机自启（推荐）
建议使用简单的批处理脚本配合 Windows 任务计划程序。

1.  新建 `start_server.bat`：
    ```batch
    @echo off
    cd /d D:\pyfiles
    python api_server.py
    ```
2.  打开 **"任务计划程序"** -> **"创建基本任务"**。
3.  触发器设为 **"计算机启动时"**。
4.  操作设为 **"启动程序"**，选择上面的 `.bat` 文件。

## 5. Dify 对接配置

在 Dify 的工作流 (Workflow) 或 插件 (Plugin) 中调用此接口：

*   **接口地址**: `http://<服务器IP>:8000/get_alarm_stats`
*   **请求方式**: `POST`
*   **Header**: `Content-Type: application/json`
*   **请求体 (Body)**:
    ```json
    {
        "start_date": "2024-02-01",
        "end_date": "2024-02-07"
    }
    ```
*   **常见问题**:
    *   如果 Dify 部署在 Docker 中，且 API 服务运行在宿主机，请使用宿主机局域网 IP (如 `192.168.x.x`)，**不要使用** `127.0.0.1`。
    *   请确保服务器防火墙已放行 `8000` 端口。

## 6. 故障排查

*   **报错 `DPY-3010`**: 说明 Oracle 客户端未正确安装或路径配置错误，Oracledb 运行在 "Thin" 模式下不支持旧版数据库。请重新检查 2.2 步骤。
*   **报错 `ORA-12541: TNS:no listener`**: 数据库 IP 或端口错误，或数据库服务未启动。
*   **报错 `ORA-01017: invalid username/password`**: 账号密码错误。
