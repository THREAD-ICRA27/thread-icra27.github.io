"""Measure layout shift under real mobile device emulation (no iframe):
   python3 scripts/qa_layout_shift.py . <width> [runs]   (needs the `websockets` package)"""
import asyncio, json, os, socket, subprocess, sys, tempfile, time, urllib.request, shutil
import websockets
OBS = """window.__cls=0;window.__sh=[];new PerformanceObserver(function(l){l.getEntries().forEach(function(e){if(!e.hadRecentInput){window.__cls+=e.value;window.__sh.push([+e.value.toFixed(4),Math.round(e.startTime),(e.sources||[]).map(function(s){var n=s.node;return n&&n.nodeType===1?(n.tagName+'.'+String(n.className).split(' ')[0]):String(n&&n.nodeName)})])}})}).observe({type:'layout-shift',buffered:true});"""
def port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p
async def run(url, W, prof):
    dp=port()
    chrome=subprocess.Popen(["google-chrome","--headless=new","--no-sandbox","--disable-gpu","--mute-audio",
        "--autoplay-policy=no-user-gesture-required",f"--remote-debugging-port={dp}",f"--user-data-dir={prof}","about:blank"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs=json.load(urllib.request.urlopen(f"http://127.0.0.1:{dp}/json")); break
            except Exception: time.sleep(0.25)
        ws_url=[t for t in tabs if t["type"]=="page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=2**24) as ws:
            mid=[0]
            async def call(m, **p):
                mid[0]+=1; i=mid[0]; await ws.send(json.dumps({"id":i,"method":m,"params":p}))
                while True:
                    r=json.loads(await ws.recv())
                    if r.get("id")==i: return r.get("result",{})
            phone = W < 769
            await call("Emulation.setDeviceMetricsOverride", width=W, height=900 if not phone else 800,
                       deviceScaleFactor=2 if phone else 1, mobile=phone)
            await call("Emulation.setTouchEmulationEnabled", enabled=phone)
            await call("Page.enable")
            await call("Page.addScriptToEvaluateOnNewDocument", source=OBS)
            await call("Page.navigate", url=url)
            await asyncio.sleep(6)
            async def ev(x):
                r=await call("Runtime.evaluate", expression=x, returnByValue=True); return r["result"].get("value")
            load_cls=await ev("window.__cls")
            H=await ev("document.documentElement.scrollHeight")
            y=0
            while y < H:
                await ev(f"window.scrollTo(0,{y})"); await asyncio.sleep(0.25); y+=600
            await asyncio.sleep(2)
            total=await ev("window.__cls"); sh=await ev("JSON.stringify(window.__sh.slice(0,8))")
            iw=await ev("window.innerWidth"); sw=await ev("document.documentElement.scrollWidth")
            return load_cls, total, sh, iw, sw
    finally:
        chrome.terminate()
def main():
    site, W = sys.argv[1], int(sys.argv[2]); runs=int(sys.argv[3]) if len(sys.argv)>3 else 3
    hp=port(); srv=subprocess.Popen([sys.executable,"-m","http.server",str(hp),"--bind","127.0.0.1"],cwd=site,
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        for k in range(runs):
            prof=tempfile.mkdtemp(prefix="cdpcls_")
            lc,tc,sh,iw,sw=asyncio.run(run(f"http://127.0.0.1:{hp}/index.html", W, prof))
            print(f"width {W} run {k+1}: innerWidth {iw} scrollWidth {sw}  CLS at load {lc:.4f}  CLS after scrolling whole page {tc:.4f}  shifts {sh}")
            shutil.rmtree(prof, ignore_errors=True)
    finally:
        srv.terminate()
if __name__=="__main__": main()
