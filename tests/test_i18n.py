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

import os
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = PROJECT_ROOT / "src" / "main.py"

class I18nTest(unittest.TestCase):
  def run_app(
      self,
      language: str,
      user_input: str = "n\n",
      arguments: tuple[str, ...] = (),
    ) -> str:
    environment = os.environ.copy()
    environment["LANGUAGE"] = language
    result = subprocess.run(
      [sys.executable, str(ENTRY_POINT), *arguments],
      check=True,
      capture_output=True,
      text=True,
      input=user_input,
      env=environment,
    )
    return result.stdout

  def test_detects_simplified_chinese_from_environment(self) -> None:
    self.assertIn("GXDE桌面环境安装器", self.run_app("zh_CN"))

  def test_unknown_language_falls_back_to_en_us(self) -> None:
    self.assertIn("GXDE Desktop Environment Installer", self.run_app("zz_ZZ"))

  def test_get_input_uses_the_active_translation(self) -> None:
    output = self.run_app("zh_CN", "x\nn\n")
    self.assertIn("输入无效，请重试...", output)

  def test_resume_help_is_translated(self) -> None:
    output = self.run_app("zh_CN", user_input="", arguments=("--help",))

    self.assertIn("--resume", output)
    self.assertIn("从之前工作目录中最后一个未完成的步骤继续", output)


if __name__ == "__main__":
  unittest.main()
