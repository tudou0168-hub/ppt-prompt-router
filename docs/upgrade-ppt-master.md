# 升级 PPT Master

覆盖层只适配 `upstream.lock` 中记录的 PPT Master 基线。升级上游前，先在干净副本中验证 Router 2.1 的合同、Director Plan、生产控制和导出门禁。

使用唯一维护脚本重新生成覆盖层：

```bash
python3 scripts/sync_master_overlay.py \
  --upstream-root <clean_master> \
  --modified-root <modified_master> \
  --output integrations/ppt-master
```

脚本只处理 Router 2.1 白名单文件，并拒绝客户信息、个人路径和二进制文件。生成后必须运行全部测试和临时安装验证。
