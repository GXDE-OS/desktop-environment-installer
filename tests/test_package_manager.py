# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils import package_manager


class PackageManagerTest(unittest.TestCase):
  def tearDown(self) -> None:
    package_manager.CURRENT_PM = package_manager.PackageManager.UNSUPPORTED

  def test_init_sets_apt_as_current_package_manager(self) -> None:
    with patch.object(
        package_manager.shutil,
        "which",
        return_value="/usr/bin/apt",
      ):
      package_manager.init_pm_helper()

    self.assertEqual(
      package_manager.PackageManager.APT,
      package_manager.get_pm(),
    )
    self.assertEqual(
      package_manager.PackageManagerAdapter(
        detection_command="apt",
        display_name="Advanced Packaging Tools",
        build_command=("./gxde_build_deb.sh", "-d"),
        artifact_patterns=("*.deb",),
        install_command=("sudo", "apt", "install"),
      ),
      package_manager.get_pm_adapter(),
    )


if __name__ == "__main__":
  unittest.main()
