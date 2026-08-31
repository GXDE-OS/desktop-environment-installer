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

# Apply one bundled source patch after checking that it matches cleanly.
apply_bundled_source_patch() {
    local description="$1"
    local patch_file="$2"

    if [[ ! -f "$patch_file" ]]; then
        echo "Error: bundled compatibility patch was not found: $patch_file"
        exit 1
    fi
    if ! git -C "$PROJ_ROOT" apply --check "$patch_file"; then
        echo "Error: $description compatibility patch does not apply cleanly."
        exit 1
    fi

    echo "Source compatibility: applying $description fixes."
    if ! git -C "$PROJ_ROOT" apply "$patch_file"; then
        echo "Error: failed to apply $description compatibility fixes."
        exit 1
    fi
}

# Debian allows exactly one address in Maintainer; additional maintainers
# belong in Uploaders.  Some GXDE source packages put a comma-separated list
# in Maintainer, which modern dpkg-source rejects before the build starts.
normalize_debian_maintainer_metadata() {
    local control_file="$PROJ_ROOT/debian/control"
    local maintainer_line
    local maintainers
    local primary
    local additional
    local has_uploaders=false
    local temporary_file

    maintainer_line="$(grep -m1 '^Maintainer:' "$control_file")"
    maintainers="${maintainer_line#Maintainer:}"
    if [[ "$maintainers" != *,* ]]; then
        return
    fi

    primary="${maintainers%%,*}"
    additional="${maintainers#*,}"
    primary="$(printf '%s\n' "$primary" \
        | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]*</ </g')"
    additional="$(printf '%s\n' "$additional" \
        | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]*</ </g')"
    grep -q '^Uploaders:' "$control_file" && has_uploaders=true

    temporary_file="$(mktemp "$PROJ_ROOT/debian/control.XXXXXX")" || {
        echo "Error: failed to create a temporary Debian control file."
        return 1
    }
    if ! awk \
        -v primary="$primary" \
        -v additional="$additional" \
        -v has_uploaders="$has_uploaders" '
          /^Maintainer:/ {
            print "Maintainer: " primary
            if (has_uploaders != "true") {
              print "Uploaders: " additional
            }
            next
          }
          /^Uploaders:/ && has_uploaders == "true" {
            sub(/^Uploaders:[[:space:]]*/, "")
            print "Uploaders: " additional ", " $0
            next
          }
          { print }
        ' "$control_file" > "$temporary_file"; then
        rm -f "$temporary_file"
        echo "Error: failed to normalize Debian maintainer metadata."
        return 1
    fi
    chmod --reference="$control_file" "$temporary_file"
    mv -f "$temporary_file" "$control_file"
    echo "Source compatibility: normalized Debian maintainer metadata."
}

# Apply source-level compatibility fixes bundled with the installer. Patches
# are scoped to their source package and skipped once the fixed code is
# present, so updated repositories are not rewritten.
apply_source_compatibility() {
    if ! normalize_debian_maintainer_metadata; then
        exit 1
    fi

    case "$PKG_NAME" in
        gxde-default-settings)
            local legacy_iwlwifi_config="$PROJ_ROOT/etc.d/modprobe.d/iwlwifi.conf"
            local gxde_iwlwifi_config="$PROJ_ROOT/etc.d/modprobe.d/gxde-iwlwifi.conf"

            if [[ -f "$legacy_iwlwifi_config" && -f "$gxde_iwlwifi_config" ]]; then
                echo "Error: both legacy and GXDE-specific iwlwifi configuration files exist."
                exit 1
            elif [[ -f "$legacy_iwlwifi_config" ]]; then
                echo "Source compatibility: renaming the GXDE iwlwifi configuration to avoid distribution package conflicts."
                if ! mv "$legacy_iwlwifi_config" "$gxde_iwlwifi_config"; then
                    echo "Error: failed to rename the GXDE iwlwifi configuration."
                    exit 1
                fi
            elif [[ -f "$gxde_iwlwifi_config" ]]; then
                echo "Source compatibility: the GXDE iwlwifi configuration already has a distribution-safe name."
            fi
            ;;
        libdframeworkdbus-qt6)
            if grep -Fq \
                'find_package(Qt6CorePrivate REQUIRED)' \
                "$PROJ_ROOT/tools/qdbusxml2cpp/CMakeLists.txt" \
                && grep -Fq \
                'find_package(Qt6DBusPrivate REQUIRED)' \
                "$PROJ_ROOT/tools/qdbusxml2cpp/CMakeLists.txt"; then
                echo "Source compatibility: Qt6 D-Bus Framework tool already imports private Qt targets."
            else
                apply_bundled_source_patch \
                    "Qt6 D-Bus Framework private targets" \
                    "$PROJ_ROOT/patches/dframework-dbus-qt6-core-private.patch"
            fi
            ;;
        dde-qt6platform-plugins)
            local bundled_xcb_headers="$PROJ_ROOT/compat/qt6-xcb-private-headers/6.10.2"
            local source_xcb_headers="$PROJ_ROOT/xcb/libqt6xcbqpa-dev/6.10.2"

            if [[ -f "$source_xcb_headers/qxcbconnection.h" ]]; then
                echo "Source compatibility: Qt 6.10.2 XCB private headers are already available."
            elif [[ ! -f "$bundled_xcb_headers/qxcbconnection.h" ]]; then
                echo "Error: bundled Qt 6.10.2 XCB private headers were not found."
                exit 1
            else
                echo "Source compatibility: installing Qt 6.10.2 XCB private headers."
                mkdir -p "$(dirname "$source_xcb_headers")"
                if ! cp -a "$bundled_xcb_headers" "$source_xcb_headers"; then
                    echo "Error: failed to install Qt 6.10.2 XCB private headers."
                    exit 1
                fi
            fi
            ;;
        dtk2widget6)
            if grep -q \
                'QString::number(static_cast<int>(modifier))' \
                "$PROJ_ROOT/src/widgets/dsettingswidgetfactory.cpp" \
                && grep -q \
                'QString::number(static_cast<int>(key))' \
                "$PROJ_ROOT/src/widgets/dsettingswidgetfactory.cpp"; then
                echo "Source compatibility: DTK2 Widget Qt6 already formats shortcut enums explicitly."
            else
                apply_bundled_source_patch \
                    "DTK2 Widget Qt6 Qt 6.10 enum string formatting" \
                    "$PROJ_ROOT/patches/dtk2widget6-qt-6.10-enum-string-format.patch"
            fi
            if grep -q 'QT_VERSION_CHECK(6, 10, 0)' \
                "$PROJ_ROOT/src/widgets/dtabbar.cpp" \
                && grep -q 'if (index == d->pressedIndex)' \
                "$PROJ_ROOT/src/widgets/dtabbar.cpp"; then
                echo "Source compatibility: DTK2 Widget Qt6 already supports Qt 6.10 tab offsets."
            else
                apply_bundled_source_patch \
                    "DTK2 Widget Qt6 Qt 6.10 tab offsets" \
                    "$PROJ_ROOT/patches/dtk2widget6-qt-6.10-tab-offsets.patch"
            fi
            if tail -n 1 "$PROJ_ROOT/src/util/dregionmonitor.cpp" \
                | grep -Fxq '#include "moc_dregionmonitor.cpp"'; then
                echo "Source compatibility: DTK2 Widget Qt6 moc include is outside the DTK namespace."
            else
                apply_bundled_source_patch \
                    "DTK2 Widget Qt6 Qt 6.10 moc namespace" \
                    "$PROJ_ROOT/patches/dtk2widget6-qt-6.10-moc-namespace.patch"
            fi
            ;;
        gxde-qt6integration)
            if tail -n 1 "$PROJ_ROOT/dstyleplugin-qt6/style.cpp" \
                | grep -Fxq '#include "moc_style.cpp"'; then
                echo "Source compatibility: GXDE Qt6 Integration moc include is outside the style namespace."
            else
                apply_bundled_source_patch \
                    "GXDE Qt6 Integration Qt 6.10 moc namespace" \
                    "$PROJ_ROOT/patches/gxde-qt6integration-qt-6.10-moc-namespace.patch"
            fi
            ;;
        dtk6widget)
            if grep -q \
                'D_DECLARE_PRIVATE_MEMBER(QDragManager_m_platformDrag_tag' \
                "$PROJ_ROOT/src/widgets/dtabbar.cpp" \
                && grep -q 'QT_VERSION_CHECK(6, 10, 1)' \
                "$PROJ_ROOT/src/widgets/dtabbar.cpp"; then
                echo "Source compatibility: DTK6 Widget already supports Qt 6.10.2."
                return
            fi
            apply_bundled_source_patch \
                "DTK6 Widget Qt 6.10" \
                "$PROJ_ROOT/patches/dtk6widget-qt-6.10.patch"
            ;;
        qt6integration)
            if grep -q \
                'find_package(Qt6 COMPONENTS CorePrivate GuiPrivate WidgetsPrivate REQUIRED)' \
                "$PROJ_ROOT/CMakeLists.txt"; then
                echo "Source compatibility: Qt6 Integration already imports Qt 6.10 private targets."
            else
                apply_bundled_source_patch \
                    "Qt6 Integration Qt 6.10 private targets" \
                    "$PROJ_ROOT/patches/qt6integration-qt-6.10-private-targets.patch"
            fi

            if grep -q \
                'qgenericunixtheme_p.h' \
                "$PROJ_ROOT/platformthemeplugin/qdeepintheme.h"; then
                echo "Source compatibility: Qt6 Integration already supports the Qt 6.10 generic Unix theme header."
            else
                apply_bundled_source_patch \
                    "Qt6 Integration Qt 6.10 generic Unix theme header" \
                    "$PROJ_ROOT/patches/qt6integration-qt-6.10-generic-theme-header.patch"
            fi

            if grep -q \
                'private/qfactoryloader_p.h' \
                "$PROJ_ROOT/platformthemeplugin/qdeepintheme.cpp" \
                && grep -q \
                '^#include <unistd.h>' \
                "$PROJ_ROOT/platformthemeplugin/qdeepinfiledialoghelper.cpp"; then
                echo "Source compatibility: Qt6 Integration already has the required explicit includes."
            else
                apply_bundled_source_patch \
                    "Qt6 Integration explicit private API includes" \
                    "$PROJ_ROOT/patches/qt6integration-missing-private-includes.patch"
            fi

            if grep -q \
                'QHighDpi::fromNativeWindowGeometry' \
                "$PROJ_ROOT/platformthemeplugin/qdeepintheme.cpp"; then
                echo "Source compatibility: Qt6 Integration already supports the Qt 6.9.2 geometry event API."
            else
                apply_bundled_source_patch \
                    "Qt6 Integration Qt 6.9.2 geometry event API" \
                    "$PROJ_ROOT/patches/qt6integration-qt-6.9-geometry-change.patch"
            fi
            ;;
    esac
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

    # Older installer runs removed a dependency name from a continuation line
    # but left its indentation behind.  Resume reuses that modified checkout,
    # so repair these invalid whitespace-only continuation lines before the
    # dependency-presence check below.  Valid stanza separators are empty
    # lines and therefore are not affected.
    if grep -Eq '^[[:space:]]+$' "$PROJ_ROOT/debian/control"; then
        echo "APT compatibility: repairing invalid blank continuation lines in debian/control."
        sed -i -E '/^[[:space:]]+$/d' "$PROJ_ROOT/debian/control"
    fi

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
    if grep -Eq \
        "^[[:space:]]*${package}[[:space:]]*,?[[:space:]]*$" \
        "$PROJ_ROOT/debian/control"; then
        # In a multi-line Build-Depends field, leaving an indented blank line
        # terminates the field.  The next dependency is then parsed as an
        # orphan continuation line.  Remove the complete dependency line.
        sed -i -E \
            "/^[[:space:]]*${package}[[:space:]]*,?[[:space:]]*$/d" \
            "$PROJ_ROOT/debian/control"
    else
        # Also support compact Build-Depends fields containing several
        # dependencies on the same line.
        sed -i -E \
            "s/(^|[[:space:]])${package}([[:space:]]*,[[:space:]]*)?/\\1/" \
            "$PROJ_ROOT/debian/control"
    fi
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

# Keep legacy cgo bindings buildable with toolchains whose default language
# mode is C23.  Older GIR-generated sources use declarations such as
# "extern void callback();".  Those declarations mean unspecified arguments
# through C17, but mean no arguments in C23 and therefore conflict with the
# prototypes emitted by cgo.  CGO_CFLAGS is ignored by non-cgo builds, so this
# compatibility setting is safe at the common APT package-build entry point.
configure_cgo_compatibility() {
    if [[ " ${CGO_CFLAGS:-} " != *" -std=gnu17 "* ]]; then
        export CGO_CFLAGS="${CGO_CFLAGS:+${CGO_CFLAGS} }-std=gnu17"
    fi
    echo "CGO compatibility: using GNU C17 for legacy generated bindings."
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
    configure_cgo_compatibility
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
