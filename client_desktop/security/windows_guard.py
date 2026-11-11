"""
Secure Examination & Proctoring Platform
client_desktop/security/windows_guard.py - Deep OS Hardening via Win32 API
Implements Commercial-Grade Anti-Cheat (Level: Safe Exam Browser / Respondus):
1. Anti-VM & Hypervisor Detection (BIOS, Registry, Virtual MAC OUIs)
2. Low-Level Keyboard Hook (WH_KEYBOARD_LL) suppressing Windows, Alt+Tab, Alt+Esc, Ctrl+Esc, F1-F12
3. Anti-Screen Recording & Capture Blackout (SetWindowDisplayAffinity)
"""

import atexit
import ctypes
from ctypes import wintypes
import logging
import os
import platform
import sys
from typing import Any, Dict, List, Optional, Tuple
import winreg

import psutil

logger = logging.getLogger("WINDOWS_GUARD")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [WINDOWS_GUARD] %(message)s")

# Win32 Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Virtual Keycodes
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_CONTROL = 0x11
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_F1 = 0x70
VK_F12 = 0x7B

LLKHF_EXTENDED = 0x01
LLKHF_ALTDOWN = 0x20

# Display Affinity Constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Known Virtual Machine MAC Address Prefixes (OUI)
VIRTUAL_MAC_PREFIXES = [
    "00:05:69",  # VMware
    "00:0C:29",  # VMware
    "00:50:56",  # VMware
    "08:00:27",  # VirtualBox
    "52:54:00",  # QEMU / KVM
    "00:1C:42",  # Parallels
    "00:15:5D",  # Microsoft Hyper-V
    "00:16:3E",  # Xen
]

# Known VM Keywords in BIOS / System Registry
VM_STRING_PATTERNS = [
    "VMWARE",
    "VIRTUALBOX",
    "VBOX",
    "QEMU",
    "KVM",
    "HYPER-V",
    "VIRTUAL MACHINE",
    "XEN",
    "PARALLELS",
    "BHYVE"
]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class AntiVMDetector:
    """Detects if client is executing inside a Virtual Machine or Hypervisor sandbox."""

    @staticmethod
    def check_bios_registry() -> Tuple[bool, str, Dict[str, str]]:
        """Scans Windows System BIOS Registry keys for hypervisor signatures."""
        details = {}
        if platform.system() != "Windows":
            return False, "Not running on Windows", details

        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS"),
            (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System")
        ]

        for root_key, sub_key in reg_paths:
            try:
                key = winreg.OpenKey(root_key, sub_key)
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    name, val, _ = winreg.EnumValue(key, i)
                    if isinstance(val, str):
                        details[name] = val
                        upper_val = val.upper()
                        for pattern in VM_STRING_PATTERNS:
                            if pattern in upper_val:
                                winreg.CloseKey(key)
                                return True, f"Phát hiện dấu hiệu máy ảo ({pattern}) trong Registry [{name}={val}]", details
                winreg.CloseKey(key)
            except Exception as e:
                logger.debug(f"Could not open reg key {sub_key}: {e}")

        return False, "Phần cứng vật lý hợp lệ (Không phát hiện chuỗi máy ảo)", details

    @staticmethod
    def check_mac_addresses() -> Tuple[bool, str, List[str]]:
        """Inspects network adapter MAC addresses for hypervisor OUI prefixes."""
        found_macs = []
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == psutil.AF_LINK and addr.address:
                        mac_clean = addr.address.upper().replace("-", ":")
                        found_macs.append(mac_clean)
                        for prefix in VIRTUAL_MAC_PREFIXES:
                            if mac_clean.startswith(prefix):
                                return True, f"Phát hiện card mạng ảo ({prefix}) trên giao diện '{iface}' ({mac_clean})", found_macs
        except Exception as e:
            logger.debug(f"Error checking MACs: {e}")

        return False, "Địa chỉ MAC card mạng vật lý hợp lệ", found_macs

    @classmethod
    def evaluate_environment(cls) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Runs comprehensive anti-VM audit.
        Returns:
            Tuple[is_vm: bool, verdict_message: str, audit_data: dict]
        """
        is_vm_reg, msg_reg, bios_details = cls.check_bios_registry()
        if is_vm_reg:
            return True, msg_reg, {"registry": bios_details}

        is_vm_mac, msg_mac, macs = cls.check_mac_addresses()
        if is_vm_mac:
            return True, msg_mac, {"macs": macs}

        return False, "Môi trường hệ thống vật lý an toàn (Bare-metal Verified)", {
            "bios": bios_details,
            "macs": macs
        }


class LowLevelKeyboardGuard:
    """
    Installs WH_KEYBOARD_LL Windows Hook to swallow Windows Key, Alt+Tab, Alt+Esc, Ctrl+Esc, F1-F12.
    Ensures safe unhooking via atexit and explicit uninstall.
    """

    _hook_handle = None
    _hook_proc = None
    _is_installed = False

    @classmethod
    def install_hook(cls) -> bool:
        """Installs the low-level keyboard hook."""
        if cls._is_installed:
            return True

        if platform.system() != "Windows":
            logger.warning("LowLevelKeyboardGuard only supported on Windows.")
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        def _low_level_proc(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                vk = kb.vkCode
                flags = kb.flags

                # 1. Block Windows Key (Left & Right)
                if vk in (VK_LWIN, VK_RWIN):
                    return 1

                # 2. Block Alt + Tab
                if (flags & LLKHF_ALTDOWN) and vk == VK_TAB:
                    return 1

                # 3. Block Alt + Esc
                if (flags & LLKHF_ALTDOWN) and vk == VK_ESCAPE:
                    return 1

                # 4. Block Ctrl + Esc (Start Menu trigger)
                ctrl_pressed = bool(user32.GetKeyState(VK_CONTROL) & 0x8000)
                if ctrl_pressed and vk == VK_ESCAPE:
                    return 1

                # 5. Block Function Keys F1 - F12 (except F11 for Kiosk Fullscreen toggle)
                if (VK_F1 <= vk <= VK_F12) and vk != 0x7A:
                    return 1

            return user32.CallNextHookEx(cls._hook_handle, nCode, wParam, lParam)

        cls._hook_proc = HOOKPROC(_low_level_proc)
        # WH_KEYBOARD_LL is a low-level hook that does not require DLL injection; hMod is 0
        cls._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            cls._hook_proc,
            0,
            0
        )

        if not cls._hook_handle:
            err = kernel32.GetLastError()
            logger.error(f"Failed to install WH_KEYBOARD_LL hook. Error code: {err}")
            return False

        cls._is_installed = True
        logger.info("🛡️ Low-level WH_KEYBOARD_LL Hook successfully installed (Windows key, Alt+Tab, F1-F12 blocked).")
        return True

    @classmethod
    def uninstall_hook(cls) -> None:
        """Safely unhooks the keyboard hook."""
        if cls._hook_handle and cls._is_installed:
            user32 = ctypes.windll.user32
            user32.UnhookWindowsHookEx(cls._hook_handle)
            cls._hook_handle = None
            cls._hook_proc = None
            cls._is_installed = False
            logger.info("🔓 Low-level WH_KEYBOARD_LL Hook cleanly removed.")

    @classmethod
    def is_active(cls) -> bool:
        return cls._is_installed


# Register cleanup at Python process exit
atexit.register(LowLevelKeyboardGuard.uninstall_hook)


class DisplayAffinityGuard:
    """Prevents exam window from being captured or recorded by OBS, Discord, Zoom, Snipping Tool."""

    @staticmethod
    def protect_window(hwnd: int) -> bool:
        """
        Enables WDA_EXCLUDEFROMCAPTURE or WDA_MONITOR on PyQt window handle.
        Window appears pitch black on screen recorders.
        """
        if platform.system() != "Windows" or not hwnd:
            return False

        user32 = ctypes.windll.user32
        if not hasattr(user32, "SetWindowDisplayAffinity"):
            return False

        # Try modern WDA_EXCLUDEFROMCAPTURE first (Win10 2004+)
        res = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if not res:
            # Fallback to WDA_MONITOR
            res = user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR)

        if res:
            logger.info(f"🛡️ Screen Capture Protection ACTIVE on window HWND 0x{hwnd:X} (Window turns black on recording/OBS).")
            return True
        else:
            err = ctypes.windll.kernel32.GetLastError()
            logger.warning(f"Could not set window display affinity on HWND 0x{hwnd:X}. Code: {err}")
            return False

    @staticmethod
    def unprotect_window(hwnd: int) -> bool:
        """Restores normal window capture affinity."""
        if platform.system() != "Windows" or not hwnd:
            return False

        user32 = ctypes.windll.user32
        if hasattr(user32, "SetWindowDisplayAffinity"):
            return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_NONE))
        return False
