"""
关机自动断电脚本（独立版）
==========================
电脑关机/重启/注销时自动关闭米家智能插座

由 Windows 计划任务调用，不需要 smart_charger.py 运行
仅在笔记本正在充电（插座通电）时才执行断电操作
"""

import sys
import os
import json
import time
from datetime import datetime

# 路径配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, ".mi_credentials.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "charger_log.txt")
SERVER = "cn"

# 从 config.json 读取 PLUG_DID
PLUG_DID = ""
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            _cfg = json.load(f)
        PLUG_DID = _cfg.get("plug_did", "")
        SERVER = _cfg.get("server", "cn")
    except Exception:
        pass

# 添加 token_extractor 路径
sys.path.insert(0, SCRIPT_DIR)
import token_extractor as _te
_te.args = type('Args', (), {
    'non_interactive': True,
    'host': None,
    'log_level': 'CRITICAL',
    'output': None,
    'server': None,
})()
from token_extractor import QrCodeXiaomiCloudConnector, XiaomiCloudConnector


def log(msg):
    """写入日志"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_laptop_charging():
    """检测笔记本是否在充电（True=充电中/插座通电, False=未充电/插座断电）"""
    try:
        import psutil
        bat = psutil.sensors_battery()
        if bat is not None:
            return bat.power_plugged
    except Exception:
        pass
    # 无法检测时，默认假设在充电（安全假设，确保断电）
    return True


def turn_off_plug():
    """关闭插座电源（仅在笔记本充电中/插座通电时执行）"""
    # 先快速判断：笔记本没在充电 → 插座本来就是断电的
    if not is_laptop_charging():
        log("⏭️ 笔记本未在充电（插座已断电），无需操作")
        return True

    # 笔记本正在充电 → 需要断电
    log("🔌 笔记本正在充电（插座通电中），执行关机断电...")

    if not os.path.exists(CREDENTIALS_FILE):
        log("❌ 关机断电失败: 未找到登录凭证")
        return False

    try:
        with open(CREDENTIALS_FILE) as f:
            creds = json.load(f)
    except Exception as e:
        log(f"❌ 关机断电失败: 读取凭证出错 - {e}")
        return False

    try:
        connector = QrCodeXiaomiCloudConnector()
        connector.userId = str(creds["userId"])  # 确保 userId 为字符串
        connector._ssecurity = creds["ssecurity"]
        connector._serviceToken = creds["serviceToken"]

        url = XiaomiCloudConnector.get_api_url(SERVER) + "/miotspec/prop/set"
        data = {
            "datasource": "property",
            "params": [{"did": PLUG_DID, "siid": 2, "piid": 1, "value": False}]
        }
        params = {"data": json.dumps(data)}
        result = connector.execute_api_call_encrypted(url, params)

        if result and result.get("code") == 0:
            log("✅ 关机断电成功！")
            return True

        log(f"⚠️ 关机断电结果: {result}")
        return False

    except Exception as e:
        log(f"❌ 关机断电异常: {e}")
        return False


if __name__ == "__main__":
    log("🔴 检测到关机事件，检查插座状态...")
    success = turn_off_plug()
    if success:
        log("👋 插座已处理，电脑可以安全关机")
    else:
        log("⚠️ 插座断电未成功，请手动检查")
