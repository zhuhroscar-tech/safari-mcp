[![English](https://img.shields.io/badge/English-555555?style=flat)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-555555?style=flat)](README.zh-CN.md)

# safari-mcp

通过 MCP server、CLI 或 Python 库控制 macOS 上真正的 Safari.app。项目使用 Apple 的 JavaScript for Automation（JXA），支持标签页导航、读取页面、执行 JavaScript、按 CSS selector 点击元素和填写表单。

**操作的是你已经登录的浏览器，不是隔离的自动化 profile。** 操作可能影响真实账户和页面。请只连接可信的 agent，并在执行重要操作前确认内容。

## 安装与权限

需要 macOS、Safari 和 Python 3.10+。pip 会安装 MCP 依赖。

```bash
git clone https://github.com/zhuhroscar-tech/safari-mcp.git
cd safari-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

需要开启两项权限：

1. 首次提示时，允许启动命令的终端或应用控制 Safari。也可在**系统设置 → 隐私与安全性 → 自动化**中检查。
2. 在 Safari 设置 → 高级中开启网页开发者功能，再勾选**开发 → 允许来自 Apple 事件的 JavaScript**。页面 JavaScript 操作需要此选项；列出、打开和关闭标签页不需要。

## 连接 MCP host

对于采用 `mcpServers` 配置格式的 host：

```json
{
  "mcpServers": {
    "safari": {
      "command": "/absolute/path/to/safari-mcp/.venv/bin/safari-mcp-server"
    }
  }
}
```

请替换为实际安装的可执行文件路径。服务使用 stdio，提供 `safari_tabs`、`safari_open`、`safari_close`、`safari_read`、`safari_js`、`safari_click`、`safari_fill`、`safari_element_exists` 和 `safari_wait_for`。

## CLI 与 Python

```bash
safari-mcp tabs
safari-mcp open "https://example.com" --new-tab
safari-mcp read --json
safari-mcp read --window 1 --tab 1
```

可指定目标的命令默认操作最前方窗口的当前标签页。窗口和标签页编号从 1 开始；各命令支持哪些定位参数，请查看 `--help`。

```python
from safari_mcp.core import list_tabs, read_page

print(list_tabs())
page = read_page()
print(page.title, page.text[:100])
```

## 能力边界

这是 DOM 自动化，不提供截图或坐标点击，也没有 sandbox、隐私浏览隔离或 Linux/Windows 支持。封装本身不发送遥测，也没有独立的网络客户端，但浏览器导航和页面操作会产生网络请求，并可能改变账户状态。传给 agent 的页面内容受对应 host 的数据处理规则约束。

## 预览与开发

[输出截图](docs/images/example-output.png) · [演示视频](docs/demo.mp4)

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
# 可选：操作真实 Safari，需要浏览器已打开且权限已授予
python tests/e2e_mcp_roundtrip.py
```

[CI](.github/workflows/ci.yml) 检查 mock Safari 交互和打包，不证明真实 Safari 的运行表现。[API 实现](src/safari_mcp/core.py) · [MIT 许可证](LICENSE)
