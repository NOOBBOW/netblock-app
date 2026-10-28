# -*- coding: utf-8 -*-
"""
路由器设备黑名单控制 App（可输入版）
用户可在界面填写：路由器 IP / 用户名 / 密码 / 类型 / 目标 MAC / 备注名
支持本地保存，下次自动读取。
"""

import os
import json
import threading

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
import requests


# 配置文件路径（安卓 / 桌面通用）
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".netblock_config.json")

DEFAULT_CONFIG = {
    "router_ip":   "192.168.1.1",
    "router_user": "admin",
    "router_pass": "",
    "router_type": "openwrt",          # openwrt / tplink
    "target_mac":  "AA:BB:CC:DD:EE:FF",
    "target_name": "kid-phone",
}


class BlacklistApp(App):
    def build(self):
        self.title = "家庭网络控制"
        self.cfg = self._load_config()

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # ---------- 可滚动表单 ----------
        scroll = ScrollView(size_hint=(1, 0.7))
        form = GridLayout(cols=2, spacing=8, size_hint_y=None, padding=5)
        form.bind(minimum_height=form.setter("height"))

        # 输入控件
        self.in_ip   = self._add_row(form, "路由器 IP",   self.cfg["router_ip"])
        self.in_user = self._add_row(form, "用户名",      self.cfg["router_user"])
        self.in_pass = self._add_row(form, "密码",        self.cfg["router_pass"], password=True)

        # 类型下拉
        form.add_widget(Label(text="路由器类型", size_hint_y=None, height=45))
        self.in_type = Spinner(
            text=self.cfg["router_type"],
            values=("openwrt", "tplink"),
            size_hint_y=None,
            height=45,
        )
        form.add_widget(self.in_type)

        self.in_mac  = self._add_row(form, "目标 MAC",    self.cfg["target_mac"])
        self.in_name = self._add_row(form, "备注名",      self.cfg["target_name"])

        scroll.add_widget(form)

        # ---------- 状态栏 ----------
        self.status = Label(
            text="填写信息后点击下方按钮",
            font_size="16sp",
            size_hint=(1, 0.12),
            halign="center",
            valign="middle",
        )
        self.status.bind(size=lambda i, v: setattr(i, "text_size", (v[0] - 20, None)))

        # ---------- 操作按钮 ----------
        btns = BoxLayout(size_hint=(1, 0.18), spacing=10)

        self.btn_block = Button(
            text="🚫 禁止上网",
            font_size="18sp",
            background_color=(0.85, 0.2, 0.2, 1),
        )
        self.btn_block.bind(on_press=lambda *_: self.start_action(block=True))

        self.btn_unblock = Button(
            text="✅ 恢复上网",
            font_size="18sp",
            background_color=(0.2, 0.65, 0.3, 1),
        )
        self.btn_unblock.bind(on_press=lambda *_: self.start_action(block=False))

        btns.add_widget(self.btn_block)
        btns.add_widget(self.btn_unblock)

        root.add_widget(scroll)
        root.add_widget(self.status)
        root.add_widget(btns)
        return root

    # ---------- 表单工具 ----------
    def _add_row(self, parent, label_text, default_value, password=False):
        parent.add_widget(Label(text=label_text, size_hint_y=None, height=45))
        ti = TextInput(
            text=str(default_value),
            multiline=False,
            password=password,
            size_hint_y=None,
            height=45,
            font_size="16sp",
        )
        parent.add_widget(ti)
        return ti

    # ---------- 配置读写 ----------
    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                # 补齐缺失项
                for k, v in DEFAULT_CONFIG.items():
                    cfg.setdefault(k, v)
                return cfg
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)

    def _save_config(self):
        data = {
            "router_ip":   self.in_ip.text.strip(),
            "router_user": self.in_user.text.strip(),
            "router_pass": self.in_pass.text,
            "router_type": self.in_type.text.strip(),
            "target_mac":  self.in_mac.text.strip().upper(),
            "target_name": self.in_name.text.strip(),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"⚠ 保存配置失败: {e}")
        return data

    # ---------- 读取当前表单值（每次操作实时取值） ----------
    def _current(self):
        return {
            "ip":   self.in_ip.text.strip(),
            "user": self.in_user.text.strip(),
            "pass": self.in_pass.text,
            "type": self.in_type.text.strip(),
            "mac":  self.in_mac.text.strip().upper(),
            "name": self.in_name.text.strip(),
        }

    # ---------- 通用调度 ----------
    def start_action(self, block: bool):
        cfg = self._save_config()

        # 简单校验
        if not cfg["router_ip"] or not cfg["target_mac"]:
            self.set_status("❌ 请填写路由器 IP 和目标 MAC")
            return

        self._set_busy(True)
        self.set_status("正在连接路由器..." if block else "正在移除黑名单...")
        threading.Thread(target=self._run, args=(block, cfg), daemon=True).start()

    def _run(self, block: bool, cfg: dict):
        try:
            if cfg["type"] == "openwrt":
                ok, msg = self._openwrt(cfg, "block" if block else "unblock")
            elif cfg["type"] == "tplink":
                ok, msg = self._tplink(cfg, "block" if block else "unblock")
            else:
                ok, msg = False, f"未实现的路由器类型: {cfg['type']}"

            if ok:
                tip = "已成功屏蔽" if block else "已恢复上网"
                self.set_status(f"✅ {tip}\n{cfg['mac']}")
            else:
                self.set_status(f"❌ 操作失败\n{msg}")
        except Exception as e:
            self.set_status(f"❌ 异常:\n{e}")
        finally:
            Clock.schedule_once(lambda dt: self._set_busy(False), 0)

    def _set_busy(self, busy: bool):
        self.btn_block.disabled = busy
        self.btn_unblock.disabled = busy

    def set_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", text), 0)

    # ---------- OpenWrt / LuCI ----------
    def _openwrt(self, cfg: dict, action: str):
        s = requests.Session()
        base = f"http://{cfg['ip']}"
        mac = cfg["mac"]

        # 1. 登录
        r = s.post(
            f"{base}/cgi-bin/luci",
            data={"luci_username": cfg["user"], "luci_password": cfg["pass"]},
            timeout=8,
        )
        if r.status_code != 200:
            return False, f"登录失败 HTTP {r.status_code}"

        token = s.cookies.get("sysauth") or s.cookies.get("sysauth_https")
        if not token:
            return False, "未获取登录 Cookie"

        list_url = f"{base}/cgi-bin/luci/admin/network/firewall/macfilter"
        referer = {"Referer": f"{base}/cgi-bin/luci/"}

        if action == "block":
            payload = {"token": token, "mac": mac, "name": cfg["name"]}
            resp = s.post(list_url, data=payload, timeout=8, headers=referer)
            if resp.status_code == 200:
                return True, "OK"
            return False, f"添加失败 HTTP {resp.status_code}"

        else:  # unblock
            rpc_url = f"{base}/cgi-bin/luci/admin/ubus"
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": [token, "firewall", "get_rules", {}],
                }
                r = s.post(rpc_url, json=payload, timeout=8, headers=referer)
                rules = []
                if r.status_code == 200:
                    rules = r.json().get("result", [None, {}])[1].get("rules", [])

                target_id = None
                for rule in rules:
                    if (rule.get("src_mac", "").upper() == mac
                            or rule.get("mac", "").upper() == mac):
                        target_id = rule.get(".name") or rule.get("name")
                        break

                if not target_id:
                    return False, "未找到该 MAC 的黑名单规则"

                del_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "call",
                    "params": [token, "uci", "delete",
                               {"config": "firewall", "section": target_id}],
                }
                r = s.post(rpc_url, json=del_payload, timeout=8, headers=referer)
                if r.status_code != 200:
                    return False, f"删除失败 HTTP {r.status_code}"

                # commit + reload
                s.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 3, "method": "call",
                    "params": [token, "uci", "commit", {"config": "firewall"}],
                }, timeout=8, headers=referer)
                s.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 4, "method": "call",
                    "params": [token, "uci", "apply", {"rollback": False}],
                }, timeout=8, headers=referer)
                return True, "OK"
            except Exception as e:
                return False, f"unblock 异常: {e}"

    # ---------- TP-Link（示例） ----------
    def _tplink(self, cfg: dict, action: str):
        s = requests.Session()
        base = f"http://{cfg['ip']}"
        mac = cfg["mac"]

        r = s.post(
            f"{base}/cgi-bin/luci/;stok=/login?form=login",
            json={"method": "do", "login": {"password": cfg["pass"]}},
            timeout=8,
        )
        stok = r.json().get("stok")
        if not stok:
            return False, "TP-Link 登录失败"

        url = f"{base}/cgi-bin/luci/;stok={stok}/admin/macfilter"

        if action == "block":
            r = s.post(url, json={
                "method": "add",
                "macfilter": {"name": cfg["name"], "mac": mac, "enable": 1},
            }, timeout=8)
            if r.status_code == 200:
                return True, "OK"
            return False, f"添加失败 HTTP {r.status_code}"

        else:  # unblock
            r = s.post(url, json={"method": "get"}, timeout=8)
            items = r.json().get("macfilter", {}).get("table", [])
            target = next(
                (x for x in items if x.get("mac", "").upper() == mac),
                None,
            )
            if not target:
                return False, "黑名单中不存在该 MAC"

            r = s.post(url, json={
                "method": "delete",
                "macfilter": {"name": target.get("name")},
            }, timeout=8)
            if r.status_code == 200:
                return True, "OK"
            return False, f"删除失败 HTTP {r.status_code}"


if __name__ == "__main__":
    BlacklistApp().run()
