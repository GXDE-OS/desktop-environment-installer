# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# GXDE Desktop Environment Installer is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# GXDE Desktop Environment Installer.If not,
# see <https://www.gnu.org/licenses/>.

from typing import TypedDict


class ModuleDefinition(TypedDict):
  repo_name: str
  display_name: str
  branch: str


DTK2_ORIGINAL_MODULES: list[ModuleDefinition] = [
  {
    # DTK2-Widget still links against the original DTK2 Core compatibility
    # packages. Build and install them before the remaining DTK2 stack.
    "repo_name": "dtk2core",
    "display_name": "DTK2-Core",
    "branch": "master",
  },
  {
    # DTK2-Widget consumes the generated libgxframeworkdbus development
    # package, so this infrastructure library has to be bootstrapped as part
    # of the original DTK2 phase rather than built with the later infra stage.
    "repo_name": "dde-qt-dbus-factory",
    "display_name": "GXDE Qt D-Bus Factory (DTK2 prerequisite)",
    "branch": "master",
  },
  {
    "repo_name": "dtk2widget",
    "display_name": "DTK2-Widget",
    "branch": "master",
  },
  {
    "repo_name": "gxde-qt5integration",
    "display_name": "DTK2-Widget integration (Qt5)",
    "branch": "master",
  },
]

DTK2_QT6_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "dtk2widget-qt6",
    "display_name": "DTK2-Widget (Qt6 port)",
    "branch": "qt6",
  },
  {
    "repo_name": "gxde-qt6-integration",
    "display_name": "DTK2-Widget integration (Qt6 port)",
    "branch": "qt6",
  },
]

DTK5_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "dtk5common",
    "display_name": "DTK5 Common",
    # dtk5common/master is still the 5.7 line, while the remaining DTK5
    # repositories build the Qt 5 variant from the 6.7 source line.  Use the
    # matching release so libdtkdata contains the configuration keys consumed
    # by dtk5gui (including disableInWindowBlur).
    "branch": "6.7.43",
  },
  {
    "repo_name": "dtklog",
    "display_name": "DTK Log",
    "branch": "master",
  },
  {
    "repo_name": "dtk5core",
    "display_name": "DTK5 Core",
    "branch": "master",
  },
  {
    "repo_name": "dtk5gui",
    "display_name": "DTK5 GUI",
    "branch": "master",
  },
  {
    "repo_name": "dtk5widget",
    "display_name": "DTK5 Widget",
    "branch": "master",
  },
]

DTK6_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "dtk6log",
    "display_name": "DTK6 Log",
    "branch": "master",
  },
  {
    "repo_name": "dtk6core",
    "display_name": "DTK6 Core",
    "branch": "master",
  },
  {
    "repo_name": "dtk6gui",
    "display_name": "DTK6 GUI",
    "branch": "master",
  },
  {
    "repo_name": "dtk6widget",
    "display_name": "DTK6 Widget",
    "branch": "master",
  },
  {
    "repo_name": "dtk6declarative",
    "display_name": "DTK6 Declarative",
    "branch": "master",
  },
  {
    # dde-qt6integration has a hard runtime dependency on the
    # dde-qt6xcb-plugin binary produced by this repository.
    "repo_name": "dde-qt6platform-plugins",
    "display_name": "Deepin Qt6 XCB Platform Plugin (GXDE modified)",
    "branch": "master",
  },
  {
    "repo_name": "qt6integration",
    "display_name": "Deepin Qt6 Integration (GXDE modified)",
    "branch": "master",
  },
]

# gxde-desktop-base is reference-only here. It contains GXDE OS distribution
# configuration for APT, GRUB, systemd, and os-release, so installing it would
# overwrite host-distribution policy rather than just install the desktop.
INFRA_MODULES: list[ModuleDefinition] = [
  {
    # GXDE's Go components use a curated GOPATH rooted at
    # /usr/share/gocode-gxde. Build and install this bootstrap source bundle
    # before gxde-api and the later daemon repositories consume it.
    "repo_name": "golang-gxde-dev",
    "display_name": "GXDE Go Development Sources",
    "branch": "master",
  },
  {
    "repo_name": "gxde-k9",
    "display_name": "GXDE Service Runner",
    "branch": "master",
  },
  {
    "repo_name": "disomaster-qt6",
    "display_name": "DISOMaster (Qt6 port)",
    "branch": "master",
  },
  {
    "repo_name": "gxde-api",
    "display_name": "GXDE API",
    "branch": "master",
  },
  {
    "repo_name": "gxde-desktop-schemas",
    "display_name": "GXDE Desktop Schemas",
    "branch": "master",
  },
  {
    "repo_name": "gxde-network-utils-qt6",
    "display_name": "GXDE Network Utils (Qt6 port)",
    "branch": "master",
  },
  {
    "repo_name": "xdg-desktop-portal-gxde",
    "display_name": "XDG Desktop Portal for GXDE",
    "branch": "master",
  },
]

CORE_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "gxde-account-faces",
    "display_name": "GXDE Account Faces",
    "branch": "master",
  },
  {
    "repo_name": "gxde-icon-theme",
    "display_name": "GXDE Icon Theme",
    "branch": "master",
  },
  {
    "repo_name": "deepin-gtk-theme",
    "display_name": "GXDE GTK Theme",
    "branch": "master",
  },
  {
    "repo_name": "gxde-artwork",
    "display_name": "GXDE Artwork",
    "branch": "master",
  },
  {
    "repo_name": "gxde-wallpapers",
    "display_name": "GXDE Wallpapers",
    "branch": "master",
  },
  {
    "repo_name": "gxde-default-settings",
    "display_name": "GXDE Default Settings",
    "branch": "master",
  },
  {
    "repo_name": "gxde-shell-tools",
    "display_name": "GXDE Shell Tools",
    "branch": "master",
  },
  {
    "repo_name": "gxde-sound-theme",
    "display_name": "GXDE Sound Theme",
    "branch": "master",
  },
  {
    "repo_name": "gxde-polkit-agent",
    "display_name": "GXDE PolicyKit Agent",
    "branch": "master",
  },
  {
    "repo_name": "deepin-daemon",
    "display_name": "GXDE System Daemon",
    "branch": "master",
  },
  {
    "repo_name": "gxde-daemon",
    "display_name": "GXDE Desktop Daemon",
    "branch": "master",
  },
  {
    "repo_name": "startgxde",
    "display_name": "GXDE Session Starter",
    "branch": "master",
  },
  {
    "repo_name": "deepin-menu",
    "display_name": "GXDE Application Menu Service",
    "branch": "master",
  },
  {
    "repo_name": "gxde-dock",
    "display_name": "GXDE Dock",
    "branch": "master",
  },
  {
    "repo_name": "gxde-control-center",
    "display_name": "GXDE Control Center",
    "branch": "master",
  },
  {
    "repo_name": "gxde-app-installer",
    "display_name": "GXDE Application Installer",
    "branch": "master",
  },
  {
    "repo_name": "gxde-app-upgrader",
    "display_name": "GXDE Application Upgrader",
    "branch": "master",
  },
  {
    "repo_name": "gxde-app-uninstaller",
    "display_name": "GXDE Application Uninstaller",
    "branch": "master",
  },
  {
    "repo_name": "gxde-launcher",
    "display_name": "GXDE Launcher",
    "branch": "master",
  },
  {
    "repo_name": "gxde-session-ui",
    "display_name": "GXDE Session UI",
    "branch": "master",
  },
  {
    "repo_name": "gxde-file-manager",
    "display_name": "GXDE File Manager",
    "branch": "char/qt6_migration",
  },
  {
    "repo_name": "gxde-requ",
    "display_name": "GXDE Hot Corners",
    "branch": "master",
  },
  {
    "repo_name": "deepin-screensaver",
    "display_name": "GXDE Screensaver",
    "branch": "master",
  },
  {
    "repo_name": "gxde-time-screensaver",
    "display_name": "GXDE Time Screensaver",
    "branch": "master",
  },
  {
    "repo_name": "gxde-globalmenu-service",
    "display_name": "GXDE Global Menu Service",
    "branch": "master",
  },
  {
    "repo_name": "gxde-top-panel",
    "display_name": "GXDE Top Panel",
    "branch": "master",
  },
  {
    "repo_name": "gxde-compressor",
    "display_name": "GXDE Compressor",
    "branch": "master",
  },
  {
    "repo_name": "gxde-shell-compressor",
    "display_name": "GXDE Shell Compressor Integration",
    "branch": "master",
  },
]

X11_SESSION_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "gxde-kglobalacceld",
    "display_name": "GXDE Global Shortcut Daemon",
    "branch": "master",
  },
  {
    "repo_name": "gxde-kwin",
    "display_name": "GXDE KWin compositor",
    "branch": "5.24",
  },
  {
    "repo_name": "gxde-wm-shim",
    "display_name": "GXDE window manager compatibility shim",
    "branch": "debian12",
  },
]

WAYLAND_SESSION_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "gxde-wlcom",
    "display_name": "GXDE Wayland compositor",
    "branch": "gxde/zhuangzhuang",
  },
  {
    "repo_name": "dde-grand-search",
    "display_name": "GXDE Grand Search",
    "branch": "master",
  },
  {
    "repo_name": "gxde-sni-server",
    "display_name": "GXDE Status Notifier Item Server",
    "branch": "main",
  },
  {
    "repo_name": "gxde-top-panel-plugins",
    "display_name": "GXDE Top Panel Plugins",
    "branch": "d20",
  },
  {
    "repo_name": "gxde-terminal",
    "display_name": "GXDE Terminal",
    "branch": "master",
  },
  {
    "repo_name": "gxde-display-manager",
    "display_name": "GXDE Display Manager",
    "branch": "main",
  },
  {
    "repo_name": "gxde-wayland-session",
    "display_name": "GXDE Wayland Session",
    "branch": "master",
  },
]
