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
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core import installer


class InstallerTest(unittest.TestCase):
  def test_copies_apt_installation_scripts_to_cloned_repository(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repo_dest = Path(temporary_directory) / "test-repository"
      repo_dest.mkdir()

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(installer, "git_clone", return_value=True), \
          patch.object(
            installer,
            "get_pm",
            return_value=installer.PackageManager.APT,
          ), patch.object(installer.os, "fork", return_value=1234) as fork_mock, \
          patch.object(
            installer.os,
            "waitpid",
            return_value=(1234, 0),
          ) as waitpid_mock:
        installer.gen_artifact("test-repository")

      copied_script = repo_dest / "gxde_build_deb.sh"
      self.assertTrue(copied_script.is_file())
      self.assertEqual(
        (installer.INSTALLATION_SCRIPTS_DIR / "gxde_build_deb.sh").read_bytes(),
        copied_script.read_bytes(),
      )
      fork_mock.assert_called_once_with()
      waitpid_mock.assert_called_once_with(1234, 0)

  def test_apt_build_child_executes_script_from_repository_root(self) -> None:
    with patch.object(installer, "WORKING_DIR", "/tmp/gxde-work"), \
        patch.object(installer, "git_clone", return_value=True), \
        patch.object(
          installer,
          "get_pm",
          return_value=installer.PackageManager.APT,
        ), patch.object(installer.shutil, "copytree"), \
        patch.object(installer.os, "fork", return_value=0), \
        patch.object(installer.os, "chdir") as chdir_mock, \
        patch.object(
          installer.os,
          "execl",
          side_effect=SystemExit,
        ) as execl_mock:
      with self.assertRaises(SystemExit):
        installer.gen_artifact("test-repository")

    chdir_mock.assert_called_once_with(
      "/tmp/gxde-work/test-repository",
    )
    execl_mock.assert_called_once_with(
      "./gxde_build_deb.sh",
      "./gxde_build_deb.sh",
      "-d",
    )

  def test_apt_build_failure_stops_artifact_generation(self) -> None:
    output = StringIO()

    with patch.object(installer, "git_clone", return_value=True), \
        patch.object(
          installer,
          "get_pm",
          return_value=installer.PackageManager.APT,
        ), patch.object(installer.shutil, "copytree"), \
        patch.object(installer.os, "fork", return_value=1234), \
        patch.object(installer.os, "waitpid", return_value=(1234, 1 << 8)), \
        redirect_stdout(output), self.assertRaises(SystemExit) as exit_error:
      installer.gen_artifact("test-repository")

    self.assertEqual(1, exit_error.exception.code)
    self.assertIn(
      installer.tr("Failed to build repository: ").strip(),
      output.getvalue(),
    )

  def test_does_not_copy_apt_scripts_for_unsupported_package_manager(
      self,
    ) -> None:
    with patch.object(installer, "git_clone", return_value=True), \
        patch.object(
          installer,
          "get_pm",
          return_value=installer.PackageManager.UNSUPPORTED,
        ), patch.object(installer.shutil, "copytree") as copytree_mock:
      installer.gen_artifact("test-repository")

    copytree_mock.assert_not_called()

  def test_selects_official_gitee_ssh_source(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_dir",
        return_value="/tmp/gxde-work",
      ) as get_dir_mock, \
        patch.object(installer, "get_int_with_bound_inclusive", return_value=1), \
        patch.object(installer, "get_yes_no_input", side_effect=[True, True]), \
        redirect_stdout(output):
      installer.init_installer()

    self.assertIn("git@gitee.com:GXDE-OS/", output.getvalue())
    self.assertEqual(
      "git@gitee.com:GXDE-OS/",
      installer.INSTALLATION_REMOTE_BASE,
    )
    self.assertTrue(installer.INSTALLATION_USE_SSH)
    self.assertEqual("/tmp/gxde-work", installer.WORKING_DIR)
    get_dir_mock.assert_called_once_with(
      installer.tr("Please enter the working directory."),
      create_mode=True,
      must_empty=True,
    )

  def test_reselects_source_after_rejecting_custom_source(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_dir",
        return_value="/tmp/gxde-work",
      ), patch.object(
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
    self.assertEqual("/tmp/gxde-work", installer.WORKING_DIR)


if __name__ == "__main__":
  unittest.main()
