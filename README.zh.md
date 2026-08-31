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

如果安装因错误而停止，可使用以下选项并选择上次的同一工作目录，从最后一个未完成的
模块继续：

```bash
./dist/gxde-desktop-environment-installer --resume
```

安装器会在每次构建和安装成功后保存进度。对于尚无续跑状态文件的旧工作目录，也会根
据已有的仓库目录重建进度。
