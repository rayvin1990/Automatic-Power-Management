# ⚡ Mi Smart Plug Auto Charger

米家智能插座自动充电管理器 —— 低电量自动通电、满电自动断电，保护笔记本电池寿命。

## ✨ 功能特性

- 🔋 **自动充放电管理**：电量低于阈值自动通电充电，高于阈值自动断电
- 📱 **二维码扫码登录**：无需输入密码，手机米家APP扫码即可
- 🛡️ **关机自动断电**：电脑关机/重启/注销时自动关闭插座（三层保障）
- 🔄 **凭证缓存**：登录一次，长期有效，过期自动重新登录
- 🪟 **开机自启**：VBS 静默启动，后台运行无干扰
- 💓 **存活检测**：每小时写入心跳日志，确认脚本运行中

## 📋 前提条件

- Windows 笔记本电脑
- 米家智能插座（WiFi版）
- Python 3.8+
- 插座和电脑在同一小米账号下

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install psutil colorama requests pycryptodome Pillow
```

### 2. 配置设备信息

复制配置模板并填写你的插座信息：

```bash
copy config.example.json config.json
```

编辑 `config.json`：

```json
{
    "plug_did": "你的设备DID",
    "plug_model": "你的设备型号",
    "server": "cn",
    "charge_on_threshold": 20,
    "charge_off_threshold": 80,
    "check_interval": 600
}
```

> 💡 如何获取 `plug_did` 和 `plug_model`？运行 `python token_extractor.py` 登录后可查看所有设备信息。

### 3. 运行

```bash
python smart_charger.py
```

首次运行会弹出二维码，用手机米家APP扫码登录即可。

### 4. 设置开机自启（可选）

双击 `启动智能充电(静默).vbs` 即可后台启动。将此 VBS 文件复制到 Windows 启动文件夹实现开机自启：

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

### 5. 注册关机断电任务（可选，需管理员权限）

右键 `注册关机断电任务.bat` → 以管理员身份运行

## ⚙️ 配置说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `plug_did` | 插座设备ID（必填） | - |
| `plug_model` | 插座设备型号 | - |
| `server` | 小米服务器区域 | `cn` |
| `charge_on_threshold` | 低电量阈值（%） | `20` |
| `charge_off_threshold` | 高电量阈值（%） | `80` |
| `check_interval` | 检测间隔（秒） | `600` |

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `smart_charger.py` | 主程序：电池监控 + 自动充放电 |
| `shutdown_turn_off_plug.py` | 独立关机脚本：由计划任务调用 |
| `token_extractor.py` | 小米云端API连接器（源自 [PiotrMachowski/Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)） |
| `config.json` | 用户配置（**不入库**） |
| `config.example.json` | 配置模板 |
| `启动智能充电(静默).vbs` | VBS 静默启动脚本 |
| `注册关机断电任务.bat` | 注册Windows关机计划任务 |

## 🔒 安全说明

- **`config.json`** 和 **`.mi_credentials.json`** 已在 `.gitignore` 中排除，**不会上传到仓库**
- 登录凭证缓存在本地 `.mi_credentials.json`，仅存储 `userId`、`ssecurity`、`serviceToken`
- 插座状态通过 `psutil.sensors_battery().power_plugged` 本地判断，减少云端API调用

## 🏗️ 工作原理

```
┌──────────────────────────────────────────┐
│         每 10 分钟检测一次电池状态          │
├──────────────────────────────────────────┤
│  电量 ≤ 20% 且 未充电  →  插座通电（开始充电） │
│  电量 ≥ 80% 且 充电中  →  插座断电（停止充电） │
│  其他情况              →  不操作            │
└──────────────────────────────────────────┘

关机保护（三层）：
  1. ctypes 控制台事件处理器 → 捕获关机信号
  2. atexit 回调 → Python正常退出时触发
  3. Windows计划任务 → 调用 shutdown_turn_off_plug.py
```

## 🤝 贡献

欢迎 PR！可以改进的方向：

- [ ] 支持 macOS / Linux
- [ ] 桌面通知（电量变化时提醒）
- [ ] Web UI 管理面板
- [ ] 多插座支持
- [ ] 更智能的充电策略（基于时间段、使用习惯等）

## 📄 许可证

MIT License

## 🙏 致谢

- [PiotrMachowski/Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor) - 小米云端API连接器
