"""Kiểm thử HTTP Java ↔ Python, gồm loại update mô phỏng và phục hồi sau restart."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
import socket
import subprocess
import sys
import time
import uuid

from minifls.data import prepare
from minifls.experiment import request, run

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def wait_health(base, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Service exited before healthy; inspect e2e logs")
        try:
            request(base,"/health")
            return
        except Exception:
            time.sleep(.25)
    raise RuntimeError("Service startup timed out")


def verify():
    token=uuid.uuid4().hex[:10]
    folder=ROOT / "artifacts" / "e2e" / token
    folder.mkdir(parents=True)
    manifest=folder / "dataset"
    prepare(manifest,dataset="synthetic",clients=100,samples=7000)
    worker_port,server_port=free_port(),free_port()
    worker_base,base=f"http://127.0.0.1:{worker_port}",f"http://127.0.0.1:{server_port}"
    env={**os.environ,"MINIFLS_WORKSPACE":str(ROOT),"MINIFLS_WORKER_URL":worker_base,
         "MINIFLS_SERVER_PORT":str(server_port),"MINIFLS_DATABASE":str(folder / "experiments.db"),
         "MINIFLS_METHOD":"none"}
    flags={"creationflags":subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {}
    log=(folder / "services.log").open("w",encoding="utf-8")
    def start_worker():
        p=subprocess.Popen([sys.executable,"-m","uvicorn","minifls.api:app","--port",str(worker_port)],
                           cwd=ROOT,env=env,stdout=log,stderr=log,**flags)
        wait_health(worker_base,p)
        return p
    worker=start_worker()
    server=None
    try:
        jar=ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar"
        server=subprocess.Popen(["java","-Xmx384m","-jar",str(jar)],cwd=ROOT,env=env,stdout=log,stderr=log,**flags)
        wait_health(base,server)
        config=json.loads((ROOT / "configurations/smoke.json").read_text())
        config.update(manifestPath=manifest.relative_to(ROOT).as_posix(),experimentId=f"e2e-{token}")
        state,rounds=run(config,base,str(folder))
        assert len(rounds)==20 and len(state["snapshot"]["clients"])==100
        assert any(r["acceptedIds"] for r in rounds)
        for r in rounds:
            assert len(r["selectedIds"])==5
            assert r["modelVersion"]<=r["roundId"]
            for p in r["participants"]:
                assert p["accepted"]==(p["status"]=="COMPLETED")
                assert p["training"]["baseModelVersion"]==r["modelVersion"]-(r["outcome"]=="COMMITTED")
        # Mọi update đều đã train thật, nhưng dropout phải khiến chúng bị loại khỏi aggregation.
        dropped={**config,"experimentId":f"dropout-{token}","rounds":2,"dropout":1.0}
        dropped_state,dropped_rounds=run(dropped,base,str(folder))
        assert dropped_state["snapshot"]["modelVersion"]==0
        assert all(r["outcome"]=="SKIPPED" and not r["weights"] for r in dropped_rounds)
        timed={**config,"experimentId":f"timeout-{token}","rounds":2,"deadlineSeconds":1e-9,"dropout":0.0,"requiredRamMb":1.0}
        _,timed_rounds=run(timed,base,str(folder))
        assert all(not r["acceptedIds"] for r in timed_rounds)
        lbw={**config,"experimentId":f"lbw-{token}","rounds":3,"selection":"resource_aware","aggregation":"fedlbw","dropout":0.0}
        _,lbw_rounds=run(lbw,base,str(folder))
        assert all(len(r["proxyLosses"])==len(r["weights"])==5 for r in lbw_rounds)
        assert all(abs(sum(r["weights"])-1)<1e-8 for r in lbw_rounds)
        # Ngắt worker sau một round đã commit rồi tiếp tục từ checkpoint đã lưu.
        retry={**config,"experimentId":f"resume-{token}","rounds":20,"simulationEnabled":False}
        request(base,"/experiments",retry)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            progress=json.loads(request(base,f"/experiments/{retry['experimentId']}"))
            if (progress["snapshot"] or {}).get("round",0)>=1:
                break
            time.sleep(.03)
        else:
            raise RuntimeError("No committed round before interruption")
        worker.terminate();worker.wait(timeout=15)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            failed=json.loads(request(base,f"/experiments/{retry['experimentId']}"))
            if failed["status"]=="FAILED":
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Experiment did not fail after worker interruption")
        worker=start_worker()
        # Restart cả Java để bảo đảm resume dựa vào SQLite, không dựa vào object cũ trong bộ nhớ.
        server.terminate();server.wait(timeout=15)
        server=subprocess.Popen(["java","-Xmx384m","-jar",str(jar)],cwd=ROOT,env=env,stdout=log,stderr=log,**flags)
        wait_health(base,server)
        recovered,recovered_rounds=run(retry,base,str(folder),resume=True)
        assert [r["roundId"] for r in recovered_rounds]==list(range(1,21))
        assert recovered["snapshot"]["modelVersion"]==20
        # Gọi từ ApplicationRunner bằng môi trường, không POST /experiments qua CLI.
        server.terminate();server.wait(timeout=15)
        launch_id=f"application-{token}"
        launch_env={**env,"MINIFLS_METHOD":"fedlbw","MINIFLS_CONFIG":"configurations/smoke.json",
                    "MINIFLS_EXPERIMENT_ID":launch_id,"MINIFLS_MANIFEST":config["manifestPath"],
                    "MINIFLS_SELECTION":"random","MINIFLS_ROUNDS":"2","MINIFLS_SEED":"42"}
        server=subprocess.Popen(["java","-Xmx384m","-jar",str(jar)],cwd=ROOT,env=launch_env,stdout=log,stderr=log,**flags)
        wait_health(base,server)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                launched=json.loads(request(base,f"/experiments/{launch_id}"))
            except HTTPError as exc:
                # HTTP can listen just before ApplicationRunner submits the run.
                if exc.code!=404:
                    raise
                time.sleep(.1)
                continue
            if launched["status"]!="RUNNING":
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Application-launched experiment did not finish")
        assert launched["status"]=="COMPLETED",launched.get("error")
        assert launched["config"]["aggregation"]=="fedlbw"
        assert len(json.loads(request(base,f"/experiments/{launch_id}/rounds")))==2
        print(f"PASS: 20-round HTTP pipeline, dropout/OOM/timeout exclusion, FedLBW, persisted resume, Application launch. Evidence: {folder}")
    finally:
        for p in [server,worker]:
            if p is not None and p.poll() is None:
                p.terminate();p.wait(timeout=15)
        log.close()


if __name__=="__main__":
    verify()
