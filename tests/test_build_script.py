# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = PROJECT_ROOT / "res/installation_scripts/gxde_build_deb.sh"


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


if __name__ == "__main__":
  unittest.main()
