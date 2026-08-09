#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,platform,shutil,tempfile,sys
from pathlib import Path
from installers import get_adapter, host_choices
from installers.base import HostError
PACKAGE_NAME='ppt-prompt-router'; PKG_VERSION='3.1.3'
REQUIRED_FILES=('SKILL.md','README.md','VERSION','prompt-index.json','install.py')
REQUIRED_DIRS=('prompts','scripts','references','lenses','installers')
class PackageError(RuntimeError): pass
def expand(x): return Path(os.path.expandvars(os.path.expanduser(x))).resolve(strict=False)
def root(): return Path(__file__).resolve().parent
def dest(target): return target/PACKAGE_NAME
def validate(r:Path):
 if not r.is_dir(): raise PackageError(f'not found: {r}')
 for f in REQUIRED_FILES:
  if not (r/f).is_file(): raise PackageError(f'missing {f}')
 for d in REQUIRED_DIRS:
  if not (r/d).is_dir(): raise PackageError(f'missing {d}/')
 if (r/'VERSION').read_text().strip()!=PKG_VERSION: raise PackageError('VERSION mismatch')
 idx=json.loads((r/'prompt-index.json').read_text());
 if len(idx.get('prompts',[]))!=26: raise PackageError('expected 26 prompts')
 for e in idx['prompts']:
  if not (r/e['file']).is_file(): raise PackageError(f"missing {e['file']}")
 for f in ('route.py','scoring.py','semantics.py','template_intent.py'):
  if not (r/'scripts'/f).is_file(): raise PackageError(f'missing scripts/{f}')
 return True
def install(target:Path,force=False):
 d=dest(target); src=root()
 if d.exists() and not force: raise PackageError(f'exists: {d}')
 target.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix='.ppt-router-',dir=str(target.parent))); stage=tmp/PACKAGE_NAME
 try:
  shutil.copytree(src,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.git'))
  validate(stage)
  if d.exists(): shutil.rmtree(d)
  shutil.move(stage,d); return d
 finally: shutil.rmtree(tmp,ignore_errors=True)
def main(argv=None):
 p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
 q=s.add_parser('detect'); q.add_argument('--host',choices=host_choices(),default='auto'); q.add_argument('--skills-dir')
 q=s.add_parser('install'); q.add_argument('--target'); q.add_argument('--host',choices=host_choices(),default='auto'); q.add_argument('--skills-dir'); q.add_argument('--force',action='store_true')
 q=s.add_parser('validate'); q.add_argument('--target',required=True)
 a=p.parse_args(argv)
 try:
  if a.cmd=='detect':
   ad=get_adapter(a.host,skills_dir=expand(a.skills_dir) if a.skills_dir else None); print(json.dumps({'host':ad.host_id,'detected':ad.detect(),'skills_dirs':[str(x) for x in ad.discover_skills_dirs()],'platform':platform.system().lower()},ensure_ascii=False,indent=2)); return 0
  if a.cmd=='install':
   if a.target: target=expand(a.target)
   else:
    ad=get_adapter(a.host,skills_dir=expand(a.skills_dir) if a.skills_dir else None); dirs=ad.discover_skills_dirs();
    if not dirs: raise PackageError('no skills directory detected; pass --target')
    target=dirs[0]
   print(f'installed: {install(target,a.force)}'); return 0
  validate(dest(expand(a.target))); print(f'validated: {dest(expand(a.target))}'); return 0
 except (PackageError,HostError) as e: print(f'error: {e}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
