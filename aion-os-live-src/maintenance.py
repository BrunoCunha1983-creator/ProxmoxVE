#!/usr/bin/env python3
import json, subprocess, time
from pathlib import Path
STATE=Path('/var/lib/aion'); STATE.mkdir(parents=True,exist_ok=True)
def run(a,t=60):
 try:
  p=subprocess.run(a,text=True,capture_output=True,timeout=t);return {'ok':p.returncode==0,'out':p.stdout[-25000:],'err':p.stderr[-8000:]}
 except Exception as e:return {'ok':False,'err':str(e)}
report={'ts':int(time.time()),'checks':{}}
checks={'pveversion':['pveversion','-v'],'failed':['systemctl','--failed','--no-legend','--plain'],'journal':['journalctl','-p','0..3','--since','48 hours ago','--no-pager','-n','1000'],'zfs':['zpool','status','-x'],'disk':['df','-hPT'],'smart':['smartctl','--scan-open']}
for k,c in checks.items(): report['checks'][k]=run(c)
report['repairs']=[]
for svc in ['pve-cluster','pvedaemon','pvestatd']:
 s=run(['systemctl','is-active',svc])
 if not s['ok']:
  r=run(['systemctl','restart',svc]); report['repairs'].append({'service':svc,'restart':r['ok']})
report['status']='attention' if any(not x.get('ok',False) for x in report['checks'].values()) else 'ok'
(STATE/'last-maintenance.json').write_text(json.dumps(report,indent=2))
