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
from unittest.mock import patch

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
  def setUp(self) -> None:
    installer.RESUME_MODE = False
    installer.INSTALLATION_STATE = None

  def test_install_original_dtk2_installs_each_module_incrementally(
      self,
    ) -> None:
    operations: list[tuple[str, object]] = []

    with patch.object(
        installer,
        "gen_artifact",
        side_effect=lambda module: operations.append(("build", module)),
      ), patch.object(
        installer,
        "install_current_stage",
        side_effect=lambda archive: operations.append(("install", archive)),
      ):
      installer.install_dtk2_original()

    self.assertEqual([
      operation
      for module in installer.DTK2_ORIGINAL_MODULES
      for operation in (("build", module), ("install", "dtk2-original"))
    ], operations)

  def test_install_qt6_dtk2_installs_each_module_incrementally(self) -> None:
    operations: list[tuple[str, object]] = []

    with patch.object(
        installer,
        "gen_artifact",
        side_effect=lambda module: operations.append(("build", module)),
      ), patch.object(
        installer,
        "install_current_stage",
        side_effect=lambda archive: operations.append(("install", archive)),
      ):
      installer.install_dtk2_qt6()

    self.assertEqual([
      operation
      for module in installer.DTK2_QT6_MODULES
      for operation in (("build", module), ("install", "dtk2-qt6"))
    ], operations)

  def test_dtk2_phases_contain_original_and_qt6_ports(self) -> None:
    original_repositories = [
      module["repo_name"]
      for module in installer.DTK2_ORIGINAL_MODULES
    ]
    qt6_repositories = [
      module["repo_name"]
      for module in installer.DTK2_QT6_MODULES
    ]

    self.assertEqual([
      "dtk2core",
      "dde-qt-dbus-factory",
      "dtk2widget",
      "gxde-qt5integration",
    ], original_repositories)
    self.assertEqual([
      "dtk2widget-qt6",
      "gxde-qt6-integration",
    ], qt6_repositories)

  def test_dtk_modules_are_in_build_dependency_order(self) -> None:
    dtk2_original_repositories = [
      module["repo_name"]
      for module in installer.DTK2_ORIGINAL_MODULES
    ]
    dtk5_repositories = [
      module["repo_name"]
      for module in installer.DTK5_MODULES
    ]
    dtk6_repositories = [
      module["repo_name"]
      for module in installer.DTK6_MODULES
    ]

    self.assertLess(
      dtk2_original_repositories.index("dtk2core"),
      dtk2_original_repositories.index("dtk2widget"),
    )
    self.assertLess(
      dtk5_repositories.index("dtklog"),
      dtk5_repositories.index("dtk5core"),
    )
    self.assertLess(
      dtk5_repositories.index("dtk5core"),
      dtk5_repositories.index("dtk5gui"),
    )
    self.assertLess(
      dtk5_repositories.index("dtk5gui"),
      dtk5_repositories.index("dtk5widget"),
    )
    self.assertLess(
      dtk6_repositories.index("dtk6log"),
      dtk6_repositories.index("dtk6core"),
    )
    self.assertLess(
      dtk6_repositories.index("dtk6core"),
      dtk6_repositories.index("dtk6gui"),
    )
    self.assertLess(
      dtk6_repositories.index("dtk6gui"),
      dtk6_repositories.index("dtk6widget"),
    )
    self.assertLess(
      dtk6_repositories.index("dtk6declarative"),
      dtk6_repositories.index("dde-qt6platform-plugins"),
    )
    self.assertLess(
      dtk6_repositories.index("dde-qt6platform-plugins"),
      dtk6_repositories.index("qt6integration"),
    )

  def test_dtk5_common_uses_the_matching_dtk_source_line(self) -> None:
    dtk5_common = next(
      module
      for module in installer.DTK5_MODULES
      if module["repo_name"] == "dtk5common"
    )

    self.assertEqual("6.7.43", dtk5_common["branch"])

  def test_system_dtk6_choice_skips_gxde_module_builds(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_yes_no_input",
        return_value=False,
      ), patch.object(installer, "install_module_stage") as stage_mock, \
        redirect_stdout(output):
      installer.install_dtk6()

    stage_mock.assert_not_called()
    self.assertIn(
      installer.tr("Warning: using the system-provided version instead of "
        "the GXDE-modified version may cause some GXDE behavior, such as "
        "blur effects, to differ from the intended experience."),
      output.getvalue(),
    )
    self.assertIn(
      installer.tr("Warning: installing the GXDE-modified version may change "
        "DTK behavior in other desktop sessions. GXDE does not guarantee "
        "that DTK applications will behave as expected outside the GXDE "
        "session."),
      output.getvalue(),
    )
    self.assertIn(
      installer.tr("Using the system-provided DTK6 packages."),
      output.getvalue(),
    )

  def test_gxde_dtk5_choice_installs_the_dtk5_stage(self) -> None:
    with patch.object(
        installer,
        "get_yes_no_input",
        return_value=True,
      ), patch.object(installer, "install_module_stage") as stage_mock:
      installer.install_dtk5()

    stage_mock.assert_called_once_with(
      "DTK5",
      "dtk5",
      installer.DTK5_MODULES,
      install_incrementally=True,
    )

  def test_session_selection_can_install_both_sessions_and_apm(self) -> None:
    with patch.object(
        installer,
        "get_int_with_bound_inclusive",
        return_value=3,
      ), patch.object(
        installer,
        "get_yes_no_input",
        return_value=True,
      ), patch.object(
        installer,
        "install_module_stage",
      ) as stage_mock, patch.object(
        installer,
        "install_named_packages",
      ) as packages_mock:
      installer.install_session_components()

    self.assertEqual(2, stage_mock.call_count)
    self.assertEqual("x11-session", stage_mock.call_args_list[0].args[1])
    self.assertEqual("wayland-session", stage_mock.call_args_list[1].args[1])
    packages_mock.assert_called_once_with(("apm",), "APM")

  def test_optional_packages_use_the_detected_manager_adapter(self) -> None:
    test_adapter = package_manager.PackageManagerAdapter(
      detection_command="test-pm",
      display_name="Test Package Manager",
      build_command=("./test-build",),
      artifact_patterns=("*.pkg",),
      install_command=("doas", "test-pm", "install"),
    )

    with patch.object(
        installer,
        "get_pm_adapter",
        return_value=test_adapter,
      ), patch.object(installer.os, "fork", return_value=0), patch.object(
        installer.os,
        "execvp",
        side_effect=SystemExit,
      ) as execvp_mock, self.assertRaises(SystemExit):
      installer.install_named_packages(("apm",), "APM")

    execvp_mock.assert_called_once_with(
      "doas",
      ["doas", "test-pm", "install", "apm"],
    )

  def test_desktop_installation_uses_dependency_stage_order(self) -> None:
    stage_order: list[str] = []

    with patch.object(
        installer,
        "install_dtk5",
        side_effect=lambda: stage_order.append("dtk5"),
      ), patch.object(
        installer,
        "install_dtk2_original",
        side_effect=lambda: stage_order.append("dtk2-original"),
      ), patch.object(
        installer,
        "install_dtk6",
        side_effect=lambda: stage_order.append("dtk6"),
      ), patch.object(
        installer,
        "install_dtk2_qt6",
        side_effect=lambda: stage_order.append("dtk2-qt6"),
      ), patch.object(
        installer,
        "install_infra",
        side_effect=lambda: stage_order.append("infra"),
      ), patch.object(
        installer,
        "install_core",
        side_effect=lambda: stage_order.append("core"),
      ), patch.object(
        installer,
        "install_session_components",
        side_effect=lambda: stage_order.append("sessions"),
      ):
      installer.install_desktop_environment()

    self.assertEqual(
      [
        "dtk5",
        "dtk2-original",
        "dtk6",
        "dtk2-qt6",
        "infra",
        "core",
        "sessions",
      ],
      stage_order,
    )

  def test_wayland_stage_contains_current_session_meta_dependencies(
      self,
    ) -> None:
    wayland_repositories = {
      module["repo_name"]
      for module in installer.WAYLAND_SESSION_MODULES
    }

    self.assertTrue({
      "gxde-wlcom",
      "dde-grand-search",
      "gxde-sni-server",
      "gxde-top-panel-plugins",
      "gxde-terminal",
      "gxde-display-manager",
      "gxde-wayland-session",
    }.issubset(wayland_repositories))

  def test_distribution_base_package_is_not_installed_as_desktop_core(
      self,
    ) -> None:
    core_repositories = {
      module["repo_name"]
      for module in installer.CORE_MODULES
    }

    self.assertNotIn("gxde-desktop-base", core_repositories)

  def test_core_stage_contains_runtime_feature_dependencies(self) -> None:
    infra_repositories = {
      module["repo_name"]
      for module in installer.INFRA_MODULES
    }
    core_repositories = {
      module["repo_name"]
      for module in installer.CORE_MODULES
    }

    self.assertIn("gxde-k9", infra_repositories)
    self.assertIn("golang-gxde-dev", infra_repositories)
    self.assertTrue({
      "gxde-account-faces",
      "gxde-app-installer",
      "gxde-app-upgrader",
      "gxde-app-uninstaller",
      "gxde-icon-theme",
      "gxde-globalmenu-service",
      "gxde-requ",
      "gxde-shell-compressor",
      "gxde-sound-theme",
      "gxde-time-screensaver",
      "deepin-gtk-theme",
      "deepin-menu",
      "deepin-screensaver",
    }.issubset(core_repositories))

  def test_gxde_go_sources_precede_api(self) -> None:
    infra_repositories = [
      module["repo_name"]
      for module in installer.INFRA_MODULES
    ]

    self.assertLess(
      infra_repositories.index("golang-gxde-dev"),
      infra_repositories.index("gxde-api"),
    )

  def test_infra_installs_modules_incrementally(self) -> None:
    with patch.object(installer, "install_module_stage") as install_stage:
      installer.install_infra()

    install_stage.assert_called_once_with(
      installer.tr("GXDE infrastructure dependencies"),
      "infra",
      installer.INFRA_MODULES,
      install_incrementally=True,
    )

  def test_x11_stage_contains_kwin_runtime_dependencies(self) -> None:
    x11_repositories = {
      module["repo_name"]
      for module in installer.X11_SESSION_MODULES
    }

    self.assertTrue({
      "gxde-kglobalacceld",
      "gxde-kwin",
      "gxde-wm-shim",
    }.issubset(x11_repositories))

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

  def test_incremental_installs_accumulate_in_one_stage_archive(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      artifacts_dir = Path(temporary_directory) / "artifacts"
      artifacts_dir.mkdir()

      with patch.object(installer, "WORKING_DIR", temporary_directory), \
          patch.object(
            installer,
            "get_pm_adapter",
            return_value=APT_ADAPTER,
          ), patch.object(installer.os, "fork", return_value=4321), \
          patch.object(installer.os, "waitpid", return_value=(4321, 0)):
        (artifacts_dir / "dtk-common.deb").touch()
        installer.install_current_stage("dtk5")
        (artifacts_dir / "dtk-log.deb").touch()
        installer.install_current_stage("dtk5")

      archive_dir = artifacts_dir / "dtk5"
      self.assertTrue((archive_dir / "dtk-common.deb").is_file())
      self.assertTrue((archive_dir / "dtk-log.deb").is_file())

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
      for patch_name in (
        "dtk2widget6-qt-6.10-enum-string-format.patch",
        "dtk2widget6-qt-6.10-moc-namespace.patch",
        "dtk2widget6-qt-6.10-tab-offsets.patch",
        "dtk6widget-qt-6.10.patch",
        "gxde-qt6integration-qt-6.10-moc-namespace.patch",
        "qt6integration-qt-6.10-private-targets.patch",
        "qt6integration-qt-6.10-generic-theme-header.patch",
        "qt6integration-missing-private-includes.patch",
        "qt6integration-qt-6.9-geometry-change.patch",
    ):
        copied_patch = repo_dest / "patches" / patch_name
        self.assertTrue(copied_patch.is_file())
        self.assertEqual(
          (
            installer.INSTALLATION_SCRIPTS_DIR
            / "patches"
            / patch_name
          ).read_bytes(),
          copied_patch.read_bytes(),
        )
      bundled_xcb_headers = (
        repo_dest
        / "compat"
        / "qt6-xcb-private-headers"
        / "6.10.2"
      )
      self.assertEqual(
        48,
        len(list(bundled_xcb_headers.rglob("*.h"))),
      )
      self.assertTrue((bundled_xcb_headers / "qxcbconnection.h").is_file())
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
        patch.object(installer, "_save_installation_state"), \
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

  def test_selects_official_github_source_without_ssh_login(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_dir",
        return_value="/tmp/gxde-work",
      ), patch.object(
        installer,
        "_save_installation_state",
      ), patch.object(
        installer,
        "get_int_with_bound_inclusive",
        return_value=2,
      ), patch.object(
        installer,
        "get_yes_no_input",
        side_effect=[False, True],
      ), redirect_stdout(output):
      installer.init_installer()

    self.assertIn("https://github.com/GXDE-OS/", output.getvalue())
    self.assertEqual(
      "https://github.com/GXDE-OS/",
      installer.INSTALLATION_REMOTE_BASE,
    )
    self.assertFalse(installer.INSTALLATION_USE_SSH)

  def test_reselects_source_after_rejecting_custom_source(self) -> None:
    output = StringIO()

    with patch.object(
        installer,
        "get_dir",
        return_value="/tmp/gxde-work",
      ), patch.object(
        installer,
        "_save_installation_state",
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
