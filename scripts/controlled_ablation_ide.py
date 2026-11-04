"""IDE-owned coordinator supervisor; worker remains independently user-owned."""
import os
import sys
import threading
import time
import psutil
from research_watchdog import main
from resume_frozen_e3 import owner_is_alive, prevent_idle_sleep


def watch_owner():
    pid=int(os.environ['MINIFLS_IDE_OWNER_PID'])
    birth=int(os.environ['MINIFLS_IDE_OWNER_STARTED_MS'])
    def monitor():
        while owner_is_alive(pid,birth):time.sleep(.5)
        owned=psutil.Process().children(recursive=True)
        for process in reversed(owned):
            try:process.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(owned,timeout=5)
        for process in alive:
            try:process.kill()
            except psutil.NoSuchProcess:pass
        os._exit(130)
    threading.Thread(target=monitor,daemon=True).start()


if __name__=='__main__':
    try:
        watch_owner()
        with prevent_idle_sleep():sys.exit(main())
    except KeyboardInterrupt:sys.exit(130)
    except Exception as error:
        print('BLOCKED: '+str(error),file=sys.stderr,flush=True)
        sys.exit(20)
