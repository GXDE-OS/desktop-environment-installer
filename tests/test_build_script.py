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

  def test_preserves_whitespace_only_package_separator(self) -> None:
    control = self.apply_compatibility(
      "(none)",
      "Source: test\n"
      "Build-Depends: debhelper\n"
      "\n"
      "Package: first\n"
      "Architecture: any\n"
      "Description: first package\n"
      " \n"
      "Package: second\n"
      "Architecture: any\n"
      "Description: second package\n",
    )

    self.assertIn(
      "Description: first package\n\nPackage: second\n",
      control,
    )

  def test_repairs_package_paragraph_merged_by_older_installer(self) -> None:
    control = self.apply_compatibility(
      "(none)",
      "Source: test\n"
      "Build-Depends: debhelper\n"
      "\n"
      "Package: first\n"
      "Architecture: any\n"
      "Description: first package\n"
      "Package: second\n"
      "Architecture: any\n"
      "Description: second package\n",
    )

    self.assertIn(
      "Description: first package\n\nPackage: second\n",
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

  def test_shell_compressor_repairs_empty_changelog_email(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-shell-compressor\n"
        "Maintainer: shenmo <jifengshenmo@outlook.com>\n"
        "Build-Depends: debhelper-compat (= 13)\n\n"
        "Package: gxde-shell-compressor\n"
        "Architecture: all\n"
        "Depends: ${misc:Depends}\n",
        encoding="utf-8",
      )
      changelog = repository / "debian/changelog"
      changelog.write_text(
        "gxde-shell-compressor (1.4.1) UNRELEASED; urgency=low\n\n"
        "  * Test entry\n\n"
        " -- shenmo <>  Sun, 01 Dec 2024 02:31:12 +0800\n\n"
        "gxde-shell-compressor (1.4.0) unstable; urgency=medium\n\n"
        "  * Previous entry\n\n"
        " -- Other Person <other@example.com>  Sat, 30 Nov 2024 12:00:00 +0800\n",
        encoding="utf-8",
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-shell-compressor"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      repaired_changelog = changelog.read_text(encoding="utf-8")
      self.assertEqual(
        1,
        repaired_changelog.count("shenmo <jifengshenmo@outlook.com>"),
      )
      self.assertNotIn("shenmo <>", repaired_changelog)
      self.assertIn("Other Person <other@example.com>", repaired_changelog)

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

  def test_promotes_valid_uploader_from_corrupted_maintainer(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-globalmenu-service\n"
        "Maintainer: SeptemberHX\n"
        "Uploaders: gfdgd_xi <3025613752@qq.com>\n"
        "Build-Depends: debhelper-compat (= 13)\n",
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
        "Maintainer: gfdgd_xi <3025613752@qq.com>\n",
        updated_control,
      )
      self.assertNotIn("Maintainer: SeptemberHX", updated_control)
      self.assertNotIn("Uploaders:", updated_control)

  def test_uses_valid_address_from_comma_separated_maintainers(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-globalmenu-service\n"
        "Maintainer: SeptemberHX, gfdgd_xi <3025613752@qq.com>\n"
        "Build-Depends: debhelper-compat (= 13)\n",
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
        "Maintainer: gfdgd_xi <3025613752@qq.com>\n",
        updated_control,
      )
      self.assertNotIn("SeptemberHX", updated_control)
      self.assertNotIn("Uploaders:", updated_control)

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

  def test_global_menu_drops_unused_deepin_build_dependencies(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-globalmenu-service\n"
        "Maintainer: GXDE <team@example.com>\n"
        "Build-Depends:\n"
        " debhelper-compat (= 13),\n"
        " qtbase5-dev,\n"
        " libdtkwidget-dev,\n"
        " libdtkcore-dev,\n"
        " libdtkcore5-bin,\n"
        " libdframeworkdbus-dev,\n"
        " libgsettings-qt-dev,\n"
        " libkf5windowsystem-dev\n",
        encoding="utf-8",
      )
      (repository / "CMakeLists.txt").write_text(
        "find_package(Qt5Widgets REQUIRED)\n"
        "find_package(KF5WindowSystem REQUIRED)\n"
        "find_package(XCB REQUIRED COMPONENTS xcb)\n",
        encoding="utf-8",
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-globalmenu-service"; apply_source_compatibility',
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
      )

      updated_control = control.read_text(encoding="utf-8")
      for unused_dependency in (
        "libdtkwidget-dev",
        "libdtkcore-dev",
        "libdtkcore5-bin",
        "libdframeworkdbus-dev",
        "libgsettings-qt-dev",
      ):
        self.assertNotIn(unused_dependency, updated_control)
      self.assertIn("qtbase5-dev", updated_control)
      self.assertIn("libkf5windowsystem-dev", updated_control)

      resumed_run = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
      )
      self.assertIn(
        "build dependencies already match its source",
        resumed_run.stdout,
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
      documentation_directory = (
        repository / "docs/reference/gnome-keyring"
      )
      documentation_directory.mkdir(parents=True)
      documentation_makefile = documentation_directory / "Makefile.in"
      documentation_makefile.write_text(
        "tmpl-build.stamp:\n"
        "\t$(GTK_DOC_V_TMPL)gtkdoc-mktmpl --module=$(DOC_MODULE) "
        "$(MKTMPL_OPTIONS)\n",
        encoding="utf-8",
      )
      (repository / "gtk-doc.make").write_text(
        "\t$(GTK_DOC_V_TMPL)gtkdoc-mktmpl --module=$(DOC_MODULE) "
        "$(MKTMPL_OPTIONS)\n",
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
      self.assertIn(
        "env -u DBUS_SESSION_BUS_ADDRESS dh_auto_test\n",
        updated_rules,
      )
      self.assertNotIn("/usr/share/cdbs", updated_rules)
      self.assertNotIn("cdbs (>=", updated_control)
      self.assertNotIn("dh-autoreconf", updated_control)
      self.assertIn("gnome-pkg-tools (>= 0.10)", updated_control)
      self.assertNotIn(
        "gtkdoc-mktmpl",
        documentation_makefile.read_text(encoding="utf-8"),
      )
      self.assertIn(
        "Using the shipped gtk-doc templates",
        documentation_makefile.read_text(encoding="utf-8"),
      )
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

  def test_gxde_dock_loads_pkg_config_before_checking_modules(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      plugin_directory = repository / "plugins/dde-sys-monitor-plugin"
      plugin_directory.mkdir(parents=True)
      frame_directory = repository / "frame"
      frame_directory.mkdir()
      tray_directory = repository / "plugins/tray"
      tray_directory.mkdir()
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      cmake_file = plugin_directory / "CMakeLists.txt"
      cmake_file.write_text(
        'file(GLOB_RECURSE SRCS "*.h" "*.cpp" "*.ui")\n'
        "# <库名>_INCLUDE_DIRS   有哪些头文件目录（Qt5Widgets_INCLUDE_DIRS）\n"
        "# <库名>_LIBRARIES      有哪些库文件（Qt5Widgets_LIBRARIES）\n"
        "find_package(Qt6 REQUIRED COMPONENTS Widgets)\n"
        "pkg_check_modules(dtk2widget REQUIRED dtk2widget)\n\n"
        "# find_package 命令还可以用来加载 cmake 的功能模块\n"
        "# 并不是所有的库都直接支持 cmake 查找的，但大部分都支持了 pkg-config 这个标准，\n"
        "# PKG_CONFIG_EXECUTABLE       pkg-config 可执行文件的路径\n"
        "# PKG_CONFIG_VERSION_STRING   pkg-config 的版本信息\n"
        "find_package(PkgConfig REQUIRED)\n\n"
        "# 加载 FindPkgConfig 模块后就可以使用 pkg_check_modules 命令加载需要的库\n"
        "# pkg_check_modules 命令是由 FindPkgConfig 模块提供的，因此要使用这个命令必须先加载 FindPkgConfig 模块。\n",
        encoding="utf-8",
      )
      frame_cmake = frame_directory / "CMakeLists.txt"
      frame_cmake.write_text(
        "# Find the library\n"
        "find_package(PkgConfig REQUIRED)\n"
        "find_package(Qt6 REQUIRED COMPONENTS DBus Gui Concurrent Widgets)\n"
        "find_package(LayerShellQt REQUIRED)\n",
        encoding="utf-8",
      )
      tray_cmake = tray_directory / "CMakeLists.txt"
      tray_cmake.write_text(
        "find_package(PkgConfig REQUIRED)\n"
        "find_package(Qt6 REQUIRED COMPONENTS Gui DBus Svg Widgets)\n"
        "pkg_check_modules(dtk2widget REQUIRED dtk2widget)\n",
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
          'PKG_NAME="gxde-dock"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )

      updated_cmake = cmake_file.read_text(encoding="utf-8")
      self.assertLess(
        updated_cmake.index("find_package(PkgConfig REQUIRED)"),
        updated_cmake.index(
          "pkg_check_modules(dtk2widget REQUIRED dtk2widget)"
        ),
      )
      self.assertIn(
        "find_package(Qt6GuiPrivate REQUIRED)",
        frame_cmake.read_text(encoding="utf-8"),
      )
      self.assertIn(
        "find_package(Qt6GuiPrivate REQUIRED)",
        tray_cmake.read_text(encoding="utf-8"),
      )
      resumed_run = subprocess.run(
        [
          "bash",
          "-c",
          'source "$1"; PROJ_ROOT="$2"; '
          'PKG_NAME="gxde-dock"; apply_source_compatibility',
          "build-script-test",
          str(BUILD_SCRIPT),
          str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
      )
      self.assertIn(
        "GXDE Dock loads PkgConfig before checking DTK2 Widget",
        resumed_run.stdout,
      )
      self.assertIn(
        "GXDE Dock explicitly imports the Qt GUI private target",
        resumed_run.stdout,
      )
      self.assertEqual(
        1,
        frame_cmake.read_text(encoding="utf-8").count(
          "find_package(Qt6GuiPrivate REQUIRED)"
        ),
      )
      self.assertEqual(
        1,
        tray_cmake.read_text(encoding="utf-8").count(
          "find_package(Qt6GuiPrivate REQUIRED)"
        ),
      )

  def test_top_panel_plugins_uses_gxde_dbusmenu_qt6_package(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory) / "gxde-top-panel-plugins"
      repository.mkdir()

      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-top-panel-plugins\n"
        "Build-Depends:\n"
        "  debhelper-compat (= 13),\n"
        "  libdbusmenu-lxqt-dev,\n"
        "  qt6-base-dev\n",
        encoding="utf-8",
      )
      root_cmake = repository / "CMakeLists.txt"
      root_cmake.write_text(
        "endif()\n\n"
        'file(GLOB INTERFACES "interfaces/*.h")\n\n'
        "# Build the Qt 6 dbusmenu implementation bundled with GXDE Dock.  "
        "The source\n"
        "# is copied into this checkout by the installer compatibility "
        "step.\n"
        'add_subdirectory("cmake/libdbusmenu")\n\n'
        '#add_subdirectory("frame")\n'
        'add_subdirectory("plugins")\n\n',
        encoding="utf-8",
      )
      tray_directory = repository / "plugins/tray"
      tray_directory.mkdir(parents=True)
      tray_cmake = tray_directory / "CMakeLists.txt"
      tray_cmake.write_text(
        "find_package(Dtk6Widget REQUIRED)\n"
        "find_package(Dtk6Gui REQUIRED)\n"
        "find_package(Dtk6Core REQUIRED)\n"
        "find_package(DFrameworkdbusQt6 CONFIG REQUIRED)\n"
        "find_package(dbusmenu-lxqt CONFIG REQUIRED)\n\n"
        "pkg_check_modules(XCB_LIBS REQUIRED xcb-ewmh xcb xcb-image "
        "xcb-composite xtst x11 xext xcb-icccm)\n"
        "pkg_check_modules(DDE-Network-Utils REQUIRED "
        "gxde-network-utils-qt6)\n"
        "pkg_check_modules(QGSettings REQUIRED gsettings-qt6)\n\n"
        "add_definitions(\"${QT_DEFINITIONS} -DQT_PLUGIN\")\n"
        "add_library(${PLUGIN_NAME} SHARED ${SRCS} tray.qrc)\n"
        "set_target_properties(${PLUGIN_NAME} PROPERTIES "
        "LIBRARY_OUTPUT_DIRECTORY ../)\n"
        "target_include_directories(${PLUGIN_NAME} PUBLIC "
        "${DtkGui_INCLUDE_DIRS}\n"
        "                                                 "
        "${XCB_LIBS_INCLUDE_DIRS}\n"
        "                                                 "
        "${DDE-Network-Utils_INCLUDE_DIRS}\n"
        "                                                 "
        "${QGSettings_INCLUDE_DIRS}\n"
        "                                                 "
        "${dbusmenu-lxqt_INCLUDE_DIRS}\n"
        "                                                 ../../interfaces\n"
        "                                                 ../../frame)\n"
        "target_include_directories(${PLUGIN_NAME} PRIVATE\n"
        '    "${CMAKE_SOURCE_DIR}/lib/3rdparty/libdbusmenu/src"\n'
        '    "${CMAKE_BINARY_DIR}/cmake/libdbusmenu/dbusmenu-build/src"\n'
        ")\n"
        "target_link_libraries(${PLUGIN_NAME} PRIVATE\n"
        "    Dtk6::Gui\n"
        "    Dtk6::Widget\n"
        "    Dtk6::Core\n"
        "    Qt6::Widgets\n"
        "    Qt6::DBus\n"
        "    Qt6::Svg\n"
        "    ${XCB_LIBS_LIBRARIES}\n"
        "    ${DDE-Network-Utils_LIBRARIES}\n"
        "    #${dbusmenu-lxqt_LIBRARIES}\n"
        "    dbusmenu-lxqt\n"
        "    DFrameworkdbusQt6::DFrameworkdbusQt6\n"
        "    ${QGSettings_LIBRARIES}\n"
        "    pthread\n"
        ")\n",
        encoding="utf-8",
      )
      tray_source = tray_directory / "snitraywidget.cpp"
      tray_source.write_text(
        "#include <dbusmenu-lxqt/dbusmenuimporter.h>\n",
        encoding="utf-8",
      )
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-top-panel-plugins"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      first_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        first_run.returncode,
        first_run.stdout + first_run.stderr,
      )

      self.assertIn("libdbusmenu-qt6-dev", control.read_text())
      self.assertNotIn("libdbusmenu-lxqt-dev", control.read_text())
      self.assertNotIn(
        'add_subdirectory("cmake/libdbusmenu")',
        root_cmake.read_text(),
      )
      self.assertIn(
        "find_package(dbusmenu-qt6 CONFIG REQUIRED)",
        tray_cmake.read_text(),
      )
      self.assertIn("dbusmenu-qt6", tray_cmake.read_text())
      self.assertNotIn("dbusmenu-lxqt", tray_cmake.read_text())
      self.assertNotIn(
        "lib/3rdparty/libdbusmenu/src",
        tray_cmake.read_text(),
      )
      self.assertIn(
        "<dbusmenuimporter.h>",
        tray_source.read_text(),
      )

      resumed_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        resumed_run.returncode,
        resumed_run.stdout + resumed_run.stderr,
      )
      self.assertIn(
        "already uses DBusMenu Qt6",
        resumed_run.stdout,
      )

  def test_dbusmenu_qt6_development_package_depends_on_qt6(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: libdbusmenu-qt6\n"
        "Build-Depends: debhelper-compat (= 13), qt6-base-dev\n\n"
        "Package: libdbusmenu-qt6-dev\n"
        "Architecture: any\n"
        "Depends: libdbusmenu-qt6-2 (= ${binary:Version}),\n"
        " qtbase5-dev,\n"
        " ${misc:Depends}\n",
        encoding="utf-8",
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="libdbusmenu-qt6"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      first_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        first_run.returncode,
        first_run.stdout + first_run.stderr,
      )
      self.assertIn(" qt6-base-dev,", control.read_text())
      self.assertNotIn("qtbase5-dev", control.read_text())

      resumed_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        resumed_run.returncode,
        resumed_run.stdout + resumed_run.stderr,
      )
      self.assertIn(
        "already use Qt 6",
        resumed_run.stdout,
      )

  def test_control_center_imports_qt_gui_private_target(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-control-center\n"
        "Build-Depends: debhelper-compat (= 13), qt6-base-private-dev\n\n"
        "Package: gxde-control-center\n"
        "Architecture: any\n"
        "Depends: ${misc:Depends}\n",
        encoding="utf-8",
      )
      frame_directory = repository / "src/frame"
      frame_directory.mkdir(parents=True)
      frame_cmake = frame_directory / "CMakeLists.txt"
      frame_cmake.write_text(
        "find_package(PkgConfig REQUIRED)\n"
        "find_package(Qt6 REQUIRED COMPONENTS Widgets Concurrent DBus)\n\n"
        "add_executable(${BIN_NAME} ${SRCS})\n"
        "target_link_libraries(${BIN_NAME} PRIVATE\n"
        "    Qt6::Widgets\n"
        "    Qt6::Concurrent\n"
        ")\n",
        encoding="utf-8",
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-control-center"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      first_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        first_run.returncode,
        first_run.stdout + first_run.stderr,
      )
      self.assertIn(
        "find_package(Qt6GuiPrivate REQUIRED)",
        frame_cmake.read_text(),
      )
      self.assertIn("Qt6::GuiPrivate", frame_cmake.read_text())

      resumed_run = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(
        0,
        resumed_run.returncode,
        resumed_run.stdout + resumed_run.stderr,
      )
      self.assertEqual(
        1,
        frame_cmake.read_text().count(
          "find_package(Qt6GuiPrivate REQUIRED)"
        ),
      )
      self.assertEqual(
        2,
        frame_cmake.read_text().count("Qt6::GuiPrivate"),
      )

  def test_gxde_movie_imports_qt_gui_private_for_both_qt6_targets(
      self,
    ) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-movie-reborn\n"
        "Build-Depends: debhelper-compat (= 13), qt6-base-private-dev\n\n"
        "Package: gxde-movie\n"
        "Architecture: any\n"
        "Depends: ${misc:Depends}\n",
        encoding="utf-8",
      )
      qt6_cmake_files = (
        repository / "src/CMakeLists.txt",
        repository / "src/libgxmr-qt6/CMakeLists.txt",
      )
      for cmake_file in qt6_cmake_files:
        cmake_file.parent.mkdir(parents=True, exist_ok=True)
        cmake_file.write_text(
          "find_package(Qt6 REQUIRED COMPONENTS Widgets Gui)\n\n"
          "pkg_check_modules(DTK2W REQUIRED IMPORTED_TARGET dtk2widget)\n\n"
          "target_link_libraries(${CMD_NAME}\n"
          "    Qt6::Gui Qt6::GuiPrivate)\n",
          encoding="utf-8",
        )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-movie-reborn"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      for cmake_file in qt6_cmake_files:
        patched_cmake = cmake_file.read_text(encoding="utf-8")
        self.assertEqual(
          1,
          patched_cmake.count("find_package(Qt6GuiPrivate REQUIRED)"),
        )
        self.assertLess(
          patched_cmake.index("find_package(Qt6GuiPrivate REQUIRED)"),
          patched_cmake.index("target_link_libraries"),
        )

  def test_file_manager_preserves_environment_with_qt610_start_detached(
      self,
    ) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-file-manager\n"
        "Build-Depends: debhelper-compat (= 13), qt6-base-dev\n\n"
        "Package: gxde-file-manager\n"
        "Architecture: any\n"
        "Depends: ${misc:Depends}\n\n"
        "Package: libgxde-file-manager\n"
        "Architecture: any\n"
        "Depends:\n"
        " ${shlibs:Depends},\n"
        " ${misc:Depends},\n"
        " libpoppler-cpp0v5 | libpoppler-cpp1 | libpoppler-cpp2,\n"
        " gvfs-backends(>=1.27.3),\n"
        " cryptsetup,\n"
        " libkf6codecs6,\n",
        encoding="utf-8",
      )
      controller = (
        repository
        / "gxde-file-manager-lib/controllers/filecontroller.cpp"
      )
      controller.parent.mkdir(parents=True)
      controller.write_text(
        "QProcessEnvironment compressorEnvironment()\n"
        "{\n"
        "    return QProcessEnvironment::systemEnvironment();\n"
        "}\n\n"
        "bool startCompressor(const QStringList &args)\n"
        "{\n"
        "    return QProcess::startDetached(QStringLiteral(\"gxde-compressor\"),\n"
        "                                   args,\n"
        "                                   QString(),\n"
        "                                   compressorEnvironment());\n"
        "}\n\n"
        "} \n",
        encoding="utf-8",
      )
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-file-manager"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      patched_controller = controller.read_text(encoding="utf-8")
      self.assertIn(
        "compressorProcess.setProcessEnvironment(compressorEnvironment())",
        patched_controller,
      )
      self.assertIn(
        "return compressorProcess.startDetached()",
        patched_controller,
      )
      self.assertNotIn(
        "QProcess::startDetached(QStringLiteral(\"gxde-compressor\")",
        patched_controller,
      )
      patched_control = (repository / "debian/control").read_text(
        encoding="utf-8",
      )
      self.assertIn(
        "libpoppler-cpp2 | libpoppler-cpp3",
        patched_control,
      )

  def test_file_manager_integration_builds_against_qt6(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      control = repository / "debian/control"
      control.write_text(
        "Source: gxde-file-manager-integration\n"
        "Section: devel\n"
        "Priority: optional\n"
        "Maintainer: gfdgd xi <3025613752@qq.com>\n"
        "Build-Depends: debhelper (>=9), pkg-config, qt5-qmake, "
        "qtbase5-dev, qtwebengine5-dev, \n"
        " \t\tlibgxde-file-manager-dev, libfontconfig1-dev, qtchooser\n"
        "Standards-Version: 3.9.6\n"
        "Homepage: http://www.deepin.org\n\n"
        "Package: gxde-file-manager-integration\n"
        "Architecture: any\n"
        "Depends: ${shlibs:Depends}, ${misc:Depends}\n"
        " libgxde-file-manager\n"
        "Description: GXDE File manager plugin integration\n"
        " Include the following plugins:\n",
        encoding="utf-8",
      )
      rules = repository / "debian/rules"
      rules.write_text(
        "#!/usr/bin/make -f\n"
        "include /usr/share/dpkg/default.mk\n\n"
        "VERSION=$(shell dpkg-parsechangelog -ldebian/changelog "
        "-SVersion | awk -F'-' '{print $$1}')\n"
        "DEB_BUILD_ARCH ?= $(shell dpkg-architecture -qDEB_BUILD_ARCH)\n"
        "export QT_SELECT=5\n"
        "%:\n"
        "\tdh $@ --parallel\n\n"
        "override_dh_shlibdeps:\n"
        "\t--ignore-missing-info\n\n"
        "override_dh_auto_configure:\n"
        "\tdh_auto_configure -- DAPP_VERSION=$(VERSION) "
        "LIB_INSTALL_DIR=/usr/lib/$(DEB_HOST_MULTIARCH)\n",
        encoding="utf-8",
      )
      webview = repository / "webview/dfmwebview.cpp"
      webview.parent.mkdir()
      webview.write_text(
        "#include <dfmeventdispatcher.h>\n\n"
        "#include <QWebEngineHistory>\n"
        "#include <QAction>\n"
        "#include <QWebEngineContextMenuData>\n"
        "#include <QWebEngineSettings>\n"
        "#include <QMenu>\n\n"
        "DFMWebView::DFMWebView(QWidget *parent)\n"
        "    : QWebEngineView(parent)\n"
        "{\n"
        "    DFMWebViewPrivate::lastCreateWebView = this;\n\n"
        "    QWebEngineSettings::defaultSettings()->setAttribute(QWebEngineSettings::PluginsEnabled, true);\n\n"
        "    connect(this, &QWebEngineView::urlChanged, this, &DFMWebView::notifyUrlChanged);\n\n"
        "void DFMWebView::contextMenuEvent(QContextMenuEvent *event)\n"
        "{\n"
        "    const QWebEngineContextMenuData &data = page()->contextMenuData();\n"
        "    const DUrl url = data.linkUrl();\n\n"
        "    if (url.isEmpty()) {\n"
        "        return QWebEngineView::contextMenuEvent(event);\n",
        encoding="utf-8",
      )
      nutstore = (
        repository
        / "nutstore-dfm-plugin/dfmgenericpluginobject.cpp"
      )
      nutstore.parent.mkdir()
      nutstore.write_text(
        "DFMGenericPluginObject::DFMGenericPluginObject(QObject *parent)\n"
        "    : QObject(parent)\n"
        "{\n\n"
        "    connect(client, &QTcpSocket::connected, this, &DFMGenericPluginObject::updateNSRootPathList);\n"
        "    connect(client, &QTcpSocket::readyRead, this, &DFMGenericPluginObject::onClientReadReady);\n"
        "    connect(client, static_cast<void(QTcpSocket::*)(QAbstractSocket::SocketError)>(&QTcpSocket::error), this, [this] {\n"
        "        qWarning() << \"The localhost:19080 tcp socket error:\" << client->errorString();\n\n"
        "        // reset\n",
        encoding="utf-8",
      )
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-file-manager-integration"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      patched_control = control.read_text(encoding="utf-8")
      self.assertIn("qmake6", patched_control)
      self.assertIn("qt6-webengine-dev", patched_control)
      self.assertNotIn("qt5-qmake", patched_control)
      self.assertIn("${misc:Depends},\n libgxde-file-manager", patched_control)
      self.assertIn("--buildsystem=qmake6", rules.read_text(encoding="utf-8"))
      self.assertIn("lastContextMenuRequest()", webview.read_text(encoding="utf-8"))
      self.assertIn("QTcpSocket::errorOccurred", nutstore.read_text(encoding="utf-8"))

  def test_wlcom_ignores_libinput_switch_kinds_unknown_to_wlroots(
      self,
    ) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-wlcom\n"
        "Build-Depends: debhelper-compat (= 13), libinput-dev\n\n"
        "Package: gxde-wlcom\n"
        "Architecture: any\n"
        "Depends: ${misc:Depends}\n",
        encoding="utf-8",
      )
      switch_source = (
        repository
        / "subprojects/wlroots/backend/libinput/switch.c"
      )
      switch_source.parent.mkdir(parents=True)
      switch_source.write_text(
        "void handle_switch_toggle(void) {\n"
        "\tswitch (libinput_event_switch_get_switch(sevent)) {\n"
        "\tcase LIBINPUT_SWITCH_LID:\n"
        "\t\twlr_event.switch_type = WLR_SWITCH_TYPE_LID;\n"
        "\t\tbreak;\n"
        "\tcase LIBINPUT_SWITCH_TABLET_MODE:\n"
        "\t\twlr_event.switch_type = WLR_SWITCH_TYPE_TABLET_MODE;\n"
        "\t\tbreak;\n"
        "\t}\n"
        "\tswitch (libinput_event_switch_get_switch_state(sevent)) {\n"
        "\tcase LIBINPUT_SWITCH_STATE_OFF:\n"
        "\t\twlr_event.switch_state = WLR_SWITCH_STATE_OFF;\n"
        "\t\tbreak;\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
      )
      shutil.copytree(BUNDLED_PATCHES, repository / "patches")
      subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository,
        check=True,
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-wlcom"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      patched_switch = switch_source.read_text(encoding="utf-8")
      self.assertIn(
        "\tdefault:\n\t\treturn;",
        patched_switch,
      )

  def test_launcher_imports_qt_gui_private_target(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      (repository / "debian").mkdir()
      (repository / "debian/control").write_text(
        "Source: gxde-launcher\n"
        "Build-Depends: debhelper-compat (= 13), qt6-base-private-dev\n\n"
        "Package: gxde-launcher\n"
        "Architecture: any\n"
        "Depends: ${misc:Depends}\n",
        encoding="utf-8",
      )
      launcher_cmake = repository / "CMakeLists.txt"
      launcher_cmake.write_text(
        "find_package(PkgConfig REQUIRED)\n"
        "find_package(Qt6Widgets REQUIRED)\n"
        "find_package(Qt6Concurrent REQUIRED)\n\n"
        "add_executable(${BIN_NAME} ${SRCS})\n"
        "target_include_directories(${BIN_NAME} PUBLIC\n"
        "    ${Qt6Gui_PRIVATE_INCLUDE_DIRS}\n"
        ")\n"
        "target_link_libraries(${BIN_NAME} PRIVATE\n"
        "    ${Qt6Widgets_LIBRARIES}\n"
        "    ${Qt6Concurrent_LIBRARIES}\n"
        ")\n",
        encoding="utf-8",
      )

      command = [
        "bash",
        "-c",
        'source "$1"; PROJ_ROOT="$2"; '
        'PKG_NAME="gxde-launcher"; '
        "apply_source_compatibility",
        "build-script-test",
        str(BUILD_SCRIPT),
        str(repository),
      ]
      for _ in range(2):
        result = subprocess.run(
          command,
          check=False,
          capture_output=True,
          text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

      patched_cmake = launcher_cmake.read_text(encoding="utf-8")
      self.assertEqual(
        1,
        patched_cmake.count("find_package(Qt6GuiPrivate REQUIRED)"),
      )
      self.assertEqual(2, patched_cmake.count("Qt6::GuiPrivate"))
      self.assertIn("${Qt6Gui_PRIVATE_INCLUDE_DIRS}", patched_cmake)

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
