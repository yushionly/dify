# Dify + Python + Oracle 报警周报系统部署指南

## 1. 环境准备 (Python 中间件)
此服务用于连接 Oracle 数据库并计算统计数据，供 Dify 调用。

1.  **安装依赖**:
    ```powershell
    cd d:\tools\dify\docker\pyfiles
    pip install -r requirements.txt
    ```

2.  **配置数据库**:
    打开 `api_server.py`，修改 `DB_CONFIG` 字典中的 IP、用户名、密码。
    ```python
    DB_CONFIG = {
        "user": "csm",
        "password": "csm",
        "dsn": "10.2.49.108:1521/orcl" 
    }
    ```

3.  **启动服务**:
    ```powershell
    python api_server.py
    ```
    服务将在 `http://0.0.0.0:8000` 启动。
    测试地址: `http://localhost:8000/docs` (自带 Swagger UI 测试界面)。

## 2. Dify Workflow 配置
请在 Dify 中创建一个 **Workflow** 应用。

### 步骤 A: 开始节点 (Start)
添加两个输入变量：
*   `start_date` (Text, 必填, 示例: 2024-02-01)
*   `end_date` (Text, 必填, 示例: 2024-02-07)

### 步骤 B: HTTP 请求节点 (HTTP Request)
*   **API URL**: `http://<你的本机IP>:8000/get_alarm_stats` 
    *   *注意：如果 Dify 运行在 Docker 容器中，访问宿主机需使用宿主机内网 IP，不能用 localhost。*
*   **Method**: `POST`
*   **Body Type**: `JSON`
*   **Body Content**:
    ```json
    {
      "start_date": "{{#start.start_date#}}",
      "end_date": "{{#start.end_date#}}"
    }
    ```
*   **Timeout**: 设置为 60秒 (防止 SQL 查询过慢)。

### 步骤 C: LLM 节点 (DeepSeek / 通义千问 等)
*   **System Prompt**: 复制 `dify_prompt.md` 中的内容。
*   **User Message**: "请生成报告。"
*   **Context/Variables**: 确保 Prompt 中的 `{{#http_request.body#}}` 正确引用了上一步 HTTP 节点的输出结果。

### 步骤 D: 结束节点 (End)
*   输出 LLM 的生成结果。

## 3. 运行测试
在 Dify 界面点击“预览/运行”，输入日期 `2024-02-01` 和 `2024-02-07`，查看生成的 Markdown 报告。
