![](./docs/img/readme-header.png)

# GXDE Desktop Environment Installer
## Introduction
> Currently, this software is still in early stage of developing.

This utility allows you to try GXDE as a desktop environment without the need of installing GXDE OS or GXDE LSG.

## Building

Install the system build tools on Ubuntu or Debian:

```bash
sudo apt update
sudo apt install gettext python3-venv file
```

`make` creates the local Python virtual environment and installs the remaining
build dependencies automatically:

```bash
make
```

## Running
```bash
./dist/gxde-desktop-environment-installer
```

If an installation stops with an error, continue from its last incomplete
module by selecting the same working directory:

```bash
./dist/gxde-desktop-environment-installer --resume
```

The installer saves progress after every successful build and installation.
It can also reconstruct progress for older working directories that do not
yet contain a resume-state file.
