# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = PROJECT_ROOT / "res/installation_scripts/gxde_build_deb.sh"
BUNDLED_XCB_HEADERS = (
  PROJECT_ROOT
  / "res/installation_scripts/compat/qt6-xcb-private-headers/6.10.2"
)
BUNDLED_PATCHES = PROJECT_ROOT / "res/installation_scripts/patches"


class BuildScriptTest(unittest.TestCase):
  def apply_compatibility(
      self,
      candidate: str,
      control_contents: str | None = None,
  ) -> str:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      debian_directory = repository / "debian"
      debian_directory.mkdir()
      control = debian_directory / "control"
      control.write_text(
        control_contents or (
          "Source: test\n"
          "Build-Depends: qt6-wayland-dev, qt6-wayland-dev-tools, "
          "treeland-protocols\n"
        ),
        encoding="utf-8",
      )

      result = subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          f'apt-cache() {{ printf "  Candidate: {candidate}\\n"; }}; '
          "apply_apt_build_dep_compatibility",
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )
      return control.read_text(encoding="utf-8")

  def test_removes_retired_qt6_wayland_tools_dependency(self) -> None:
    control = self.apply_compatibility("(none)")

    self.assertNotIn("qt6-wayland-dev-tools", control)
    self.assertIn("qt6-wayland-dev, treeland-protocols", control)

  def test_keeps_qt6_wayland_tools_dependency_when_available(self) -> None:
    control = self.apply_compatibility("6.9.2-1")

    self.assertIn("qt6-wayland-dev-tools", control)

  def test_removes_complete_multiline_dependency_entry(self) -> None:
    control = self.apply_compatibility(
      "(none)",
      "Source: xdg-desktop-portal-gxde\n"
      "Build-Depends:\n"
      "  qt6-wayland-private-dev,\n"
      "  qt6-wayland-dev-tools,\n"
      "  libpipewire-0.3-dev,\n"
      "Standards-Version: 4.5.0\n",
    )

    self.assertNotIn("qt6-wayland-dev-tools", control)
    self.assertNotIn("\n  \n", control)
    self.assertIn(
      "  qt6-wayland-private-dev,\n"
      "  libpipewire-0.3-dev,\n",
      control,
    )

  def test_repairs_checkout_corrupted_by_older_installer(self) -> None:
    control = self.apply_compatibility(
      "(none)",
      "Source: xdg-desktop-portal-gxde\n"
      "Build-Depends:\n"
      "  qt6-wayland-private-dev,\n"
      "  \n"
      "  libpipewire-0.3-dev,\n"
      "Standards-Version: 4.5.0\n",
    )

    self.assertNotIn("\n  \n", control)
    self.assertIn(
      "  qt6-wayland-private-dev,\n"
      "  libpipewire-0.3-dev,\n",
      control,
    )

  def test_builds_legacy_cgo_bindings_as_gnu17(self) -> None:
    result = subprocess.run(
      [
        "bash",
        "-c",
        'source "$1"; CGO_CFLAGS="-O2 -std=gnu23"; '
        "configure_cgo_compatibility; printf '%s' \"$CGO_CFLAGS\"",
        "build-script-test",
        str(BUILD_SCRIPT),
      ],
      check=True,
      capture_output=True,
      text=True,
    )

    self.assertTrue(result.stdout.endswith("-O2 -std=gnu23 -std=gnu17"))

  def test_accepts_architecture_independent_build_mode(self) -> None:
    result = subprocess.run(
      [
        "bash",
        "-c",
        'source "$1"; parse_args --architecture-independent; '
        "printf '%s %s' \"$BUILD_BIN\" \"$BUILD_ARCH_INDEPENDENT\"",
        "build-script-test",
        str(BUILD_SCRIPT),
      ],
      check=True,
      capture_output=True,
      text=True,
    )

    self.assertEqual("false true", result.stdout)

  def test_normalizes_comma_separated_maintainers(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-desktop-base\n"
        "Section: misc\n"
        "Priority: optional\n"
        "Maintainer: gfdgd xi<3025613752@qq.com>, "
        "shenmo <shenmo@spark-app.store>\n"
        "Standards-Version: 4.5.1\n"
        "Build-Depends: \n"
        " debhelper-compat (= 12),\n",
        encoding="utf-8",
      )

      result = subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          "normalize_debian_maintainer_metadata",
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      self.assertIn(
        "Maintainer: gfdgd xi <3025613752@qq.com>\n",
        updated_control,
      )
      self.assertIn(
        "Uploaders: shenmo <shenmo@spark-app.store>\n",
        updated_control,
      )

  def test_merges_additional_maintainers_into_existing_uploaders(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-default-settings\n"
        "Maintainer: gfdgd xi <3025613752@qq.com>, "
        "sysdev <sysdev@deepin.com>\n"
        "Uploaders: Existing Person <existing@example.com>\n"
        "Build-Depends: debhelper\n",
        encoding="utf-8",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          "normalize_debian_maintainer_metadata",
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      self.assertIn(
        "Maintainer: gfdgd xi <3025613752@qq.com>\n",
        updated_control,
      )
      self.assertIn(
        "Uploaders: sysdev <sysdev@deepin.com>, "
        "Existing Person <existing@example.com>\n",
        updated_control,
      )
      self.assertEqual(updated_control.count("Uploaders:"), 1)

  def test_renames_gxde_iwlwifi_config_to_avoid_kmod_conflict(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-default-settings\n"
        "Maintainer: GXDE <team@example.com>\n",
        encoding="utf-8",
      )
      modprobe_directory = repository / "etc.d/modprobe.d"
      modprobe_directory.mkdir(parents=True)
      legacy_config = modprobe_directory / "iwlwifi.conf"
      legacy_config.write_text(
        "options iwlwifi power_save=0 swcrypto=0\n",
        encoding="utf-8",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="gxde-default-settings"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      renamed_config = modprobe_directory / "gxde-iwlwifi.conf"
      self.assertFalse(legacy_config.exists())
      self.assertEqual(
        "options iwlwifi power_save=0 swcrypto=0\n",
        renamed_config.read_text(encoding="utf-8"),
      )

  def test_metadata_only_keyring_extension_drops_obsolete_build_deps(
      self,
    ) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: dpa-ext-gnomekeyring\n"
        "Maintainer: GXDE <team@example.com>\n"
        "Build-Depends: debhelper, qtbase5-dev, "
        "gxde-polkit-agent-dev, libgnome-keyring-dev\n",
        encoding="utf-8",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="dpa-ext-gnomekeyring"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      self.assertIn("Build-Depends: debhelper (>= 9)\n", updated_control)
      self.assertNotIn("qtbase5-dev", updated_control)
      self.assertNotIn("gxde-polkit-agent-dev", updated_control)
      self.assertNotIn("libgnome-keyring-dev", updated_control)

  def test_legacy_keyring_replaces_retired_cdbs_with_debhelper(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: libgnome-keyring\n"
        "Maintainer: GXDE <team@example.com>\n"
        "Build-Depends: debhelper (>= 9),\n"
        " cdbs (>= 0.4.93~),\n"
        " dh-autoreconf,\n"
        " gnome-pkg-tools (>= 0.10),\n"
        " intltool\n",
        encoding="utf-8",
      )
      (repository / "debian/control.in").write_text(
        (repository / "debian/control").read_text(encoding="utf-8"),
        encoding="utf-8",
      )
      rules = repository / "debian/rules"
      rules.write_text(
        "#!/usr/bin/make -f\n"
        "include /usr/share/cdbs/1/rules/debhelper.mk\n"
        "include /usr/share/cdbs/1/rules/autoreconf.mk\n"
        "include /usr/share/cdbs/1/class/gnome.mk\n",
        encoding="utf-8",
      )
      compatibility_directory = repository / "compat/libgnome-keyring"
      compatibility_directory.mkdir(parents=True)
      shutil.copy2(
        PROJECT_ROOT
        / "res/installation_scripts/compat/libgnome-keyring/debian-rules",
        compatibility_directory / "debian-rules",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="libgnome-keyring"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_rules = rules.read_text(encoding="utf-8")
      updated_control = (repository / "debian/control").read_text(
        encoding="utf-8",
      )
      self.assertIn("dh $@ --with gnome\n", updated_rules)
      self.assertIn("export GPGRT_CONFIG ?= gpgrt-config\n", updated_rules)
      self.assertNotIn("/usr/share/cdbs", updated_rules)
      self.assertNotIn("cdbs (>=", updated_control)
      self.assertNotIn("dh-autoreconf", updated_control)
      self.assertIn("gnome-pkg-tools (>= 0.10)", updated_control)
      self.assertTrue(rules.stat().st_mode & 0o100)

  def test_deepin_daemon_defers_compositor_until_session_selection(
      self,
    ) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: deepin-daemon\n"
        "Maintainer: GXDE <team@example.com>\n"
        "Package: deepin-daemon\n"
        "Depends: network-manager,\n"
        " deepin-wm | deepin-metacity | dde-kwin | gxde-wlcom,\n"
        " gxde-desktop-schemas\n",
        encoding="utf-8",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="deepin-daemon"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      self.assertNotIn("deepin-wm", updated_control)
      self.assertNotIn("gxde-wlcom", updated_control)
      self.assertIn(" gxde-desktop-schemas\n", updated_control)

  def test_startgxde_defers_compositor_until_session_selection(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: startgxde\n"
        "Maintainer: GXDE <team@example.com>\n"
        "Package: startgxde\n"
        "Depends: deepin-daemon,\n"
        " gxde-wm-shim | deepin-metacity | gxde-kwin-neo | gxde-wlcom,\n"
        " gxde-desktop-schemas\n",
        encoding="utf-8",
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="startgxde"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      self.assertNotIn("gxde-wm-shim", updated_control)
      self.assertNotIn("gxde-wlcom", updated_control)
      self.assertIn(" gxde-desktop-schemas\n", updated_control)

  def test_imports_qt_core_private_for_qt6_dbus_framework(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      tool_directory = repository / "tools/qdbusxml2cpp"
      tool_directory.mkdir(parents=True)
      cmake = tool_directory / "CMakeLists.txt"
      cmake.write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(gxde-qdbusxml2cpp LANGUAGES CXX)\n\n"
        "# Build gxde-qdbusxml2cpp with Qt6 (host tool for code generation)\n"
        "# NOTE: Not currently integrated into the main build due to\n"
        "# chicken-and-egg problem (tool must be built before codegen,\n"
        "# but execute_process runs at configure time).\n"
        "# To use: build manually with `cmake --build . --target "
        "gxde-qdbusxml2cpp`,\n"
        "# then re-run cmake to generate headers with the fix tool.\n\n"
        "find_package(Qt6 REQUIRED COMPONENTS Core DBus)\n\n"
        "add_executable(gxde-qdbusxml2cpp\n"
        "    qdbusxml2cpp.cpp\n"
        ")\n",
        encoding="utf-8",
      )
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      result = subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="libdframeworkdbus-qt6"; '
          "apply_source_compatibility",
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      self.assertIn(
        "find_package(Qt6CorePrivate REQUIRED)",
        cmake.read_text(encoding="utf-8"),
      )
      self.assertIn(
        "find_package(Qt6DBusPrivate REQUIRED)",
        cmake.read_text(encoding="utf-8"),
      )

  def test_installs_qt_6_10_xcb_private_headers(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      bundled_headers = (
        repository / "compat/qt6-xcb-private-headers/6.10.2"
      )
      shutil.copytree(BUNDLED_XCB_HEADERS, bundled_headers)

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="dde-qt6platform-plugins"; '
          "apply_source_compatibility",
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      installed_headers = (
        repository / "xcb/libqt6xcbqpa-dev/6.10.2"
      )
      self.assertEqual(48, len(list(installed_headers.rglob("*.h"))))
      self.assertEqual(
        (BUNDLED_XCB_HEADERS / "qxcbconnection.h").read_bytes(),
        (installed_headers / "qxcbconnection.h").read_bytes(),
      )

  def test_moves_dtk2widget_moc_include_outside_namespace(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "src/widgets").mkdir(parents=True)
      (repository / "src/util").mkdir(parents=True)
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      (repository / "src/widgets/dsettingswidgetfactory.cpp").write_text(
        "QString::number(static_cast<int>(modifier));\n"
        "QString::number(static_cast<int>(key));\n",
        encoding="utf-8",
      )
      (repository / "src/widgets/dtabbar.cpp").write_text(
        "#if QT_VERSION >= QT_VERSION_CHECK(6, 10, 0)\n"
        "if (index == d->pressedIndex) {}\n",
        encoding="utf-8",
      )
      region_monitor = repository / "src/util/dregionmonitor.cpp"
      region_monitor.write_text(
        "    return p / ratio;\n"
        "}\n\n"
        '#include "moc_dregionmonitor.cpp"\n\n'
        "DWIDGET_END_NAMESPACE\n",
        encoding="utf-8",
      )
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="dtk2widget6"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      lines = [
        line
        for line in region_monitor.read_text(encoding="utf-8").splitlines()
        if line
      ]
      self.assertEqual("DWIDGET_END_NAMESPACE", lines[-2])
      self.assertEqual('#include "moc_dregionmonitor.cpp"', lines[-1])

  def test_moves_gxde_qt6integration_moc_include_outside_namespace(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      style_directory = repository / "dstyleplugin-qt6"
      style_directory.mkdir()
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      style = style_directory / "style.cpp"
      style.write_text(
        "    }\n"
        "}\n\n"
        '#include "moc_style.cpp"\n\n'
        "}\n",
        encoding="utf-8",
      )
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="gxde-qt6integration"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      lines = [
        line for line in style.read_text(encoding="utf-8").splitlines()
        if line
      ]
      self.assertEqual("}", lines[-2])
      self.assertEqual('#include "moc_style.cpp"', lines[-1])


if __name__ == "__main__":
  unittest.main()
