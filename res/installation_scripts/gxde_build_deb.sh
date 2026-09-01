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
BUILD_ARCH_INDEPENDENT=false
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
    echo "  -a, --architecture-independent"
    echo "                        Build Architecture: all packages only"
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
                BUILD_ARCH_INDEPENDENT=false
                shift
                ;;
            -a|--architecture-independent)
                BUILD_BIN=false
                BUILD_ARCH_INDEPENDENT=true
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
    local uploaders_line
    local uploaders
    local candidate_values
    local candidate
    local normalized_candidate
    local existing_candidate
    local maintainer_pattern='^.+[[:space:]]<[^<>[:space:]]+@[^<>[:space:]]+>$'
    local -a raw_candidates=()
    local -a valid_candidates=()
    local primary
    local additional=""
    local has_uploaders=false
    local duplicate
    local temporary_file

    if [[ ! -f "$control_file" ]]; then
        return
    fi
    maintainer_line="$(grep -m1 '^Maintainer:' "$control_file")"
    if [[ -z "$maintainer_line" ]]; then
        return
    fi
    maintainers="${maintainer_line#Maintainer:}"
    normalized_candidate="$(printf '%s\n' "$maintainers" \
        | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]*</ </g')"
    if [[ "$maintainers" != *,* \
        && "$normalized_candidate" =~ $maintainer_pattern ]]; then
        return
    fi

    uploaders_line="$(grep -m1 '^Uploaders:' "$control_file")"
    uploaders="${uploaders_line#Uploaders:}"
    if [[ -n "$uploaders_line" ]]; then
        has_uploaders=true
        candidate_values="$maintainers,$uploaders"
    else
        candidate_values="$maintainers"
    fi

    IFS=',' read -r -a raw_candidates <<< "$candidate_values"
    for candidate in "${raw_candidates[@]}"; do
        normalized_candidate="$(printf '%s\n' "$candidate" \
            | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]*</ </g')"
        if [[ ! "$normalized_candidate" =~ $maintainer_pattern ]]; then
            continue
        fi

        duplicate=false
        for existing_candidate in "${valid_candidates[@]}"; do
            if [[ "$existing_candidate" == "$normalized_candidate" ]]; then
                duplicate=true
                break
            fi
        done
        if [[ "$duplicate" == false ]]; then
            valid_candidates+=("$normalized_candidate")
        fi
    done

    if [[ ${#valid_candidates[@]} -eq 0 ]]; then
        echo "Error: Debian Maintainer metadata contains no valid email address."
        return 1
    fi

    primary="${valid_candidates[0]}"
    for candidate in "${valid_candidates[@]:1}"; do
        if [[ -n "$additional" ]]; then
            additional+=", "
        fi
        additional+="$candidate"
    done

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
            if (has_uploaders != "true" && additional != "") {
              print "Uploaders: " additional
            }
            next
          }
          /^Uploaders:/ && has_uploaders == "true" {
            if (additional != "") {
              print "Uploaders: " additional
            }
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

# Normalize blank lines without losing Debian control paragraph boundaries.
# Older installer versions deleted every whitespace-only line while repairing
# a removed Build-Depends entry. Some repositories use such a line between
# binary package paragraphs, so that behavior could merge two Package fields.
repair_debian_control_layout() {
    local control_file="$PROJ_ROOT/debian/control"
    local temporary_file

    if [[ ! -f "$control_file" ]]; then
        return
    fi

    temporary_file="$(mktemp "$PROJ_ROOT/debian/control.XXXXXX")" || {
        echo "Error: failed to create a temporary Debian control file."
        return 1
    }
    if ! awk '
        { lines[NR] = $0 }
        END {
            in_build_depends = 0
            paragraph_has_fields = 0

            for (line_number = 1; line_number <= NR; line_number++) {
                line = lines[line_number]

                if (line ~ /^[[:space:]]*$/) {
                    next_line = line_number + 1
                    while (next_line <= NR \
                           && lines[next_line] ~ /^[[:space:]]*$/) {
                        next_line++
                    }

                    # A blank line between two Build-Depends continuation
                    # entries is damage left by an older dependency removal.
                    if (in_build_depends \
                        && next_line <= NR \
                        && lines[next_line] ~ /^[[:space:]]+[^[:space:]]/) {
                        continue
                    }

                    print ""
                    in_build_depends = 0
                    paragraph_has_fields = 0
                    continue
                }

                # Package must begin a binary paragraph. Reinsert a separator
                # when an older run merged it into the preceding paragraph.
                if (line ~ /^Package:[[:space:]]*/ && paragraph_has_fields) {
                    print ""
                    in_build_depends = 0
                    paragraph_has_fields = 0
                }

                print line

                if (line ~ /^Build-Depends(-Arch|-Indep)?:/) {
                    in_build_depends = 1
                } else if (in_build_depends \
                           && line !~ /^[[:space:]]/) {
                    in_build_depends = 0
                }

                if (line !~ /^[[:space:]]/) {
                    paragraph_has_fields = 1
                }
            }
        }
    ' "$control_file" > "$temporary_file"; then
        rm -f "$temporary_file"
        echo "Error: failed to normalize the Debian control layout."
        return 1
    fi

    if cmp -s "$temporary_file" "$control_file"; then
        rm -f "$temporary_file"
        return
    fi

    echo "Debian control compatibility: repairing blank lines and package paragraph boundaries."
    if ! mv "$temporary_file" "$control_file"; then
        rm -f "$temporary_file"
        echo "Error: failed to install the normalized Debian control file."
        return 1
    fi
}

# Core session packages are built and installed before the user chooses an X11
# or Wayland compositor.  Their historical Debian metadata requires a window
# manager immediately, which either blocks bootstrap or makes APT pick an
# unrelated distribution compositor.  The installer guarantees that the
# chosen session stack is installed later, so remove only the exact standalone
# dependency line from the cloned package metadata.
defer_session_runtime_dependency() {
    local dependency_expression="$1"
    local control_file="$PROJ_ROOT/debian/control"
    local escaped_expression

    escaped_expression="$(printf '%s\n' "$dependency_expression" \
        | sed -E 's/[][(){}.^$*+?|\\]/\\&/g')"
    if ! grep -Eq \
        "^[[:space:]]*${escaped_expression},?[[:space:]]*$" \
        "$control_file"; then
        return
    fi

    echo "Source compatibility: deferring session compositor dependency until session selection."
    sed -i -E \
        "/^[[:space:]]*${escaped_expression},?[[:space:]]*$/d" \
        "$control_file"
}

# Apply source-level compatibility fixes bundled with the installer. Patches
# are scoped to their source package and skipped once the fixed code is
# present, so updated repositories are not rewritten.
apply_source_compatibility() {
    if ! repair_debian_control_layout; then
        exit 1
    fi
    if ! normalize_debian_maintainer_metadata; then
        exit 1
    fi

    case "$PKG_NAME" in
        deepin-daemon)
            defer_session_runtime_dependency \
                'deepin-wm | deepin-metacity | dde-kwin | gxde-wlcom'
            ;;
        startgxde)
            defer_session_runtime_dependency \
                'gxde-wm-shim | deepin-metacity | gxde-kwin-neo | gxde-wlcom'
            ;;
        gxde-shell-compressor)
            local compressor_changelog="$PROJ_ROOT/debian/changelog"

            # The repository's changelog has an empty address (shenmo <>),
            # which modern dpkg rejects.  Shenmo's commits in this repository
            # consistently use jifengshenmo@outlook.com.
            if grep -Eq \
                '^[[:space:]]*--[[:space:]]+shenmo[[:space:]]+<[[:space:]]*>' \
                "$compressor_changelog"; then
                echo "Source compatibility: restoring GXDE Shell Compressor's changelog email from its Git history."
                if ! sed -i -E \
                    's/^([[:space:]]*--[[:space:]]+shenmo[[:space:]]+)<[[:space:]]*>/\1<jifengshenmo@outlook.com>/' \
                    "$compressor_changelog"; then
                    echo "Error: failed to repair GXDE Shell Compressor's changelog email."
                    exit 1
                fi
            fi

            if grep -Eq \
                '^[[:space:]]*--[[:space:]]+shenmo[[:space:]]+<[[:space:]]*>' \
                "$compressor_changelog"; then
                echo "Error: GXDE Shell Compressor's changelog still contains an empty maintainer email."
                exit 1
            fi
            ;;
        dpa-ext-gnomekeyring)
            # The current GXDE repository contains no qmake/CMake/Meson build
            # definition or Debian install manifest.  It therefore produces a
            # metadata-only compatibility package, matching the package in the
            # GXDE repository.  Its old Qt, GNOME Keyring and PolicyKit agent
            # development Build-Depends are therefore unused; the agent one
            # also creates a cycle because the agent runtime depends on this
            # package.  Keep only debhelper while the source remains
            # metadata-only, allowing this package to be built and installed
            # before the agent even on distributions that retired the legacy
            # development libraries.
            if [[ ! -f "$PROJ_ROOT/CMakeLists.txt" \
                && ! -f "$PROJ_ROOT/meson.build" \
                && ! -f "$PROJ_ROOT/Makefile" ]] \
                && ! find "$PROJ_ROOT" -maxdepth 1 -type f \
                    \( -name '*.pro' -o -name '*.install' \) \
                    -print -quit | grep -q . \
                && ! grep -Fxq 'Build-Depends: debhelper (>= 9)' \
                    "$PROJ_ROOT/debian/control"; then
                echo "Source compatibility: removing obsolete source-build dependencies from the metadata-only keyring extension."
                sed -i -E \
                    's/^Build-Depends:.*/Build-Depends: debhelper (>= 9)/' \
                    "$PROJ_ROOT/debian/control"
            fi
            ;;
        libdbusmenu-qt6)
            local dbusmenu_control="$PROJ_ROOT/debian/control"

            # GXDE's package is built with Qt 6, but its development binary
            # package still carries the upstream Qt 5 dependency name.  Keep
            # the generated development package on the same Qt ABI as the
            # library and its exported CMake target.
            if grep -Eq '^[[:space:]]*qtbase5-dev([[:space:]]|,|\(|$)' \
                "$dbusmenu_control"; then
                echo "Source compatibility: correcting the DBusMenu Qt6 development dependency."
                sed -i -E \
                    's/^([[:space:]]*)qtbase5-dev([[:space:]]*,?)/\1qt6-base-dev\2/' \
                    "$dbusmenu_control"
            else
                echo "Source compatibility: DBusMenu development dependencies already use Qt 6."
            fi

            if grep -Eq '^[[:space:]]*qtbase5-dev([[:space:]]|,|\(|$)' \
                "$dbusmenu_control" \
                || ! grep -Eq '^[[:space:]]*qt6-base-dev([[:space:]]|,|\(|$)' \
                    "$dbusmenu_control"; then
                echo "Error: failed to correct the DBusMenu Qt6 development dependency."
                exit 1
            fi
            ;;
        libgnome-keyring)
            # GNOME's source uses Autotools, while this repository still has
            # a 2014 CDBS Debian wrapper. gnome-pkg-tools 0.22.13 retired its
            # CDBS makefiles but retains the supported dh_gnome sequence.
            # Use standard debhelper around the release's generated configure
            # files and keep GNOME packaging integration through `--with
            # gnome`; no library source or binary package layout is changed.
            local modern_rules="$PROJ_ROOT/compat/libgnome-keyring/debian-rules"

            if [[ ! -f "$modern_rules" ]]; then
                echo "Error: bundled modern libgnome-keyring Debian rules were not found."
                exit 1
            elif cmp -s "$modern_rules" "$PROJ_ROOT/debian/rules"; then
                echo "Source compatibility: modern GNOME debhelper rules are already configured."
            else
                echo "Source compatibility: replacing retired GNOME CDBS rules with debhelper."
                if ! install -m 0755 "$modern_rules" \
                    "$PROJ_ROOT/debian/rules"; then
                    echo "Error: failed to install modern libgnome-keyring Debian rules."
                    exit 1
                fi
            fi

            local control_file
            for control_file in \
                "$PROJ_ROOT/debian/control" \
                "$PROJ_ROOT/debian/control.in"; do
                if [[ ! -f "$control_file" ]]; then
                    continue
                fi
                sed -i -E \
                    '/^[[:space:]]*cdbs([[:space:]]*\([^)]*\))?,?[[:space:]]*$/d; /^[[:space:]]*dh-autoreconf,?[[:space:]]*$/d' \
                    "$control_file"
            done
            if grep -Eq '^[[:space:]]*(cdbs|dh-autoreconf)([[:space:](,]|$)' \
                "$PROJ_ROOT/debian/control"; then
                echo "Error: failed to remove retired libgnome-keyring CDBS build dependencies."
                exit 1
            fi

            # gtk-doc 1.26 removed gtkdoc-mktmpl. This release already ships
            # its generated tmpl/*.sgml files, so keep building and packaging
            # the reference manual from those templates instead of attempting
            # to regenerate them with a command that no longer exists.
            local gtkdoc_makefile
            for gtkdoc_makefile in \
                "$PROJ_ROOT/gtk-doc.make" \
                "$PROJ_ROOT/docs/reference/gnome-keyring/Makefile.in" \
                "$PROJ_ROOT/docs/reference/gnome-keyring/Makefile"; do
                if [[ ! -f "$gtkdoc_makefile" ]]; then
                    continue
                fi
                sed -i \
                    's|gtkdoc-mktmpl --module=$(DOC_MODULE) $(MKTMPL_OPTIONS)|echo "Using the shipped gtk-doc templates"|g' \
                    "$gtkdoc_makefile"
            done
            if grep -Fq 'gtkdoc-mktmpl --module=$(DOC_MODULE)' \
                "$PROJ_ROOT/docs/reference/gnome-keyring/Makefile.in"; then
                echo "Error: failed to disable the retired gtkdoc-mktmpl step."
                exit 1
            fi
            ;;
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
        gxde-globalmenu-service)
            local global_menu_control="$PROJ_ROOT/debian/control"
            local unused_global_menu_dependency
            local global_menu_unused_dependencies=(
                libdtkwidget-dev
                libdtkcore-dev
                libdtkcore5-bin
                libdframeworkdbus-dev
                libgsettings-qt-dev
            )

            # The service only links Qt5, KF5 and XCB.  Its Debian metadata
            # still lists DTK and other Deepin framework development packages
            # that are not referenced by the build, and an unversioned
            # libdtkwidget-dev resolves to the distribution's DTK5 package on
            # Ubuntu instead of GXDE's already-installed compatibility stack.
            # Stop if a future source revision genuinely starts using DTK.
            if grep -Eqi \
                'find_package\([^)]*dtk|pkg_check_modules\([^)]*dtk|Dtk::|DTK::' \
                "$PROJ_ROOT/CMakeLists.txt"; then
                echo "Source compatibility: GXDE Global Menu Service now uses DTK; preserving its declared build dependencies."
                return
            fi

            if grep -Eq \
                '^[[:space:]]*(libdtkwidget-dev|libdtkcore-dev|libdtkcore5-bin|libdframeworkdbus-dev|libgsettings-qt-dev)([[:space:]]|,|\(|$)' \
                "$global_menu_control"; then
                echo "Source compatibility: removing unused DTK and Deepin framework build dependencies from GXDE Global Menu Service."
                for unused_global_menu_dependency in \
                    "${global_menu_unused_dependencies[@]}"; do
                    sed -i -E \
                        "/^[[:space:]]*${unused_global_menu_dependency}([[:space:]]*\([^)]*\))?,?[[:space:]]*$/d" \
                        "$global_menu_control"
                done
            else
                echo "Source compatibility: GXDE Global Menu Service build dependencies already match its source."
            fi

            if grep -Eq \
                '^[[:space:]]*(libdtkwidget-dev|libdtkcore-dev|libdtkcore5-bin|libdframeworkdbus-dev|libgsettings-qt-dev)([[:space:]]|,|\(|$)' \
                "$global_menu_control"; then
                echo "Error: failed to remove unused GXDE Global Menu Service build dependencies."
                exit 1
            fi
            ;;
        gxde-top-panel-plugins)
            local panel_control="$PROJ_ROOT/debian/control"
            local panel_root_cmake="$PROJ_ROOT/CMakeLists.txt"
            local panel_tray_cmake="$PROJ_ROOT/plugins/tray/CMakeLists.txt"
            local panel_tray_source="$PROJ_ROOT/plugins/tray/snitraywidget.cpp"

            # Older installer revisions copied GXDE Dock's embedded DBusMenu
            # tree into this checkout.  Remove only the CMake glue inserted by
            # that compatibility path so --resume can migrate the same source
            # tree to GXDE's independently packaged Qt 6 implementation.
            if grep -Fq 'add_subdirectory("cmake/libdbusmenu")' \
                "$panel_root_cmake"; then
                echo "Source compatibility: removing the retired bundled DBusMenu integration."
                sed -i \
                    '/^# Build the Qt 6 dbusmenu implementation bundled with GXDE Dock\./,/^add_subdirectory("cmake\/libdbusmenu")$/d' \
                    "$panel_root_cmake"
            fi
            if grep -Fq '"${CMAKE_SOURCE_DIR}/lib/3rdparty/libdbusmenu/src"' \
                "$panel_tray_cmake"; then
                sed -i \
                    '/^target_include_directories(${PLUGIN_NAME} PRIVATE$/,/^)$/d' \
                    "$panel_tray_cmake"
            fi

            if grep -Fq 'dbusmenu-lxqt' "$panel_tray_cmake" \
                || grep -Fq '<dbusmenu-lxqt/dbusmenuimporter.h>' \
                    "$panel_tray_source" \
                || grep -Fq '<dbusmenu-qt6/dbusmenuimporter.h>' \
                    "$panel_tray_source" \
                || grep -Eq \
                    '^[[:space:]]*libdbusmenu-lxqt-dev([[:space:]]|,|\(|$)' \
                    "$panel_control"; then
                echo "Source compatibility: switching GXDE Top Panel Plugins to GXDE's DBusMenu Qt6 package."
                sed -i 's/dbusmenu-lxqt/dbusmenu-qt6/g' \
                    "$panel_tray_cmake" \
                    "$panel_control"
                sed -i -E \
                    's#<dbusmenu-(lxqt|qt6)/dbusmenuimporter\.h>#<dbusmenuimporter.h>#g' \
                    "$panel_tray_source"
            else
                echo "Source compatibility: GXDE Top Panel Plugins already uses DBusMenu Qt6."
            fi

            if grep -Fq 'add_subdirectory("cmake/libdbusmenu")' \
                "$panel_root_cmake" \
                || grep -Fq 'lib/3rdparty/libdbusmenu/src' \
                    "$panel_tray_cmake" \
                || grep -Fq 'dbusmenu-lxqt' "$panel_tray_cmake" \
                || ! grep -Fq 'find_package(dbusmenu-qt6 CONFIG REQUIRED)' \
                    "$panel_tray_cmake" \
                || ! grep -Fq '<dbusmenuimporter.h>' \
                    "$panel_tray_source" \
                || ! grep -Eq \
                    '^[[:space:]]*libdbusmenu-qt6-dev([[:space:]]|,|\(|$)' \
                    "$panel_control"; then
                echo "Error: GXDE Top Panel Plugins' DBusMenu Qt6 configuration is incomplete."
                exit 1
            fi
            ;;
        gxde-movie-reborn)
            local movie_qt6_cmake
            local movie_qt6_cmake_files=(
                "$PROJ_ROOT/src/CMakeLists.txt"
                "$PROJ_ROOT/src/libgxmr-qt6/CMakeLists.txt"
            )

            # Both the Qt 6 player and libgxmr-qt6 already link GuiPrivate,
            # but the repository only discovers Qt6::Gui.  On current CMake,
            # private Qt targets are separate packages and therefore must be
            # imported explicitly before target_link_libraries is evaluated.
            for movie_qt6_cmake in "${movie_qt6_cmake_files[@]}"; do
                if [[ ! -f "$movie_qt6_cmake" ]]; then
                    echo "Error: GXDE Movie Qt 6 CMake file was not found: $movie_qt6_cmake"
                    exit 1
                fi
                if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                    "$movie_qt6_cmake"; then
                    echo "Source compatibility: importing the Qt GUI private target in $movie_qt6_cmake."
                    if ! sed -i \
                        '/^[[:space:]]*pkg_check_modules(DTK2W[[:space:]]/i\
if(NOT TARGET Qt6::GuiPrivate)\
    find_package(Qt6GuiPrivate REQUIRED)\
endif()\
' \
                        "$movie_qt6_cmake"; then
                        echo "Error: failed to import the Qt GUI private target in $movie_qt6_cmake."
                        exit 1
                    fi
                fi

                if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                    "$movie_qt6_cmake" \
                    || ! grep -Fq 'Qt6::GuiPrivate' "$movie_qt6_cmake"; then
                    echo "Error: GXDE Movie's Qt GUI private target configuration is incomplete in $movie_qt6_cmake."
                    exit 1
                fi
            done
            ;;
        gxde-file-manager)
            local file_manager_controller="$PROJ_ROOT/gxde-file-manager-lib/controllers/filecontroller.cpp"

            # Qt 6.10 no longer provides the static startDetached overload
            # taking a QProcessEnvironment as its fourth argument.  Use an
            # instance so the compressor still receives the deliberately
            # sanitized X11/Wayland environment before it is detached.
            if grep -Fq \
                'setProcessEnvironment(compressorEnvironment())' \
                "$file_manager_controller"; then
                echo "Source compatibility: GXDE File Manager already uses the supported detached-process environment API."
            else
                apply_bundled_source_patch \
                    "GXDE File Manager Qt 6.10 detached-process environment" \
                    "$PROJ_ROOT/patches/gxde-file-manager-qt-6.10-qprocess-environment.patch"
            fi
            ;;
        gxde-wlcom)
            local wlroots_libinput_switch="$PROJ_ROOT/subprojects/wlroots/backend/libinput/switch.c"

            # New libinput releases added switch kinds that this bundled
            # wlroots version cannot represent.  Ignore unknown kinds instead
            # of leaving wlr_event.switch_type uninitialized; the default also
            # keeps -Werror=switch builds working across libinput versions.
            if grep -A3 -F \
                'case LIBINPUT_SWITCH_TABLET_MODE:' \
                "$wlroots_libinput_switch" \
                | grep -Fq 'default:'; then
                echo "Source compatibility: bundled wlroots already ignores unsupported libinput switch kinds."
            else
                apply_bundled_source_patch \
                    "GXDE Wlcom new libinput switch kinds" \
                    "$PROJ_ROOT/patches/gxde-wlcom-libinput-keypad-switch.patch"
            fi
            ;;
        gxde-launcher)
            local launcher_cmake="$PROJ_ROOT/CMakeLists.txt"

            # GXDE Launcher includes qguiapplication_p.h directly.  Its
            # Qt6Gui_PRIVATE_INCLUDE_DIRS reference remains empty until CMake
            # imports GuiPrivate, and linking the target propagates the
            # versioned private include directories to the executable.
            if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                "$launcher_cmake"; then
                echo "Source compatibility: importing the Qt GUI private target for GXDE Launcher."
                if ! sed -i \
                    '/^[[:space:]]*find_package(Qt6Widgets REQUIRED)[[:space:]]*$/a\
if(NOT TARGET Qt6::GuiPrivate)\
    find_package(Qt6GuiPrivate REQUIRED)\
endif()' \
                    "$launcher_cmake"; then
                    echo "Error: failed to import the Qt GUI private target for GXDE Launcher."
                    exit 1
                fi
            fi

            if ! grep -Eq '^[[:space:]]*Qt6::GuiPrivate[[:space:]]*$' \
                "$launcher_cmake"; then
                echo "Source compatibility: linking GXDE Launcher to the Qt GUI private target."
                if ! sed -i \
                    '/^[[:space:]]*${Qt6Widgets_LIBRARIES}[[:space:]]*$/a\
    Qt6::GuiPrivate' \
                    "$launcher_cmake"; then
                    echo "Error: failed to link GXDE Launcher to the Qt GUI private target."
                    exit 1
                fi
            fi

            if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                "$launcher_cmake" \
                || ! grep -Eq '^[[:space:]]*Qt6::GuiPrivate[[:space:]]*$' \
                    "$launcher_cmake"; then
                echo "Error: GXDE Launcher's Qt GUI private target configuration is incomplete."
                exit 1
            fi
            ;;
        gxde-control-center)
            local control_center_frame_cmake="$PROJ_ROOT/src/frame/CMakeLists.txt"

            # The frame accesses QPA types directly.  Merely listing
            # qt6-base-private-dev in Debian Build-Depends does not propagate
            # Qt's versioned private include directories to this executable;
            # importing and linking GuiPrivate does.
            if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                "$control_center_frame_cmake"; then
                echo "Source compatibility: importing the Qt GUI private target for GXDE Control Center."
                if ! sed -i \
                    '/^[[:space:]]*find_package(Qt6 REQUIRED COMPONENTS/a\
if(NOT TARGET Qt6::GuiPrivate)\
    find_package(Qt6GuiPrivate REQUIRED)\
endif()' \
                    "$control_center_frame_cmake"; then
                    echo "Error: failed to import the Qt GUI private target for GXDE Control Center."
                    exit 1
                fi
            fi

            if ! grep -Eq '^[[:space:]]*Qt6::GuiPrivate[[:space:]]*$' \
                "$control_center_frame_cmake"; then
                echo "Source compatibility: linking GXDE Control Center to the Qt GUI private target."
                if ! sed -i \
                    '/^[[:space:]]*Qt6::Widgets[[:space:]]*$/a\
    Qt6::GuiPrivate' \
                    "$control_center_frame_cmake"; then
                    echo "Error: failed to link GXDE Control Center to the Qt GUI private target."
                    exit 1
                fi
            fi

            if ! grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                "$control_center_frame_cmake" \
                || ! grep -Eq '^[[:space:]]*Qt6::GuiPrivate[[:space:]]*$' \
                    "$control_center_frame_cmake"; then
                echo "Error: GXDE Control Center's Qt GUI private target configuration is incomplete."
                exit 1
            fi
            ;;
        gxde-dock)
            local system_monitor_cmake="$PROJ_ROOT/plugins/dde-sys-monitor-plugin/CMakeLists.txt"
            local dock_frame_cmake="$PROJ_ROOT/frame/CMakeLists.txt"
            local dock_tray_cmake="$PROJ_ROOT/plugins/tray/CMakeLists.txt"

            if sed -n '/find_package(PkgConfig REQUIRED)/,+1p' \
                "$system_monitor_cmake" \
                | grep -Fq 'pkg_check_modules(dtk2widget REQUIRED dtk2widget)'; then
                echo "Source compatibility: GXDE Dock loads PkgConfig before checking DTK2 Widget."
            else
                apply_bundled_source_patch \
                    "GXDE Dock CMake PkgConfig scope" \
                    "$PROJ_ROOT/patches/gxde-dock-cmake-pkg-config-scope.patch"
            fi

            local qt_gui_private_cmake
            for qt_gui_private_cmake in "$dock_frame_cmake" "$dock_tray_cmake"; do
                if grep -Fq 'find_package(Qt6GuiPrivate REQUIRED)' \
                    "$qt_gui_private_cmake"; then
                    continue
                fi

                if ! grep -Eq \
                    '^[[:space:]]*find_package\(Qt6[[:space:]].*COMPONENTS' \
                    "$qt_gui_private_cmake"; then
                    echo "Error: cannot find the Qt 6 component declaration in $qt_gui_private_cmake."
                    exit 1
                fi

                if ! sed -i \
                    '/^[[:space:]]*find_package(Qt6[[:space:]].*COMPONENTS/a\
if(NOT TARGET Qt6::GuiPrivate)\
    find_package(Qt6GuiPrivate REQUIRED)\
endif()' \
                    "$qt_gui_private_cmake"; then
                    echo "Error: failed to import the Qt GUI private target in $qt_gui_private_cmake."
                    exit 1
                fi
            done
            echo "Source compatibility: GXDE Dock explicitly imports the Qt GUI private target."
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

    if ! repair_debian_control_layout; then
        exit 1
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
    if [[ "$BUILD_ARCH_INDEPENDENT" == true ]]; then
        dpkg_args+=("-A")
    elif [[ "$BUILD_BIN" == true ]]; then
        dpkg_args+=("-b")
    fi

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
