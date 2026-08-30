# GXDE桌面环境安装器
## 简介
> 当前此程序正在开发的早期阶段！！

本程序可以让您在其他发行版上安装GXDE桌面环境而无需安装GXDE OS或GXDE子系统。

## 构建

在 Ubuntu 或 Debian 上先安装系统构建工具：

```bash
sudo apt update
sudo apt install gettext python3-venv file
```

`make` 会自动创建本地 Python 虚拟环境，并安装其余构建依赖：

```bash
make
```

## 运行
```bash
./dist/gxde-desktop-environment-installer
```
