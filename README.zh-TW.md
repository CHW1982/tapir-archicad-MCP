# Archicad Tapir MCP 伺服器

繁體中文 | [English](./README.md)

本專案為 Archicad 提供了一個模型上下文協議（MCP）伺服器。它作為橋樑，允許 AI 代理和應用程式（如 Claude for Desktop）通過包裝社群驅動的 **Tapir API** 和**官方 Archicad JSON API**，與正在運行的 Archicad 實例進行交互。

該伺服器從組合的 API 架構中動態生成全面的 **137 個** MCP 工具集，實現對 Archicad 專案的精細控制。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

> **免責聲明：** 本專案處於早期開發階段。尚未經過廣泛測試，主要用於實驗和教育目的。介面和功能可能在未來更新中發生變化。請謹慎使用。

## 主要特色

-   **智能工具發現：** 伺服器提供了一個簡單的 `discover_tools` 功能，使用強大的本地語義搜索引擎，從用戶的自然語言查詢中找到最相關的 Archicad 命令。
-   **龐大工具集，最小佔用：** 通過智能合併社群 Tapir API 和官方 Archicad JSON API，提供對 **137 個命令**（且不斷增長）的統一工具集訪問，而不會壓垮 AI 的上下文窗口。
-   **100% 本地和私密搜索：** 使用 `sentence-transformers` 和 `faiss-cpu` 完全在您的機器上構建和運行語義搜索索引。數據永遠不會離開您的電腦，也不需要 API 金鑰。
-   **自適應和相關結果：** 搜索使用複雜的「最高分相對閾值」來過濾噪音，只返回與給定查詢最相關的工具。
-   **多實例控制：** 同時連接和管理多個正在運行的 Archicad 實例。
-   **穩健且打包完善：** 設計為具有 `pyproject.toml` 的適當 Python 套件，實現簡單可靠的安裝。

## 安裝與設置

按照以下步驟使伺服器運行並連接到 MCP 客戶端（如 Claude for Desktop）。

### 1. 先決條件

-   **Python 3.12+** 和 **`uv`**：確保您安裝了現代版本的 Python 和 `uv` 套件管理器。您可以使用 `pip install uv` 安裝 `uv`。

-   **Archicad**：需要運行 Archicad 25 或更高版本的實例，其中包含官方 JSON API。

-   **Tapir Add-On（必需）**：[Tapir Archicad Add-On](https://github.com/ENZYME-APD/tapir-archicad-automation) 對於本伺服器的功能**至關重要**。沒有它：
    - 伺服器無法發現正在運行的 Archicad 實例
    - 所有 Tapir 特定命令（80+ 個工具）將失敗
    - 只有有限的官方 API 命令子集可以工作
    
    **安裝指南：** 請遵循 [Tapir 安裝說明](https://github.com/ENZYME-APD/tapir-archicad-automation#installation)，為您的 Archicad 版本下載並安裝 Add-On。

-   **MCP 客戶端**：可以託管 MCP 伺服器的應用程式，例如：
    - [Claude for Desktop](https://www.claude.ai/download)
    - [Gemini CLI](https://github.com/google-gemini/gemini-cli)

### 2. 配置您的 AI 客戶端

這現在是**唯一需要的步驟**。打開您的客戶端的 `config.json` 文件並添加以下配置。此命令是通用的，可以在任何操作系統上使用而無需修改。

-   **macOS：** `~/Library/Application Support/Claude/claude_desktop_config.json`
-   **Windows：** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ArchicadTapir": {
      "command": "uvx",
        "args": [
          "--from",
          "tapir-archicad-mcp",
          "archicad-server"
        ]
    }
  }
}
```

**工作原理：**
`uvx` 命令（`uv` 工具鏈的一部分）是一個強大的實用程式，會自動為您處理整個過程：
1.  AI 客戶端第一次需要該工具時，`uvx` 將從 PyPI 下載最新版本的 `tapir-archicad-mcp`。
2.  它將將其安裝到臨時的隔離環境中。
3.  它將運行伺服器。

## 使用方法

1.  **重啟 Claude for Desktop** 以應用配置更改。
2.  確保至少有一個 Archicad 實例（帶有 Tapir）正在運行。
3.  客戶端現在可以訪問一小組核心工具。首先要求它查找正在運行的 Archicad 實例：

    > "你能檢查我正在運行哪些 Archicad 專案嗎？"

    AI 將運行 `discovery_list_active_archicads` 並報告活動實例及其 `port` 號。

4.  現在，陳述您的主要目標。例如：

    > "好的，使用端口 12345，從專案中獲取所有牆元素。"

5.  AI 現在將執行兩步 `discover`/`call` 工作流程：
    *   **首先，它將調用 `archicad_discover_tools`**，查詢如 `"get all wall elements"`。伺服器的語義搜索將發現最佳匹配是 `elements_get_elements_by_type` 工具。
    *   **其次，它將調用 `archicad_call_tool`**，使用它剛剛發現的 `name="elements_get_elements_by_type"`，並構建必要的 `arguments`（包括 `port` 和帶有 `elementType="Wall"` 的 `params`）。
    *   最終結果將返回給您。

## 工作原理

伺服器通過分層架構運行：

-   **AI 代理（例如 Claude）：** 與用戶交互並決定調用哪些工具。
-   **MCP 客戶端（例如 Claude for Desktop）：** 管理伺服器進程和通訊。
-   **MCP 伺服器（本專案）：** 提供 Archicad 自動化 API 的智能抽象層，公開簡單的 `discover`/`call` 介面。
-   **`multiconn_archicad` 庫：** 處理與 Archicad 實例的底層通訊的基礎 Python 庫。
-   **Tapir Add-On（必需）：** 使用 80+ 個額外命令擴展 Archicad 的內建 JSON API，並啟用實例發現。
-   **Archicad JSON API：** Archicad 的官方 JSON 自動化介面。

> **注意：** Tapir Add-On 是關鍵依賴項。它不僅提供額外的命令，還使伺服器能夠發現和識別正在運行的 Archicad 實例。沒有它，伺服器將無法正常運行。

## 貢獻

歡迎貢獻！請隨時提交 issue 或打開 pull request。

## 授權條款

本專案根據 MIT 授權條款授權。詳見 [LICENSE](./LICENSE) 文件。
