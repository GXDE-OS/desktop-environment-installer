# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core import installer


class InstallerTest(unittest.TestCase):
  def test_selects_official_gitee_ssh_source(self) -> None:
    output = StringIO()

    with patch.object(installer, "get_int_with_bound_inclusive", return_value=1), \
        patch.object(installer, "get_yes_no_input", side_effect=[True, True]), \
        redirect_stdout(output):
      installer.init_installer()

    self.assertIn("git@gitee.com:GXDE-OS/", output.getvalue())
    self.assertEqual(
      "git@gitee.com:GXDE-OS/",
      installer.INSTALLATION_REMOTE_BASE,
    )
    self.assertTrue(installer.INSTALLATION_USE_SSH)

  def test_reselects_source_after_rejecting_custom_source(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_int_with_bound_inclusive",
        side_effect=[3, 1],
      ), patch.object(
        installer,
        "get_yes_no_input",
        side_effect=[True, False, False, True],
      ), patch("builtins.input", return_value="https://example.com/GXDE-OS"), \
        redirect_stdout(output):
      installer.init_installer()

    self.assertIn("https://example.com/GXDE-OS/", output.getvalue())
    self.assertIn("https://gitee.com/GXDE-OS/", output.getvalue())
    self.assertEqual(
      "https://gitee.com/GXDE-OS/",
      installer.INSTALLATION_REMOTE_BASE,
    )
    self.assertFalse(installer.INSTALLATION_USE_SSH)


if __name__ == "__main__":
  unittest.main()
