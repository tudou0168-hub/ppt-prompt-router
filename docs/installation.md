# 安装说明

先准备标准 PPT Master 工作区，再安装 Router 和最小覆盖层。

```bash
python3 install.py detect
python3 install.py install --host codex --master-root <ppt_master_root>
python3 install.py validate --host codex --master-root <ppt_master_root>
python3 install.py uninstall --host codex --master-root <ppt_master_root> --yes
```

支持 `codex`、`claude-code` 和 `hermes`。可用 `--router-target` 指定技能父目录；可用 `--mode symlink` 供本地开发使用。

安装器只应用 `integrations/ppt-master/manifest.json` 声明的文件。上游 Hash 不匹配时会停止，不覆盖用户修改；安装失败时恢复 Router 和 PPT Master 备份。
