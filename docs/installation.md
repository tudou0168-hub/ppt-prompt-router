# 安装说明

先准备标准 PPT Master 工作区，再安装 Router 和最小覆盖层。

```bash
python3 install.py detect
python3 install.py install --host claude-code
python3 install.py validate --host claude-code
python3 install.py uninstall --host claude-code --yes
```

支持 `codex`、`claude-code` 和 `hermes`。默认从 `upstream.lock` 对应的 codeload ZIP 获取指定 PPT Master，不使用 Git clone。也可选用本地只读来源：

```bash
python3 install.py install --host claude-code --master-source-dir <ppt_master_root>
python3 install.py install --host claude-code --master-source-zip <template_path>/ppt-master.zip
```

可用 `--router-target` 指定技能父目录；可用 `--mode symlink` 供本地开发使用。

安装器只应用 `integrations/ppt-master/manifest.json` 声明的文件。上游 Hash 不匹配时会停止，不覆盖用户修改；安装失败时恢复 Router 和 PPT Master 备份。最终安装位置是宿主正式 skills 目录中的 `ppt-master`，不会修改 Claude plugin cache 或 marketplace。
