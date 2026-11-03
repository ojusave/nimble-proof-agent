"""Run both isolated processes; forward shutdown and fail when either child exits."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    if not (os.environ.get('PROOF_PUBLIC_URL') or os.environ.get('RENDER_EXTERNAL_URL')):
        sys.exit('Set PROOF_PUBLIC_URL to the external HTTPS origin.')
    root=Path(__file__).resolve().parent.parent
    children=[]
    stopping=False
    def shutdown(*_):
        nonlocal stopping
        stopping=True
        for child in children:
            if child.poll() is None: child.terminate()
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try:
        children.append(subprocess.Popen([sys.executable,'app.py','serve','--port','8767'],cwd=root))
        children.append(subprocess.Popen(['node','server.js'],cwd=root/'frontend',env={
            **os.environ,'HOSTNAME':'0.0.0.0','PORT':os.environ.get('PORT','10000'),
            'PROOF_BACKEND_URL':'http://127.0.0.1:8767'}))
        while not stopping and all(child.poll() is None for child in children): time.sleep(.2)
        code=0 if stopping else 1
    finally:
        shutdown()
        deadline=time.monotonic()+20
        for child in children:
            try: child.wait(timeout=max(.1,deadline-time.monotonic()))
            except subprocess.TimeoutExpired: child.kill();child.wait()
    return code


if __name__=='__main__':sys.exit(main())
