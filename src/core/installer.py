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

import json
import os
from pathlib import Path
import shutil
import sys

from utils.translation import tr
from utils.get_input import (
  get_dir,
  get_int_with_bound_inclusive,
  get_yes_no_input,
)
from utils.git import git_clone
from utils.package_manager import get_pm_adapter
from definitions.modules import (
  CORE_MODULES,
  DTK2_ORIGINAL_MODULES,
  DTK2_QT6_MODULES,
  DTK5_MODULES,
  DTK6_MODULES,
  INFRA_MODULES,
  WAYLAND_SESSION_MODULES,
  X11_SESSION_MODULES,
  ModuleDefinition,
)

INSTALLATION_REMOTE_BASE = "https://gitee.com/GXDE-OS/"
INSTALLATION_USE_SSH = False
WORKING_DIR = "./"
RESUME_MODE = False
INSTALLATION_STATE: dict[str, object] | None = None
STATE_FILE_NAME = ".gxde-installer-state.json"
STATE_VERSION = 1
BUNDLE_ROOT = Path(
  getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent)
)
INSTALLATION_SCRIPTS_DIR = BUNDLE_ROOT / "res" / "installation_scripts"

def _state_path() -> Path:
  return Path(WORKING_DIR) / STATE_FILE_NAME

def _save_installation_state() -> None:
  if INSTALLATION_STATE is None:
    return

  state_path = _state_path()
  temporary_path = state_path.with_suffix(".tmp")
  try:
    temporary_path.write_text(
      json.dumps(INSTALLATION_STATE, indent=2, sort_keys=True) + "\n",
      encoding="utf-8",
    )
    temporary_path.replace(state_path)
  except OSError as error:
    print(
      tr("Failed to save installation resume state: ") + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

def _load_installation_state() -> None:
  global INSTALLATION_REMOTE_BASE, INSTALLATION_USE_SSH, INSTALLATION_STATE

  state_path = _state_path()
  try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as error:
    print(
      tr("Failed to load installation resume state: ") + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if (
      not isinstance(state, dict)
      or state.get("version") != STATE_VERSION
      or not isinstance(state.get("repository_remote_base"), str)
      or not isinstance(state.get("installation_use_ssh"), bool)
      or not isinstance(state.get("choices"), dict)
      or not isinstance(state.get("completed_steps"), list)
      or not all(
        isinstance(step, str) for step in state.get("completed_steps", [])
      )
  ):
    print(tr("The installation resume state is invalid."), file=sys.stderr)
    sys.exit(1)

  INSTALLATION_STATE = state
  INSTALLATION_REMOTE_BASE = str(state["repository_remote_base"])
  INSTALLATION_USE_SSH = bool(state["installation_use_ssh"])

def _is_step_completed(step: str) -> bool:
  if INSTALLATION_STATE is None:
    return False
  completed_steps = INSTALLATION_STATE.get("completed_steps", [])
  return isinstance(completed_steps, list) and step in completed_steps

def _mark_step_completed(step: str) -> None:
  if INSTALLATION_STATE is None or _is_step_completed(step):
    return
  completed_steps = INSTALLATION_STATE.setdefault("completed_steps", [])
  if not isinstance(completed_steps, list):
    print(tr("The installation resume state is invalid."), file=sys.stderr)
    sys.exit(1)
  completed_steps.append(step)
  _save_installation_state()

def _get_saved_choice(name: str) -> object | None:
  if INSTALLATION_STATE is None:
    return None
  choices = INSTALLATION_STATE.get("choices", {})
  if not isinstance(choices, dict):
    return None
  return choices.get(name)

def _save_choice(name: str, value: bool | int) -> None:
  if INSTALLATION_STATE is None:
    return
  choices = INSTALLATION_STATE.setdefault("choices", {})
  if not isinstance(choices, dict):
    print(tr("The installation resume state is invalid."), file=sys.stderr)
    sys.exit(1)
  choices[name] = value
  _save_installation_state()

def _build_step(archive_name: str, repo_name: str) -> str:
  return f"build:{archive_name}:{repo_name}"

def _module_install_step(archive_name: str, repo_name: str) -> str:
  return f"install:{archive_name}:{repo_name}"

def _stage_install_step(archive_name: str) -> str:
  return f"install:{archive_name}"

def _initialize_legacy_resume_state(
    installation_remote_base: str,
    installation_use_ssh: bool,
  ) -> None:
  global INSTALLATION_STATE

  stage_specs = (
    ("dtk5", DTK5_MODULES, True),
    ("dtk2-original", DTK2_ORIGINAL_MODULES, True),
    ("dtk6", DTK6_MODULES, True),
    ("dtk2-qt6", DTK2_QT6_MODULES, True),
    ("infra", INFRA_MODULES, False),
    ("core", CORE_MODULES, False),
    ("x11-session", X11_SESSION_MODULES, False),
    ("wayland-session", WAYLAND_SESSION_MODULES, False),
  )
  ordered_modules = [
    (archive_name, module, install_incrementally)
    for archive_name, modules, install_incrementally in stage_specs
    for module in modules
  ]
  existing_indexes = [
    index
    for index, (_, module, _) in enumerate(ordered_modules)
    if (Path(WORKING_DIR) / module["repo_name"]).is_dir()
  ]
  resume_index = max(existing_indexes) if existing_indexes else 0
  completed_steps: list[str] = []

  for index, (archive_name, module, install_incrementally) in enumerate(
      ordered_modules
    ):
    if index >= resume_index:
      continue
    repo_name = module["repo_name"]
    completed_steps.append(_build_step(archive_name, repo_name))
    if install_incrementally:
      completed_steps.append(_module_install_step(archive_name, repo_name))

  for archive_name, modules, install_incrementally in stage_specs:
    if install_incrementally or not modules:
      continue
    module_indexes = [
      index
      for index, (_, module, _) in enumerate(ordered_modules)
      if module in modules
    ]
    if module_indexes and max(module_indexes) < resume_index:
      completed_steps.append(_stage_install_step(archive_name))

  INSTALLATION_STATE = {
    "version": STATE_VERSION,
    "repository_remote_base": installation_remote_base,
    "installation_use_ssh": installation_use_ssh,
    "choices": {},
    "completed_steps": completed_steps,
  }
  _save_installation_state()

  if existing_indexes:
    target_module = ordered_modules[resume_index][1]
    print(
      tr("Legacy resume state created; restarting from module: ")
      + target_module["display_name"]
    )
  else:
    print(tr("No previous module checkout was found; restarting from the beginning."))

def _choose_repository_source() -> tuple[str, bool]:

  while True:
    print("")
    print(tr("Please choose from following repository sources:"))
    print(tr("  1. Gitee official"))
    print(tr("  2. GitHub official"))
    print(tr("  3. Manually entering mirror source"))

    source_choice = get_int_with_bound_inclusive("", 3, 1)

    if source_choice < 3:
      print(tr("Do you want to use SSH?"))
      installation_use_ssh = get_yes_no_input("")

      if source_choice == 1:
        if installation_use_ssh:
          installation_remote_base = "git@gitee.com:GXDE-OS/"
        else:
          installation_remote_base = "https://gitee.com/GXDE-OS/"
      else:
        if installation_use_ssh:
          installation_remote_base = "git@github.com:GXDE-OS/"
        else:
          installation_remote_base = "https://github.com/GXDE-OS/"
    else:
      print(tr("Third-party mirror sources are maintained by their respective "
        "providers and are not verified by the GXDE project. Before "
        "continuing, please make sure that you trust the selected source. "
        "The GXDE project is not responsible for issues caused by "
        "third-party sources."))
      proceed = get_yes_no_input(tr("Still proceed?"))
      if not proceed:
        continue

      print(tr("Please enter the mirror source URL."))
      print("  e.g. https://github.com/GXDE-OS/")
      print("  e.g. git@github.com:GXDE-OS/")
      installation_remote_base = input(tr("URL)> ")).strip()

      if not installation_remote_base.endswith("/"):
        installation_remote_base += "/"

      installation_use_ssh = installation_remote_base.startswith("git@")

    print(tr("We are now using: ") + installation_remote_base
      + tr("<REPO_NAME>"))
    print(tr("Is that correct?"))
    repo_confirm = get_yes_no_input("")
    if repo_confirm:
      return installation_remote_base, installation_use_ssh

def init_installer(resume: bool = False) -> None:
  global INSTALLATION_REMOTE_BASE, INSTALLATION_USE_SSH, WORKING_DIR
  global RESUME_MODE, INSTALLATION_STATE

  RESUME_MODE = resume
  INSTALLATION_STATE = None

  if resume:
    print("")
    WORKING_DIR = get_dir(
      tr("Please enter the previous working directory."),
      create_mode=False,
      must_empty=False,
    )
    if _state_path().is_file():
      _load_installation_state()
      print(tr("Loaded installation resume state from: ") + str(_state_path()))
      print(tr("We are now using: ") + INSTALLATION_REMOTE_BASE
        + tr("<REPO_NAME>"))
      return

    print(tr("No resume state was found; reconstructing the previous run."))
    installation_remote_base, installation_use_ssh = (
      _choose_repository_source()
    )
    INSTALLATION_REMOTE_BASE = installation_remote_base
    INSTALLATION_USE_SSH = installation_use_ssh
    _initialize_legacy_resume_state(
      installation_remote_base,
      installation_use_ssh,
    )
    return

  installation_remote_base, installation_use_ssh = _choose_repository_source()
  INSTALLATION_REMOTE_BASE = installation_remote_base
  INSTALLATION_USE_SSH = installation_use_ssh

  print("")
  WORKING_DIR = get_dir(
    tr("Please enter the working directory."),
    create_mode=True,
    must_empty=True,
  )
  INSTALLATION_STATE = {
    "version": STATE_VERSION,
    "repository_remote_base": INSTALLATION_REMOTE_BASE,
    "installation_use_ssh": INSTALLATION_USE_SSH,
    "choices": {},
    "completed_steps": [],
  }
  _save_installation_state()

def repo_cat(repo_name: str) -> str:
  return INSTALLATION_REMOTE_BASE + repo_name

def repo_clone_dest_cat(repo_name: str) -> str:
  return WORKING_DIR + "/" + repo_name

def gen_artifact(module: ModuleDefinition) -> None:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    print(
      tr("Warning: no supported package manager adapter is available."),
      file=sys.stderr,
    )
    sys.exit(1)

  repo_name = module["repo_name"]
  display_name = module["display_name"]
  repo_dest = repo_clone_dest_cat(repo_name)
  repo_path = Path(repo_dest)
  if RESUME_MODE and (repo_path / ".git").is_dir():
    print(tr("Resume: reusing existing repository checkout: ") + display_name)
  else:
    clone_res = git_clone(
      repo_cat(repo_name),
      repo_dest,
      branch=module["branch"],
    )
    if not clone_res:
      print(tr("Failed to clone repository: ") + display_name)
      print(tr("Installation failed due to error occurred."))
      sys.exit(1)

    print(tr("Successfully cloned repository: ") + display_name)
  print(tr("Detected package manager: ") + pm_adapter.display_name)

  shutil.copytree(
    INSTALLATION_SCRIPTS_DIR,
    Path(repo_dest),
    dirs_exist_ok=True,
  )
  print(tr("Successfully generated installation scripts for repository: ")
    + display_name)

  build_pid = os.fork()
  if build_pid == 0:
    try:
      os.chdir(repo_dest)
      os.execvp(pm_adapter.build_command[0], list(pm_adapter.build_command))
    except OSError as error:
      print(
        tr("Failed to start package build: ") + str(error),
        file=sys.stderr,
        flush=True,
      )
      os._exit(1)

  _, build_status = os.waitpid(build_pid, 0)
  if os.waitstatus_to_exitcode(build_status) != 0:
    print(tr("Failed to build repository: ") + display_name)
    print(tr("Installation failed due to error occurred."))
    sys.exit(1)

  print(tr("Successfully built repository: ") + display_name)

def install_current_stage(archive_name: str) -> None:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    print(
      tr("Warning: no supported package manager adapter is available."),
      file=sys.stderr,
    )
    sys.exit(1)

  archive_path = Path(archive_name)
  if (
      archive_path.is_absolute()
      or len(archive_path.parts) != 1
      or archive_name in {".", ".."}
    ):
    print(
      tr("Warning: invalid artifact archive name: ") + archive_name,
      file=sys.stderr,
    )
    sys.exit(1)

  artifacts_dir = (Path(WORKING_DIR) / "artifacts").resolve()
  try:
    packages = sorted({
      package.resolve()
      for pattern in pm_adapter.artifact_patterns
      for package in artifacts_dir.glob(pattern)
      if package.is_file()
    })
  except OSError as error:
    print(
      tr("Warning: failed to read the artifacts directory: ") + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if not packages:
    print(
      tr("Warning: no package artifacts were found in: ")
      + str(artifacts_dir),
      file=sys.stderr,
    )
    sys.exit(1)

  try:
    install_pid = os.fork()
  except OSError as error:
    print(
      tr("Warning: failed to create the package installation process: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if install_pid == 0:
    try:
      install_command = [
        *pm_adapter.install_command,
        *(str(package) for package in packages),
      ]
      os.execvp(install_command[0], install_command)
    except OSError as error:
      print(
        tr("Warning: failed to start package installation: ") + str(error),
        file=sys.stderr,
        flush=True,
      )
      os._exit(1)

  try:
    _, install_status = os.waitpid(install_pid, 0)
  except OSError as error:
    print(
      tr("Warning: failed while waiting for package installation: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if os.waitstatus_to_exitcode(install_status) != 0:
    print(
      tr("Warning: failed to install the current stage: ") + archive_name,
      file=sys.stderr,
    )
    sys.exit(1)

  archive_dir = artifacts_dir / archive_name
  try:
    archive_dir.mkdir(exist_ok=True)
    for package in packages:
      package.replace(archive_dir / package.name)
  except OSError as error:
    print(
      tr("Warning: failed to archive installed packages: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  print(tr("Successfully installed the current stage: ") + archive_name)
  print(tr("Archived installed packages in: ") + str(archive_dir))

def install_dtk2_original() -> None:
  install_module_stage(
    tr("DTK2 original compatibility dependencies"),
    "dtk2-original",
    DTK2_ORIGINAL_MODULES,
    install_incrementally=True,
  )

def install_dtk2_qt6() -> None:
  install_module_stage(
    tr("DTK2 Qt6 port compatibility dependencies"),
    "dtk2-qt6",
    DTK2_QT6_MODULES,
    install_incrementally=True,
  )

def _has_unarchived_package_artifacts() -> bool:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    return False

  artifacts_dir = Path(WORKING_DIR) / "artifacts"
  return any(
    package.is_file()
    for pattern in pm_adapter.artifact_patterns
    for package in artifacts_dir.glob(pattern)
  )

def install_module_stage(
    display_name: str,
    archive_name: str,
    modules: list[ModuleDefinition],
    *,
    install_incrementally: bool = False,
) -> None:
  print(tr("Installing module stage: ") + display_name)
  for module in modules:
    repo_name = module["repo_name"]
    build_step = _build_step(archive_name, repo_name)
    install_step = _module_install_step(archive_name, repo_name)
    build_completed = _is_step_completed(build_step)
    install_completed = (
      install_incrementally and _is_step_completed(install_step)
    )
    rebuild_missing_artifacts = (
      build_completed
      and install_incrementally
      and not install_completed
      and not _has_unarchived_package_artifacts()
    )

    if rebuild_missing_artifacts:
      print(
        tr("Resume: package artifacts are missing; rebuilding repository: ")
        + module["display_name"]
      )
      gen_artifact(module)
    elif build_completed:
      print(
        tr("Resume: skipping completed repository build: ")
        + module["display_name"]
      )
    else:
      gen_artifact(module)
      _mark_step_completed(build_step)

    if install_incrementally:
      # DTK repositories consume freshly built development packages from
      # earlier repositories in the same stage. Install each repository's
      # complete artifact set before building the next one, while keeping one
      # archive directory for the whole stage.
      if install_completed:
        print(
          tr("Resume: skipping completed repository installation: ")
          + module["display_name"]
        )
      else:
        install_current_stage(archive_name)
        _mark_step_completed(install_step)
    print()

  if not install_incrementally:
    install_step = _stage_install_step(archive_name)
    if _is_step_completed(install_step):
      print(tr("Resume: skipping completed module stage: ") + display_name)
    else:
      install_current_stage(archive_name)
      _mark_step_completed(install_step)

def should_install_gxde_dtk(version: int) -> bool:
  version_name = f"DTK{version}"
  choice_name = f"dtk{version}_gxde"
  saved_choice = _get_saved_choice(choice_name)
  if isinstance(saved_choice, bool):
    print(
      tr("Resume: using the saved source choice for {version_name}.").format(
        version_name=version_name,
      )
    )
    return saved_choice

  print("")
  print(tr("Please choose the source for {version_name}.").format(
    version_name=version_name,
  ))
  print(tr("Warning: using the system-provided version instead of the GXDE-"
    "modified version may cause some GXDE behavior, such as blur effects, "
    "to differ from the intended experience."))
  print(tr("Warning: installing the GXDE-modified version may change DTK "
    "behavior in other desktop sessions. GXDE does not guarantee that DTK "
    "applications will behave as expected outside the GXDE session."))
  choice = get_yes_no_input(
    tr("Build and install the GXDE-modified version of {version_name}?")
    .format(version_name=version_name),
  )
  _save_choice(choice_name, choice)
  return choice

def install_dtk5() -> None:
  if should_install_gxde_dtk(5):
    install_module_stage(
      "DTK5",
      "dtk5",
      DTK5_MODULES,
      install_incrementally=True,
    )
  else:
    print(tr("Using the system-provided DTK5 packages."))

def install_dtk6() -> None:
  if should_install_gxde_dtk(6):
    install_module_stage(
      "DTK6",
      "dtk6",
      DTK6_MODULES,
      install_incrementally=True,
    )
  else:
    print(tr("Using the system-provided DTK6 packages."))

def install_infra() -> None:
  install_module_stage(
    tr("GXDE infrastructure dependencies"),
    "infra",
    INFRA_MODULES,
  )

def install_core() -> None:
  install_module_stage(tr("GXDE core"), "core", CORE_MODULES)

def install_named_packages(
    package_names: tuple[str, ...],
    display_name: str,
  ) -> None:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    print(
      tr("Warning: no supported package manager adapter is available."),
      file=sys.stderr,
    )
    sys.exit(1)

  try:
    install_pid = os.fork()
  except OSError as error:
    print(
      tr("Warning: failed to create the package installation process: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if install_pid == 0:
    try:
      install_command = [*pm_adapter.install_command, *package_names]
      os.execvp(install_command[0], install_command)
    except OSError as error:
      print(
        tr("Warning: failed to start package installation: ") + str(error),
        file=sys.stderr,
        flush=True,
      )
      os._exit(1)

  try:
    _, install_status = os.waitpid(install_pid, 0)
  except OSError as error:
    print(
      tr("Warning: failed while waiting for package installation: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if os.waitstatus_to_exitcode(install_status) != 0:
    print(
      tr("Warning: failed to install optional component: ") + display_name,
      file=sys.stderr,
    )
    sys.exit(1)

  print(tr("Successfully installed optional component: ") + display_name)

def install_session_components() -> None:
  saved_session_choice = _get_saved_choice("session_choice")
  if (
      isinstance(saved_session_choice, int)
      and not isinstance(saved_session_choice, bool)
      and 1 <= saved_session_choice <= 3
  ):
    session_choice = saved_session_choice
    print(tr("Resume: using the saved GXDE session choice."))
  else:
    print("")
    print(tr("Please choose the GXDE session type to install:"))
    print(tr("  1. X11 session (including compositor)"))
    print(tr("  2. Wayland session (including compositor)"))
    print(tr("  3. Both X11 and Wayland sessions"))
    session_choice = get_int_with_bound_inclusive("", 3, 1)
    _save_choice("session_choice", session_choice)

  if session_choice in {1, 3}:
    install_module_stage(
      tr("GXDE X11 session and compositor"),
      "x11-session",
      X11_SESSION_MODULES,
    )
  if session_choice in {2, 3}:
    install_module_stage(
      tr("GXDE Wayland session and compositor"),
      "wayland-session",
      WAYLAND_SESSION_MODULES,
    )

  saved_apm_choice = _get_saved_choice("install_apm")
  if isinstance(saved_apm_choice, bool):
    install_apm = saved_apm_choice
    print(tr("Resume: using the saved APM choice."))
  else:
    print("")
    install_apm = get_yes_no_input(tr("Install APM (Amber Package Manager)?"))
    _save_choice("install_apm", install_apm)

  if install_apm:
    apm_step = "install:optional:apm"
    if _is_step_completed(apm_step):
      print(tr("Resume: skipping completed optional component: APM"))
    else:
      install_named_packages(("apm",), "APM")
      _mark_step_completed(apm_step)
  else:
    print(tr("Skipping APM installation."))

def install_desktop_environment() -> None:
  if _is_step_completed("installation:complete"):
    print(tr("The installation recorded in this working directory is already complete."))
    return

  install_dtk5()
  # The original DTK2-Widget needs DTK5 Core and DTK Log, while GXDE's Qt5
  # integration needs the resulting libdtkwidget2-dev package.
  install_dtk2_original()
  install_dtk6()
  # The Qt6 port consumes the DTK6 development packages.
  install_dtk2_qt6()
  install_infra()
  install_core()
  install_session_components()
  _mark_step_completed("installation:complete")
  print(tr("Installation completed; resume state has been saved."))

__all__ = [
  "init_installer",
  "install_desktop_environment",
]
