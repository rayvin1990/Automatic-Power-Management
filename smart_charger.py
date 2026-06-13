"""
米家智能插座自动充电管理器（云端API版 - 二维码登录）
============================================
通过小米云端API控制：低电通电充电 → 满电自动断电

使用方法：
  python smart_charger.py
"""

import time
import logging
import sys
import os
import json
import atexit
import ctypes
from datetime import datetime

import requests
import psutil

try:
    from Crypto.Cipher import ARC4
except ModuleNotFoundError:
    from Cryptodome.Cipher import ARC4

from colorama import Fore, Style, init

# 导入 token_extractor 中已验证的云端连接器
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import token_extractor as _te

# 覆盖 token_extractor 的 args
_te.args = type('Args', (), {
    'non_interactive': True,
    'host': None,
    'log_level': 'CRITICAL',
    'output': None,
    'server': None,
})()

# 覆盖 print_if_interactive，让它在我们的场景下也能输出
_te.print_if_interactive = lambda value="": print(value)

from token_extractor import QrCodeXiaomiCloudConnector, XiaomiCloudConnector

init(autoreset=True)

# ==================== 配置加载 ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(SCRIPT_DIR, "config.example.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, ".mi_credentials.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "charger_log.txt")
QR_IMAGE_PATH = os.path.join(SCRIPT_DIR, "qr_login.jpg")

# load_config() runs before setup_logging(), so this placeholder prevents first-run
# config warnings from crashing the script when config.json is missing or invalid.
logger = logging.getLogger(__name__)


def load_config():
    """从 config.json 加载用户配置，不存在则使用默认值"""
    defaults = {
        "plug_did": "",
        "plug_model": "",
        "server": "cn",
        "charge_on_threshold": 20,
        "charge_off_threshold": 80,
        "check_interval": 600,
    }
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            logger.warning(f"⚠️ 未找到 config.json，请复制 config.example.json 为 config.json 并填写你的设备信息")
        return defaults
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user_cfg = json.load(f)
        defaults.update(user_cfg)
        return defaults
    except Exception as e:
        logger.warning(f"⚠️ 读取 config.json 失败: {e}，使用默认配置")
        return defaults


_cfg = load_config()
# ==================================================

# 全局引用，关机时使用
_connector_ref = None
_shutting_down = False
_manual_stop_requested = False
_windows_ctrl_handler_ref = None


def validate_config(cfg):
    """校验配置，避免用空 DID 或异常阈值控制真实插座。"""
    did = str(cfg.get("plug_did", "")).strip()
    if not did or did == "你的设备DID":
        raise ValueError("config.json 中的 plug_did 不能为空，请填写真实设备 DID")

    try:
        cfg["charge_on_threshold"] = int(cfg["charge_on_threshold"])
        cfg["charge_off_threshold"] = int(cfg["charge_off_threshold"])
        cfg["check_interval"] = int(cfg["check_interval"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("充电阈值、断电阈值和检测间隔必须是整数") from e

    if not 0 <= cfg["charge_on_threshold"] < cfg["charge_off_threshold"] <= 100:
        raise ValueError("阈值必须满足 0 <= charge_on_threshold < charge_off_threshold <= 100")

    if cfg["check_interval"] <= 0:
        raise ValueError("check_interval 必须大于 0 秒")

    return cfg


def setup_logging():
    handlers = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
    # pythonw.exe 或隐藏窗口下 sys.stdout 可能为 None，避免崩溃
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    # force=True 确保覆盖 token_extractor 等模块可能已做的 logging 配置
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True
    )
    logger = logging.getLogger(__name__)
    # token_extractor 导入时可能污染了 __main__ 日志器，强制修正
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = True
    return logger


logger = setup_logging()

try:
    _cfg = validate_config(_cfg)
except ValueError as e:
    logger.error(f"❌ 配置错误: {e}")
    raise SystemExit(1) from e

PLUG_DID = _cfg["plug_did"]                 # 设备ID（必填）
PLUG_MODEL = _cfg["plug_model"]              # 设备型号
CHARGE_ON_THRESHOLD = _cfg["charge_on_threshold"]   # 低于 → 开始充电 (%)
CHARGE_OFF_THRESHOLD = _cfg["charge_off_threshold"]  # 高于 → 停止充电 (%)
CHECK_INTERVAL = _cfg["check_interval"]       # 检测间隔（秒）
SERVER = _cfg["server"]                       # 服务器区域


# ==================================================
# 关机/注销时自动断电
# ==================================================

def _emergency_turn_off_plug():
    """紧急断电：关机/注销时快速关闭插座（仅在插座通电时执行）"""
    global _connector_ref, _shutting_down
    if _manual_stop_requested:
        return
    if _shutting_down:
        return
    _shutting_down = True

    log_msg = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔴 检测到关机/注销事件，检查插座状态..."

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception:
        pass

    print(log_msg)

    # 快速判断：如果笔记本没有在充电，说明插座本身就是断电的
    try:
        bat = psutil.sensors_battery()
        if bat and not bat.power_plugged:
            skip_msg = f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ 笔记本未在充电（插座已断电），无需操作"
            print(skip_msg)
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(skip_msg + "\n")
            except Exception:
                pass
            return
    except Exception:
        pass

    # 笔记本正在充电 → 插座是通电的，需要断电
    turn_off_msg = f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 插座正在通电中，执行关机断电..."
    print(turn_off_msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(turn_off_msg + "\n")
    except Exception:
        pass

    connector = _connector_ref
    if connector is None:
        connector = load_credentials()
    if connector is None:
        err = "❌ 无法获取登录凭证，跳过关机断电"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(err + "\n")
        except Exception:
            pass
        return

    try:
        url = XiaomiCloudConnector.get_api_url(SERVER) + "/miotspec/prop/set"
        data = {
            "datasource": "property",
            "params": [{"did": PLUG_DID, "siid": 2, "piid": 1, "value": False}]
        }
        params = {"data": json.dumps(data)}
        result = connector.execute_api_call_encrypted(url, params)
        success_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 关机断电成功！"
        if result and result.get("code") == 0:
            print(success_msg)
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(success_msg + "\n")
            except Exception:
                pass
        else:
            err_msg = f"[{datetime.now().strftime('%H:%M:%S')}] 关机断电失败: {result}"
            print(err_msg)
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(err_msg + "\n")
            except Exception:
                pass
    except Exception as e:
        err_msg = f"关机断电异常: {e}"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(err_msg + "\n")
        except Exception:
            pass


def _windows_ctrl_handler(ctrl_type):
    """Windows 控制台事件处理函数（关机/注销/关闭窗口）"""
    # CTRL_SHUTDOWN_EVENT = 6, CTRL_LOGOFF_EVENT = 5, CTRL_CLOSE_EVENT = 2
    if ctrl_type in (2, 5, 6):
        _emergency_turn_off_plug()
        return True
    return False


def register_shutdown_handler():
    """注册 Windows 关机/注销事件处理"""
    global _windows_ctrl_handler_ref
    try:
        # 方式1: ctypes 设置控制台控制处理器
        CTRL_HANDLER_TYPE = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
        handler = CTRL_HANDLER_TYPE(_windows_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
        # 保持模块级引用，防止 ctypes 回调被垃圾回收。
        _windows_ctrl_handler_ref = handler

        # 方式2: atexit 作为后备
        atexit.register(_emergency_turn_off_plug)

        logger.info("🛡️ 关机自动断电保护已启用")
    except Exception as e:
        logger.warning(f"⚠️ 关机事件注册失败（atexit后备仍可用）: {e}")
        atexit.register(_emergency_turn_off_plug)


def save_credentials(connector):
    """保存认证信息"""
    creds = {
        "userId": connector.userId,
        "ssecurity": connector._ssecurity,
        "serviceToken": connector._serviceToken,
        "login_time": datetime.now().isoformat(),
    }
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f)
    logger.info("✅ 登录凭证已缓存到 " + CREDENTIALS_FILE)


def load_credentials():
    """加载已保存的认证信息"""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            creds = json.load(f)
        connector = QrCodeXiaomiCloudConnector()
        connector.userId = creds["userId"]
        connector._ssecurity = creds["ssecurity"]
        connector._serviceToken = creds["serviceToken"]
        # 快速验证
        test = connector.get_homes(SERVER)
        if test is not None:
            logger.info("✅ 已加载缓存的登录凭证")
            return connector
        else:
            logger.warning("⚠️ 缓存凭证已过期")
            os.remove(CREDENTIALS_FILE)
            return None
    except Exception as e:
        logger.warning(f"⚠️ 加载缓存失败: {e}")
        if os.path.exists(CREDENTIALS_FILE):
            os.remove(CREDENTIALS_FILE)
        return None


def set_device_power(connector, did, state_on=True):
    """通过云端API控制插座开关"""
    action_text = "开启" if state_on else "关闭"
    logger.info(f"🔌 正在{action_text}插座电源...")

    # 正确的API路径和数据格式（MiService datasource 格式）
    url = XiaomiCloudConnector.get_api_url(SERVER) + "/miotspec/prop/set"
    data = {
        "datasource": "property",
        "params": [{"did": did, "siid": 2, "piid": 1, "value": state_on}]
    }
    params = {"data": json.dumps(data)}

    result = connector.execute_api_call_encrypted(url, params)

    if result is not None:
        code = result.get("code", -1)
        # 检查每个参数的执行结果
        results = result.get("result", [])
        if isinstance(results, list) and len(results) > 0:
            item_code = results[0].get("code", -1)
            if code == 0 and item_code == 0:
                icon = "✅" if state_on else "🔴"
                text = "通电！开始充电 ⚡" if state_on else "断电！停止充电 🔋"
                logger.info(f"{icon} 插座{text}")
                return True
            else:
                logger.error(f"❌ 控制失败: item_code={item_code}, result={result}")
                return False
        elif code == 0:
            icon = "✅" if state_on else "🔴"
            text = "通电！开始充电 ⚡" if state_on else "断电！停止充电 🔋"
            logger.info(f"{icon} 插座{text}")
            return True
        else:
            logger.error(f"❌ 控制失败: {result}")
            return False
    else:
        logger.error("❌ API无响应")
        return False


def get_device_power(connector, did):
    """查询插座当前开关状态（True=通电, False=断电）"""
    try:
        url = XiaomiCloudConnector.get_api_url(SERVER) + "/v2/device/control"

        # MIoT spec: 读取 piid=1 (power)
        params = {
            "data": json.dumps({
                "did": did,
                "siid": 2,
                "aiid": 2,
                "in": [{"piid": 1}]
            })
        }
        result = connector.execute_api_call_encrypted(url, params)
        if result and result.get("code") == 0:
            # 解析返回值
            out = result.get("out", result.get("result", []))
            if isinstance(out, list) and len(out) > 0:
                val = out[0].get("value", out[0]) if isinstance(out[0], dict) else out[0]
                return bool(val)
    except Exception:
        pass

    # 旧版查询方式
    try:
        params2 = {
            "data": json.dumps({
                "did": did,
                "method": "get_prop",
                "params": ["power"]
            })
        }
        result2 = connector.execute_api_call_encrypted(url, params2)
        if result2 and result2.get("code") == 0:
            val = result2.get("result", "")
            if isinstance(val, list) and len(val) > 0:
                return val[0] == "on"
            elif isinstance(val, str):
                return val == "on"
    except Exception:
        pass

    # 无法确认状态时，默认返回 True（安全假设：通电中）
    return True


def get_battery_info():
    """获取笔记本电池信息"""
    bat = psutil.sensors_battery()
    if bat is None:
        raise RuntimeError("无法检测到电池信息")
    return {
        "percent": bat.percent,
        "plugged": bat.power_plugged,
        "secsleft": bat.secsleft,
    }


def qr_login():
    """二维码扫码登录（完整流程）"""
    print()
    print(f"{Fore.CYAN}{'='*58}")
    print(f"  📱 二维码扫码登录小米账号")
    print(f"{'='*58}{Style.RESET_ALL}")
    print()

    connector = QrCodeXiaomiCloudConnector()

    # Step 1: 获取二维码
    logger.info("正在获取登录二维码...")
    if not connector.login_step_1():
        logger.error("❌ 无法获取登录信息")
        return None

    # Step 2: 下载并保存二维码图片
    qr_url = connector._qr_image_url
    login_url = connector._login_url
    logger.info("正在下载二维码图片...")

    try:
        img_resp = connector._session.get(qr_url)
        if img_resp.status_code == 200:
            with open(QR_IMAGE_PATH, "wb") as f:
                f.write(img_resp.content)
            logger.info(f"📷 二维码已保存: {QR_IMAGE_PATH}")

            # 自动打开图片
            try:
                os.startfile(QR_IMAGE_PATH)
                logger.info("✅ 二维码图片已自动打开")
            except Exception:
                logger.warning("⚠️ 无法自动打开，请手动打开上面的图片文件")
        else:
            logger.warning("⚠️ 无法下载二维码图片")
    except Exception as e:
        logger.warning(f"⚠️ 二维码图片处理失败: {e}")

    # 打印登录链接（备选方案）
    print()
    print(f"{Fore.CYAN}{'='*58}")
    print(f"  📱 登录方式（二选一）:")
    print(f"{'='*58}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}方式一: 用手机浏览器打开下面链接，点「批准」:")
    print(f"    {Fore.YELLOW}{login_url}")
    print(f"{Style.RESET_ALL}  {Fore.GREEN}方式二: 用手机米家APP扫描弹出的二维码图片")
    print(f"    {Fore.YELLOW}二维码路径: {QR_IMAGE_PATH}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*58}{Style.RESET_ALL}")
    print()

    # Step 3: 等待扫码结果（长轮询）
    logger.info("⏳ 等待扫码中...（请在手机上操作）")

    if not connector.login_step_3():
        logger.error("❌ 扫码登录失败（超时或取消）")
        return None

    # Step 4: 获取 serviceToken
    if not connector.login_step_4():
        logger.error("❌ 无法获取服务令牌")
        return None

    logger.info("✅ 扫码登录成功!")
    save_credentials(connector)
    return connector


def main():
    global _connector_ref, _manual_stop_requested

    print()
    print(f"{Fore.CYAN}{'='*58}")
    print("  ⚡ 米家智能插座自动充电管理器")
    print(f"{'='*58}{Style.RESET_ALL}")
    print(f"   目标插座: AlmLbs Smart Socket (WiFi)")
    print(f"   设备ID  : {PLUG_DID}")
    print(f"   充电阈值: <{CHARGE_ON_THRESHOLD}% 开启")
    print(f"   断电阈值: >{CHARGE_OFF_THRESHOLD}% 关闭")
    print(f"   检测间隔: {CHECK_INTERVAL}秒")
    print(f"{'='*58}")
    print()

    # 尝试加载缓存凭证
    connector = load_credentials()

    if connector is None:
        connector = qr_login()
        if connector is None:
            logger.error("❌ 无法登录，程序退出")
            print("按回车退出...")
            try:
                input()
            except EOFError:
                pass
            return

    # 测试云端连接
    print()
    logger.info("🧪 测试云端连接...")

    # 保存全局引用（关机时使用）
    _connector_ref = connector

    # 注册关机自动断电处理
    register_shutdown_handler()

    homes = connector.get_homes(SERVER)
    plug_found = False
    if homes and "result" in homes and "homelist" in homes["result"]:
        for h in homes["result"]["homelist"]:
            devices = connector.get_devices(SERVER, h["id"], connector.userId)
            if devices and "result" in devices and devices["result"].get("device_info"):
                for dev in devices["result"]["device_info"]:
                    if str(dev.get("did")) == PLUG_DID:
                        plug_found = True
                        online_status = "在线" if dev.get("isOnline") else "离线"
                        logger.info(f"✅ 找到插座: {dev.get('name', 'AlmLbs')} ({online_status})")
                        break
            if plug_found:
                break

    if not plug_found:
        logger.warning("⚠️ 未在设备列表中找到插座，但仍将尝试控制")

    # 查询当前电池状态
    try:
        battery = get_battery_info()
        logger.info(f"🔋 当前电量: {battery['percent']}% | 充电中: {'是' if battery['plugged'] else '否'}")
    except Exception as e:
        logger.error(f"❌ 无法读取电池: {e}")
        return

    # 进入监控循环
    print()
    logger.info("🔄 开始监控电池电量...")
    logger.info("   按 Ctrl+C 可随时停止\n")

    last_action = None
    check_count = 0

    while True:
        try:
            battery = get_battery_info()
            pct = battery["percent"]
            plugged = battery["plugged"]

            need_on = pct <= CHARGE_ON_THRESHOLD
            need_off = pct >= CHARGE_OFF_THRESHOLD

            action = None

            if need_off and plugged and last_action != "off":
                if set_device_power(connector, PLUG_DID, False):
                    action = "off"
            elif need_on and not plugged and last_action != "on":
                if set_device_power(connector, PLUG_DID, True):
                    action = "on"

            if action:
                last_action = action
            elif need_off and not plugged:
                last_action = "off"
            elif need_on and plugged:
                last_action = "on"

            # 状态显示
            status_icon = "🔋" if not plugged else "⚡"
            charge_text = "充电中" if plugged else "未充电"
            action_hint = ""
            if need_off and plugged:
                action_hint = " → 即将断电"
            elif need_on and not plugged:
                action_hint = " → 即将通电"

            now_str = datetime.now().strftime("%H:%M:%S")
            line = f"[{now_str}] {status_icon} 电量: {pct:3}% | {charge_text}{action_hint}"
            print(line)

            # 每6次检测（约1小时）写一次日志，便于确认脚本存活
            check_count += 1
            if check_count % 6 == 1:
                logger.info(f"💓 存活检测 | 电量: {pct}% | {charge_text}{action_hint}")

        except KeyboardInterrupt:
            _manual_stop_requested = True
            logger.info("\n\n🛑 手动停止监控")
            break
        except Exception as e:
            logger.error(f"监控出错: {e}", exc_info=True)

        time.sleep(CHECK_INTERVAL)

    print()
    logger.info("👋 程序已退出")


if __name__ == "__main__":
    main()
