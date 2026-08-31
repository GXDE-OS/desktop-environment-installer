# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import main as installer_main
from core import installer
from utils import package_manager


APT_ADAPTER = package_manager.PM_ADAPTERS[package_manager.PackageManager.APT]


class ResumeTest(unittest.TestCase):
  def setUp(self) -> None:
    installer.RESUME_MODE = False
    installer.INSTALLATION_STATE = None

  def test_cli_accepts_resume_option(self) -> None:
    self.assertTrue(installer_main.parse_arguments(["--resume"]).resume)
    self.assertFalse(installer_main.parse_arguments([]).resume)

  def test_init_resume_loads_saved_source_and_steps(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      state = {
        "version": installer.STATE_VERSION,
        "repository_remote_base": "https://github.com/GXDE-OS/",
        "installation_use_ssh": False,
        "choices": {"dtk6_gxde": True},
        "completed_steps": ["build:dtk6:dtk6core"],
      }
      state_path = Path(temporary_directory) / installer.STATE_FILE_NAME
      state_path.write_text(json.dumps(state), encoding="utf-8")

      with patch.object(
          installer,
          "get_dir",
          return_value=temporary_directory,
        ) as get_dir_mock, patch.object(
          installer,
          "_choose_repository_source",
        ) as source_mock:
        installer.init_installer(resume=True)

      source_mock.assert_not_called()
      get_dir_mock.assert_called_once_with(
        installer.tr("Please enter the previous working directory."),
        create_mode=False,
        must_empty=False,
      )
      self.assertTrue(installer.RESUME_MODE)
      self.assertEqual(
        "https://github.com/GXDE-OS/",
        installer.INSTALLATION_REMOTE_BASE,
      )
      self.assertTrue(installer._is_step_completed("build:dtk6:dtk6core"))

  def test_incremental_stage_restarts_first_incomplete_module(self) -> None:
    modules = [
      {"repo_name": "first", "display_name": "First", "branch": "main"},
      {"repo_name": "failed", "display_name": "Failed", "branch": "main"},
    ]
    installer.INSTALLATION_STATE = {
      "version": installer.STATE_VERSION,
      "repository_remote_base": "https://github.com/GXDE-OS/",
      "installation_use_ssh": False,
      "choices": {},
      "completed_steps": [
        "build:test-stage:first",
        "install:test-stage:first",
      ],
    }
    operations: list[tuple[str, str]] = []

    with patch.object(
        installer,
        "gen_artifact",
        side_effect=lambda module: operations.append(
          ("build", module["repo_name"]),
        ),
      ), patch.object(
        installer,
        "install_current_stage",
        side_effect=lambda archive: operations.append(("install", archive)),
      ), patch.object(installer, "_save_installation_state"):
      installer.install_module_stage(
        "Test stage",
        "test-stage",
        modules,
        install_incrementally=True,
      )

    self.assertEqual(
      [("build", "failed"), ("install", "test-stage")],
      operations,
    )
    self.assertTrue(
      installer._is_step_completed("build:test-stage:failed"),
    )
    self.assertTrue(
      installer._is_step_completed("install:test-stage:failed"),
    )

  def test_resume_rebuilds_when_uninstalled_artifacts_were_archived(self) -> None:
    module = {
      "repo_name": "failed",
      "display_name": "Failed",
      "branch": "main",
    }
    installer.INSTALLATION_STATE = {
      "version": installer.STATE_VERSION,
      "repository_remote_base": "https://github.com/GXDE-OS/",
      "installation_use_ssh": False,
      "choices": {},
      "completed_steps": ["build:test-stage:failed"],
    }
    operations: list[str] = []

    with TemporaryDirectory() as temporary_directory, patch.object(
        installer,
        "WORKING_DIR",
        temporary_directory,
      ), patch.object(
        installer,
        "get_pm_adapter",
        return_value=APT_ADAPTER,
      ), patch.object(
        installer,
        "gen_artifact",
        side_effect=lambda unused_module: operations.append("build"),
      ), patch.object(
        installer,
        "install_current_stage",
        side_effect=lambda unused_archive: operations.append("install"),
      ), patch.object(installer, "_save_installation_state"):
      installer.install_module_stage(
        "Test stage",
        "test-stage",
        [module],
        install_incrementally=True,
      )

    self.assertEqual(["build", "install"], operations)

  def test_resume_reuses_failed_module_checkout(self) -> None:
    module = {
      "repo_name": "failed-module",
      "display_name": "Failed module",
      "branch": "main",
    }
    with TemporaryDirectory() as temporary_directory:
      repository = Path(temporary_directory) / module["repo_name"]
      (repository / ".git").mkdir(parents=True)
      installer.WORKING_DIR = temporary_directory
      installer.RESUME_MODE = True

      with patch.object(installer, "get_pm_adapter", return_value=APT_ADAPTER), \
          patch.object(installer, "git_clone") as clone_mock, \
          patch.object(installer.shutil, "copytree") as copytree_mock, \
          patch.object(installer.os, "fork", return_value=1234), \
          patch.object(installer.os, "waitpid", return_value=(1234, 0)):
        installer.gen_artifact(module)

      clone_mock.assert_not_called()
      copytree_mock.assert_called_once_with(
        installer.INSTALLATION_SCRIPTS_DIR,
        repository,
        dirs_exist_ok=True,
      )

  def test_legacy_resume_restarts_last_existing_checkout(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      installer.WORKING_DIR = temporary_directory
      target = "qt6integration"
      (Path(temporary_directory) / target).mkdir()

      with patch.object(installer, "_save_installation_state"):
        installer._initialize_legacy_resume_state(
          "https://github.com/GXDE-OS/",
          False,
        )

      self.assertTrue(
        installer._is_step_completed("build:dtk6:dtk6declarative"),
      )
      self.assertTrue(
        installer._is_step_completed("install:dtk6:dtk6declarative"),
      )
      self.assertFalse(
        installer._is_step_completed("build:dtk6:qt6integration"),
      )


if __name__ == "__main__":
  unittest.main()
