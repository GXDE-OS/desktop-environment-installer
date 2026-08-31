#!/bin/bash

# Copyright (C) 2026 CharOfString
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This script builds installation packages for deployment and removal on test systems.
#
# Project metadata is derived from debian/ so this script normally needs no
# per-project changes:
#   - Build dependencies come from Build-Depends in debian/control.
#   - The source package name comes from debian/changelog.
#   - The build system (CMake, Meson, etc.) is selected by debian/rules.
#
# Usage: ./build-deb <options>
#
# Options:
#    -b, --binary          Build binary packages only (default)
#    -d, --install-deps    Install build dependencies before building
#    -c, --clean           Remove buildinfo and changes files, then exit
#    -h, --help            Show this help message

set -o pipefail

# This script is installed in the project root next to debian/.
CUR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ_ROOT="$CUR_SCRIPT_DIR"
ARTIFACTS_DIR="$(dirname "$PROJ_ROOT")/artifacts"

# Options
BUILD_BIN=true
INSTALL_DEPS=false
ACT_CLEANUPS=false

# Source package name, derived from debian/changelog.
PKG_NAME=""

# Print help.
print_help() {
    echo "Usage: $0 <options>"
    echo ""
    echo "Options:"
    echo "  -b, --binary          Build binary packages only (default)"
    echo "  -d, --install-deps    Install dependencies from debian/control, then build"
    echo "  -c, --clean           Remove buildinfo and changes files, then exit"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -d                # Install build dependencies and build"
    echo "  $0                   # Build with dependencies already installed"
    echo "  $0 -c                # Remove build metadata"
    exit 0
}

# Parse options.
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--binary)
                BUILD_BIN=true
                shift
                ;;
            -c|--clean)
                ACT_CLEANUPS=true
                shift
                ;;
            -d|--install-deps)
                INSTALL_DEPS=true
                BUILD_BIN=true
                shift
                ;;
            -h|--help)
                print_help
                ;;
            *)
                echo "Unknown option: $1"
                echo "See the following help:"
                print_help
                ;;
        esac
    done
}

# Return whether a command is available.
is_cmd_exists() {
    command -v "$1" &> /dev/null
}

# Validate the project layout and read the source package name.
detect_project() {
    if [[ ! -f "$PROJ_ROOT/debian/control" || ! -f "$PROJ_ROOT/debian/changelog" ]]; then
        echo "Error: debian/control or debian/changelog was not found in $PROJ_ROOT."
        echo "This script must be placed in the project root next to debian/."
        exit 1
    fi
    PKG_NAME="$(cd "$PROJ_ROOT" && dpkg-parsechangelog -S Source 2>/dev/null)"
    if [[ -z "$PKG_NAME" ]]; then
        echo "Error: could not read the source package name from debian/changelog."
        exit 1
    fi
    echo "Project root: $PROJ_ROOT"
    echo "Source package: $PKG_NAME"
    echo "Artifacts directory: $ARTIFACTS_DIR"
}

# Check the basic toolchain. Other tools come from Build-Depends.
check_toolchains() {
    echo "Checking the basic toolchain..."
    local missing_tools=()

    # dpkg-buildpackage and dpkg-parsechangelog are provided by dpkg-dev.
    if ! is_cmd_exists "dpkg-buildpackage"; then
        missing_tools+=("dpkg-dev")
    fi
    # apt-get build-dep installs Build-Depends automatically.
    if ! is_cmd_exists "apt-get"; then
        missing_tools+=("apt")
    fi
    if ! is_cmd_exists "git"; then
        missing_tools+=("git")
    fi

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo "Missing required tools: ${missing_tools[*]}"
        echo "Try: sudo apt install ${missing_tools[*]}"
        exit 1
    fi
    echo "Basic toolchain check passed."
}

# Apply source-level compatibility fixes bundled with the installer.  Patches
# are scoped to their source package and skipped once the fixed code is
# present, so updated repositories and unrelated package-manager backends are
# not rewritten.
apply_source_compatibility() {
    local patch_file="$PROJ_ROOT/patches/dtk6widget-qt-6.10.patch"

    if [[ "$PKG_NAME" != "dtk6widget" ]]; then
        return
    fi

    if grep -q 'D_DECLARE_PRIVATE_MEMBER(QDragManager_m_platformDrag_tag' \
        "$PROJ_ROOT/src/widgets/dtabbar.cpp" \
        && grep -q 'QT_VERSION_CHECK(6, 10, 1)' \
        "$PROJ_ROOT/src/widgets/dtabbar.cpp"; then
        echo "Source compatibility: DTK6 Widget already supports Qt 6.10.2."
        return
    fi

    if [[ ! -f "$patch_file" ]]; then
        echo "Error: bundled DTK6 Widget compatibility patch was not found."
        exit 1
    fi
    if ! git -C "$PROJ_ROOT" apply --check "$patch_file"; then
        echo "Error: DTK6 Widget Qt 6.10 compatibility patch does not apply cleanly."
        exit 1
    fi

    echo "Source compatibility: applying DTK6 Widget Qt 6.10 fixes."
    if ! git -C "$PROJ_ROOT" apply "$patch_file"; then
        echo "Error: failed to apply DTK6 Widget Qt 6.10 compatibility fixes."
        exit 1
    fi
}

# Drop build dependencies that were retired by the active APT distribution.
#
# Qt 6.10 stopped publishing qt6-wayland-dev-tools separately.  Ubuntu 26.04
# ships qt6-wayland-dev and qt6-wayland-private-dev without that package, but
# older DTK packaging still names it explicitly.  Keep the dependency on
# distributions that provide it, and only adjust the cloned source tree when
# APT reports that no installation candidate exists.
apply_apt_build_dep_compatibility() {
    local package="qt6-wayland-dev-tools"
    local candidate

    if ! grep -Eq "(^|[[:space:],])${package}([[:space:],]|$)" \
        "$PROJ_ROOT/debian/control"; then
        return
    fi

    candidate="$(apt-cache policy "$package" 2>/dev/null \
        | awk '/^[[:space:]]*Candidate:/ { print $2; exit }')"
    if [[ -n "$candidate" && "$candidate" != "(none)" ]]; then
        return
    fi

    echo "APT compatibility: removing unavailable build dependency $package."
    sed -i -E \
        "s/(^|[[:space:]])${package}([[:space:]]*,[[:space:]]*)?/\\1/" \
        "$PROJ_ROOT/debian/control"
}

# Install build dependencies from Build-Depends in debian/control.
auto_install_deps() {
    if [[ "$INSTALL_DEPS" != true ]]; then
        return
    fi
    echo "Installing build dependencies from debian/control..."
    if ! sudo apt-get update; then
        echo "Error: failed to update package indexes."
        exit 1
    fi
    apply_apt_build_dep_compatibility

    echo ""
    echo ">>> Note: apt is running without -y. Carefully review the packages that"
    echo ">>>       will be installed or removed, especially GXDE system packages."
    echo ""
    # apt-get build-dep reads Build-Depends from this project's debian/control.
    if ! sudo apt-get build-dep "$PROJ_ROOT"; then
        echo "Error: failed to install build dependencies."
        exit 1
    fi
    echo "Build dependencies installed."
}

# Prefetch Meson wrap subprojects before Debian's nodownload build starts.
prefetch_subprojects() {
    [[ -d subprojects ]] || return 0
    shopt -s nullglob
    local wraps=(subprojects/*.wrap)
    shopt -u nullglob
    [[ ${#wraps[@]} -eq 0 ]] && return 0

    if ! is_cmd_exists meson; then
        echo "Warning: Meson was not found; skipping subproject prefetch."
        return 0
    fi
    echo "Prefetching Meson wrap subprojects..."
    if ! meson subprojects download; then
        echo "Error: Meson subproject download failed. Check the network, Git, and wrap configuration."
        exit 1
    fi
}

# Remove build metadata only. Package artifacts are intentionally preserved.
exec_clean() {
    echo "Removing buildinfo and changes files..."

    if [[ -n "$PKG_NAME" ]]; then
        rm -f "$PROJ_ROOT"/../"${PKG_NAME}"_*.buildinfo \
              "$PROJ_ROOT"/../"${PKG_NAME}"_*.changes
    fi

    echo "Build metadata cleanup complete."
}

# Build packages and collect artifacts.
exec_build() {
    local dpkg_args=("-us" "-uc")
    local build_marker
    local package
    local packages=()
    [[ "$BUILD_BIN" == true ]] && dpkg_args+=("-b")

    cd "$PROJ_ROOT" || exit 1
    prefetch_subprojects
    mkdir -p "$ARTIFACTS_DIR"
    build_marker="$(mktemp "$PROJ_ROOT/../.${PKG_NAME}.build.XXXXXX")" || exit 1

    echo "Building packages with dpkg-buildpackage (arguments: ${dpkg_args[*]})..."
    if ! dpkg-buildpackage "${dpkg_args[@]}"; then
        rm -f "$build_marker"
        echo "Error: package build failed."
        exit 1
    fi

    while IFS= read -r -d '' package; do
        packages+=("$package")
    done < <(find "$PROJ_ROOT/.." -maxdepth 1 -type f \
        \( -name '*.deb' -o -name '*.ddeb' -o -name '*.udeb' \) \
        -newer "$build_marker" -print0)
    rm -f "$build_marker"

    for package in "${packages[@]}"; do
        mv -f -- "$package" "$ARTIFACTS_DIR/"
    done

    exec_clean

    echo "Build complete. Package artifacts:"
    if [[ ${#packages[@]} -gt 0 ]]; then
        printf '  %s\n' "${packages[@]##*/}"
        echo "Artifacts directory: $ARTIFACTS_DIR"
    else
        echo "  No .deb, .ddeb, or .udeb files were produced; check the build output above."
    fi
}

# Main entry point.
main() {
    parse_args "$@"
    detect_project

    if [[ "$ACT_CLEANUPS" == true ]]; then
        exec_clean
        return
    fi

    check_toolchains
    apply_source_compatibility
    auto_install_deps
    exec_build
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
