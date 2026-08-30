# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import call, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core import installer
from utils import package_manager

APT_ADAPTER = package_manager.PM_ADAPTERS[package_manager.PackageManager.APT]
TEST_MODULE = {
  "repo_name": "test-repository",
  "display_name": "Test Repository",
  "branch": "develop",
}


class InstallerTest(unittest.TestCase):
  def test_install_dtk2_builds_module_definitions_then_installs_stage(
      self,
    ) -> None:
    with patch.object(installer, "gen_artifact") as gen_artifact_mock, \
        patch.object(
          installer,
          "install_current_stage",
        ) as install_stage_mock:
      installer.install_dtk2()

    gen_artifact_mock.assert_has_calls([
      call(module)
      for module in installer.DTK2_MODULES
    ])
    self.assertEqual(len(installer.DTK2_MODULES), gen_artifact_mock.call_count)
    install_stage_mock.assert_called_once_with("dtk2")

  def test_current_stage_uses_adapter_pattern_and_install_command(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      artifacts_dir = Path(temporary_directory) / "artifacts"
      artifacts_dir.mkdir()
      first_package = artifacts_dir / "first package.pkg"
      second_package = artifacts_dir / "second-package.pkg"
      ignored_package = artifacts_dir / "ignored-package.deb"
      first_package.touch()
      second_package.touch()
      ignored_package.touch()
      test_adapter = package_manager.PackageManagerAdapter(
        detection_command="test-pm",
        display_name="Test Package Manager",
        build_command=("./test-build", "--install-deps"),
        artifact_patterns=("*.pkg",),
        install_command=("doas", "test-pm", "install"),
      )

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(
            installer,
            "get_pm_adapter",
            return_value=test_adapter,
          ), patch.object(installer.os, "fork", return_value=0), \
          patch.object(
            installer.os,
            "execvp",
            side_effect=SystemExit,
          ) as execvp_mock, self.assertRaises(SystemExit):
        installer.install_current_stage("DTK2")

    execvp_mock.assert_called_once_with(
      "doas",
      [
        "doas",
        "test-pm",
        "install",
        str(first_package.resolve()),
        str(second_package.resolve()),
      ],
    )

  def test_current_stage_parent_waits_for_apt_installation(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      artifacts_dir = Path(temporary_directory) / "artifacts"
      artifacts_dir.mkdir()
      (artifacts_dir / "package.deb").touch()

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(
            installer,
            "get_pm_adapter",
            return_value=APT_ADAPTER,
          ), patch.object(installer.os, "fork", return_value=4321), \
          patch.object(
            installer.os,
            "waitpid",
            return_value=(4321, 0),
          ) as waitpid_mock:
        installer.install_current_stage("DTK2")

      waitpid_mock.assert_called_once_with(4321, 0)
      self.assertFalse((artifacts_dir / "package.deb").exists())
      self.assertTrue((artifacts_dir / "DTK2" / "package.deb").is_file())

  def test_current_stage_rejects_archive_paths_outside_artifacts(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_pm_adapter",
        return_value=APT_ADAPTER,
      ), patch.object(installer.os, "fork") as fork_mock, \
        redirect_stderr(output), self.assertRaises(SystemExit) as exit_error:
      installer.install_current_stage("../outside")

    self.assertEqual(1, exit_error.exception.code)
    self.assertIn(
      installer.tr("Warning: invalid artifact archive name: ").strip(),
      output.getvalue(),
    )
    fork_mock.assert_not_called()

  def test_current_stage_exits_when_no_package_artifacts_are_available(
      self,
    ) -> None:
    output = StringIO()

    with TemporaryDirectory() as temporary_directory, \
        patch.object(installer, "WORKING_DIR", temporary_directory), \
        patch.object(
          installer,
          "get_pm_adapter",
          return_value=APT_ADAPTER,
        ), patch.object(installer.os, "fork") as fork_mock, \
        redirect_stderr(output), self.assertRaises(SystemExit) as exit_error:
      installer.install_current_stage("DTK2")

    self.assertEqual(1, exit_error.exception.code)
    self.assertIn(
      installer.tr("Warning: no package artifacts were found in: ").strip(),
      output.getvalue(),
    )
    fork_mock.assert_not_called()

  def test_current_stage_exits_when_apt_fails(self) -> None:
    output = StringIO()

    with TemporaryDirectory() as temporary_directory:
      artifacts_dir = Path(temporary_directory) / "artifacts"
      artifacts_dir.mkdir()
      (artifacts_dir / "package.deb").touch()

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(
            installer,
            "get_pm_adapter",
            return_value=APT_ADAPTER,
          ), patch.object(installer.os, "fork", return_value=4321), \
          patch.object(
            installer.os,
            "waitpid",
            return_value=(4321, 1 << 8),
          ), redirect_stderr(output), \
          self.assertRaises(SystemExit) as exit_error:
        installer.install_current_stage("DTK2")

      self.assertEqual(1, exit_error.exception.code)
      self.assertIn(
        installer.tr("Warning: failed to install the current stage: ").strip(),
        output.getvalue(),
      )
      self.assertTrue((artifacts_dir / "package.deb").is_file())
      self.assertFalse((artifacts_dir / "DTK2").exists())

  def test_copies_apt_installation_scripts_to_cloned_repository(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      repo_dest = Path(temporary_directory) / "test-repository"
      repo_dest.mkdir()

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(
            installer,
            "git_clone",
            return_value=True,
          ) as git_clone_mock, \
          patch.object(
            installer,
            "get_pm_adapter",
            return_value=APT_ADAPTER,
          ), patch.object(installer.os, "fork", return_value=1234) as fork_mock, \
          patch.object(
            installer.os,
            "waitpid",
            return_value=(1234, 0),
          ) as waitpid_mock:
        installer.gen_artifact(TEST_MODULE)

      copied_script = repo_dest / "gxde_build_deb.sh"
      self.assertTrue(copied_script.is_file())
      self.assertEqual(
        (installer.INSTALLATION_SCRIPTS_DIR / "gxde_build_deb.sh").read_bytes(),
        copied_script.read_bytes(),
      )
      fork_mock.assert_called_once_with()
      waitpid_mock.assert_called_once_with(1234, 0)
      git_clone_mock.assert_called_once_with(
        installer.repo_cat("test-repository"),
        str(repo_dest),
        branch="develop",
      )

  def test_build_child_uses_adapter_command_from_repository_root(self) -> None:
    test_adapter = package_manager.PackageManagerAdapter(
      detection_command="test-pm",
      display_name="Test Package Manager",
      build_command=("./test-build", "--install-deps"),
      artifact_patterns=("*.pkg",),
      install_command=("doas", "test-pm", "install"),
    )

    with patch.object(installer, "WORKING_DIR", "/tmp/gxde-work"), \
        patch.object(installer, "git_clone", return_value=True), \
        patch.object(
          installer,
          "get_pm_adapter",
          return_value=test_adapter,
        ), patch.object(installer.shutil, "copytree"), \
        patch.object(installer.os, "fork", return_value=0), \
        patch.object(installer.os, "chdir") as chdir_mock, \
        patch.object(
          installer.os,
          "execvp",
          side_effect=SystemExit,
        ) as execvp_mock:
      with self.assertRaises(SystemExit):
        installer.gen_artifact(TEST_MODULE)

    chdir_mock.assert_called_once_with(
      "/tmp/gxde-work/test-repository",
    )
    execvp_mock.assert_called_once_with(
      "./test-build",
      ["./test-build", "--install-deps"],
    )

  def test_apt_build_failure_stops_artifact_generation(self) -> None:
    output = StringIO()

    with patch.object(installer, "git_clone", return_value=True), \
        patch.object(
          installer,
          "get_pm_adapter",
          return_value=APT_ADAPTER,
        ), patch.object(installer.shutil, "copytree"), \
        patch.object(installer.os, "fork", return_value=1234), \
        patch.object(installer.os, "waitpid", return_value=(1234, 1 << 8)), \
        redirect_stdout(output), self.assertRaises(SystemExit) as exit_error:
      installer.gen_artifact(TEST_MODULE)

    self.assertEqual(1, exit_error.exception.code)
    self.assertIn(
      installer.tr("Failed to build repository: ").strip(),
      output.getvalue(),
    )

  def test_unsupported_package_manager_stops_artifact_generation(
      self,
    ) -> None:
    output = StringIO()

    with patch.object(installer, "git_clone") as git_clone_mock, \
        patch.object(
          installer,
          "get_pm_adapter",
          return_value=None,
        ), patch.object(installer.shutil, "copytree") as copytree_mock:
      with redirect_stderr(output), self.assertRaises(SystemExit):
        installer.gen_artifact(TEST_MODULE)

    git_clone_mock.assert_not_called()
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
