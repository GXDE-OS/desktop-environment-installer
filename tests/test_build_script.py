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
  def apply_compatibility(self, candidate: str) -> str:
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory)
      debian_directory = repository / "debian"
      debian_directory.mkdir()
      control = debian_directory / "control"
      control.write_text(
        "Source: test\n"
        "Build-Depends: qt6-wayland-dev, qt6-wayland-dev-tools, "
        "treeland-protocols\n",
        encoding="utf-8",
      )

      subprocess.run(
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
