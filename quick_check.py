"""
轻量电量检测脚本（单次执行版）
================================
由 Windows 计划任务定期唤醒电脑后调用。
检测电池电量，根据阈值决定是否通电/断电，执行完即退出。

电脑睡眠时，Python 主脚本暂停无法检测。
本脚本配合 Windows 计划任务的 WakeToRun 功能，
定期唤醒电脑做一次快速检测（约3-5秒），然后电脑自动回睡。

使用方法：
  python quick_check.py                # 正常检测
  python quick_check.py --force-on     # 强制通电（无视阈值）
  python quick_check.py --force-off    # 强制断电（无视阈值）
"""

import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
import token_extractor as _te

_te.args = type('Args', (), {
    'non_interactive': True,
    'host': None,
    'log_level': 'CRITICAL',
    'output': None,
    'server': None,
})()

from token_extractor import QrCodeXiaomiCloudConnector, XiaomiCloudConnector

# ==================== 配置加载 ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, ".mi_credentials.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "charger_log.txt")
SERVER = "cn"

CHARGE_ON_THRESHOLD = 20
CHARGE_OFF_THRESHOLD = 80
PLUG_DID = ""

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            _cfg = json.load(f)
        PLUG_DID = _cfg.get("plug_did", "")
        SERVER = _cfg.get("server", "cn")
        CHARGE_ON_THRESHOLD = _cfg.get("charge_on_threshold", 20)
        CHARGE_OFF_THRESHOLD = _cfg.get("charge_off_threshold", 80)
    except Exception:
        pass

# ==================== 日志 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
    force=True
)
logger = logging.getLogger("quick_check")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.propagate = True


def load_credentials():
    """快速加载缓存凭证（不验证，速度优先）"""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            creds = json.load(f)
        connector = QrCodeXiaomiCloudConnector()
        connector.userId = str(creds["userId"])
        connector._ssecurity = creds["ssecurity"]
        connector._serviceToken = creds["serviceToken"]
        return connector
    except Exception as e:
        logger.warning(f"⚠️ 加载凭证失败: {e}")
        return None


def set_device_power(connector, did, state_on):
    """通过云端API控制插座开关"""
    action_text = "通电" if state_on else "断电"
    try:
        url = XiaomiCloudConnector.get_api_url(SERVER) + "/miotspec/prop/set"
        data = {
            "datasource": "property",
            "params": [{"did": did, "siid": 2, "piid": 1, "value": state_on}]
        }
        params = {"data": json.dumps(data)}
        result = connector.execute_api_call_encrypted(url, params)

        if result and result.get("code") == 0:
            icon = "⚡" if state_on else "🔋"
            logger.info(f"🌙 唤醒检测 → {icon} 插座{action_text} | 电量阈值触发")
            return True
        else:
            logger.error(f"❌ 唤醒检测 → {action_text}失败: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ 唤醒检测 → {action_text}异常: {e}")
        return False


def main():
    # 解析命令行
    force_on = "--force-on" in sys.argv
    force_off = "--force-off" in sys.argv

    # 读取电量
    bat = psutil.sensors_battery()
    if bat is None:
        logger.warning("🌙 唤醒检测 → 无法读取电池，跳过")
        return

    pct = bat.percent
    plugged = bat.power_plugged

    # 强制模式
    if force_on or force_off:
        connector = load_credentials()
        if connector and PLUG_DID:
            set_device_power(connector, PLUG_DID, force_on)
        return

    # 阈值判断
    need_on = pct <= CHARGE_ON_THRESHOLD and not plugged
    need_off = pct >= CHARGE_OFF_THRESHOLD and plugged

    if not need_on and not need_off:
        # 无需操作，只写心跳日志
        charge_text = "充电中" if plugged else "未充电"
        logger.info(f"🌙 唤醒检测 → 💓 电量{pct}% | {charge_text} | 无需操作")
        return

    # 需要操作
    connector = load_credentials()
    if connector is None:
        logger.warning("🌙 唤醒检测 → ⚠️ 无登录凭证，无法操作")
        return

    if not PLUG_DID:
        logger.warning("🌙 唤醒检测 → ⚠️ 未配置 plug_did")
        return

    if need_on:
        set_device_power(connector, PLUG_DID, True)
    elif need_off:
        set_device_power(connector, PLUG_DID, False)


if __name__ == "__main__":
    main()
