"""Start the local broker, backend and simulator; Ctrl+C stops owned children."""
import argparse
import socket
import subprocess
import sys
import time
import urllib.request
import json
from common.config import ROOT, load_config
from simulator.scenarios import SCENARIOS

def main():
    p=argparse.ArgumentParser();p.add_argument('--scenario',choices=SCENARIOS,default='combined_event')
    args=p.parse_args();cfg=load_config()
    if cfg['mqtt']['host'] not in ('127.0.0.1','localhost') or cfg['mqtt']['username']:
        p.error('Demo broker requires localhost without credentials. Use separate terminals for Mosquitto.')
    endpoints = (
        ('MQTT', '127.0.0.1', cfg['mqtt']['port']),
        ('HTTP', cfg['web']['host'], cfg['web']['port']),
    )
    if endpoints[0][2] == endpoints[1][2]:
        p.error('The MQTT and HTTP ports must be different.')
    for service, host, port in endpoints:
        with socket.socket() as probe:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError as exc:
                p.error(f'{service} cannot bind {host}:{port}. Check port availability and network settings ({exc}).')
    local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    logs=ROOT/'logs';logs.mkdir(exist_ok=True);children=[];handles=[]
    def start(name,*command):
        handle=(logs/(name+'.log')).open('w',encoding='utf-8');handles.append(handle)
        child=subprocess.Popen([sys.executable,'-u','-m',*command],cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        children.append(child)
    try:
        start('broker','tools.demo_broker','--port',str(cfg['mqtt']['port']))
        time.sleep(.5)
        if children[0].poll() is not None:raise RuntimeError('Broker could not start; see logs/broker.log (port already occupied?).')
        start('backend','backend.app')
        url=f"http://{cfg['web']['host']}:{cfg['web']['port']}"
        deadline=time.monotonic()+12
        while True:
            if any(c.poll() is not None for c in children):raise RuntimeError('A service exited; inspect logs/.')
            try:
                with local_http.open(url+'/api/health',timeout=1) as r:ready=json.load(r)['mqtt_connected']
                if ready:break
            except OSError:pass
            if time.monotonic()>deadline:raise RuntimeError('Backend/MQTT startup timed out; inspect logs/ and local firewall/port settings.')
            time.sleep(.2)
        start('simulator','simulator.device_simulator','--scenario',args.scenario)
        print(f'Open {url}\nScenario: {args.scenario}. Logs: {logs}\nCtrl+C stops all three services.',flush=True)
        while True:
            if any(c.poll() is not None for c in children):raise RuntimeError('A service exited; inspect logs/.')
            time.sleep(.5)
    except KeyboardInterrupt:print('\nStopping demo.')
    finally:
        for child in reversed(children):
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        for handle in handles:handle.close()

if __name__=='__main__':main()
