#!/usr/bin/env python3
import base64, json, os, socket, subprocess, time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

WEB=Path('/opt/aion/web'); STATE=Path('/var/lib/aion'); STATE.mkdir(parents=True,exist_ok=True)
USER=os.getenv('AION_USER','admin'); PASS=os.getenv('AION_PASSWORD','aion-test')
app=FastAPI(title='AION Server OS',version='0.1-live')

def run(argv,timeout=45):
    try:
        p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
        return {'ok':p.returncode==0,'code':p.returncode,'stdout':p.stdout[-40000:],'stderr':p.stderr[-12000:]}
    except Exception as e: return {'ok':False,'code':500,'stdout':'','stderr':str(e)}

def auth(req:Request):
    h=req.headers.get('authorization','')
    if not h.startswith('Basic '): raise HTTPException(401,'authentication required',headers={'WWW-Authenticate':'Basic realm="AION"'})
    try: u,p=base64.b64decode(h[6:]).decode().split(':',1)
    except Exception: raise HTTPException(401,'bad credentials',headers={'WWW-Authenticate':'Basic realm="AION"'})
    if u!=USER or p!=PASS: raise HTTPException(401,'bad credentials',headers={'WWW-Authenticate':'Basic realm="AION"'})

def j(cmd):
    r=run(cmd)
    if not r['ok']: return []
    try:return json.loads(r['stdout'])
    except:return []

def inventory():
    resources=j(['pvesh','get','/cluster/resources','--type','vm','--output-format','json'])
    nodes=j(['pvesh','get','/nodes','--output-format','json'])
    storage=j(['pvesh','get','/storage','--output-format','json'])
    return {'resources':resources,'nodes':nodes,'storage':storage,'zfs':run(['zpool','status','-x']),'df':run(['df','-hPT'])}

@app.middleware('http')
async def guard(req:Request,call_next):
    try: auth(req)
    except HTTPException as e: return JSONResponse({'detail':e.detail},status_code=e.status_code,headers=e.headers)
    return await call_next(req)

@app.get('/api/system')
def system(req:Request):
    return {'name':'AION Server OS','edition':'Live Preview','version':'0.1','hostname':socket.gethostname(),'time':int(time.time()),'maintenance':'48h','autonomy':'enabled','pve':run(['pveversion'])}

@app.get('/api/inventory')
def inv(req:Request): return inventory()

@app.get('/api/health')
def health(req:Request):
    return {'failed':run(['systemctl','--failed','--no-legend','--plain']),'pve_cluster':run(['systemctl','is-active','pve-cluster']),'pvedaemon':run(['systemctl','is-active','pvedaemon']),'zfs':run(['zpool','status','-x'])}

@app.get('/api/maintenance')
def maintenance(req:Request):
    f=STATE/'last-maintenance.json'
    if not f.exists(): return {'status':'not-run-yet'}
    try:return json.loads(f.read_text())
    except:return {'status':'invalid-report'}

@app.post('/api/action/{kind}/{vmid}/{action}')
def action(kind:str,vmid:int,action:str,req:Request):
    if kind not in {'vm','ct'} or action not in {'start','shutdown','reboot'} or vmid<100: raise HTTPException(400,'invalid action')
    tool='qm' if kind=='vm' else 'pct'
    argv=[tool,action,str(vmid)]
    if action=='shutdown': argv += ['--timeout','60']
    r=run(argv,90)
    with (STATE/'actions.jsonl').open('a') as f:f.write(json.dumps({'ts':int(time.time()),'kind':kind,'id':vmid,'action':action,'result':r['ok']})+'\n')
    return r

app.mount('/assets',StaticFiles(directory=str(WEB)),name='assets')
@app.get('/')
def root(req:Request): return FileResponse(WEB/'index.html')
