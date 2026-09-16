"""Headless-Chrome QA for a static site.
  python3 scripts/qa_page.py . qa_out [--widths 1440,1024,768,390] [--port 8765]
Copies the site to a temp dir, injects a probe into <head> (layout shifts, horizontal overflow,
broken images, video readiness/errors, console-visible JS errors), serves it over HTTP, then for
each width: full-page screenshot + probe JSON. The real site is never modified."""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time, html, socket
PROBE = r"""<script>(function(){
 window.__qa={cls:0,shifts:[],errors:[]};
 window.addEventListener('error',function(e){__qa.errors.push(String(e.message||e.type)+' @'+(e.filename||(e.target&&(e.target.src||e.target.currentSrc))||''))},true);
 try{new PerformanceObserver(function(l){l.getEntries().forEach(function(e){if(!e.hadRecentInput){__qa.cls+=e.value;
   __qa.shifts.push({v:+e.value.toFixed(4),t:Math.round(e.startTime),src:(e.sources||[]).map(function(s){var n=s.node;
   return n&&n.nodeType===1?(n.tagName+(n.id?'#'+n.id:'')+(n.className&&n.className.baseVal===undefined?'.'+String(n.className).split(' ').join('.'):'')):String(n&&n.nodeName)})})}})}).observe({type:'layout-shift',buffered:true})}catch(x){__qa.errors.push('no PerformanceObserver '+x)}
 window.addEventListener('load',function(){setTimeout(function(){
   var d=document.documentElement, over=[];
   document.querySelectorAll('body *').forEach(function(el){var r=el.getBoundingClientRect(); if(r.width>0&&(r.right>window.innerWidth+1)) over.push(el.tagName+(el.id?'#'+el.id:'')+'.'+String(el.className).split(' ').slice(0,2).join('.')+' right='+Math.round(r.right))});
   var rep={cls:+__qa.cls.toFixed(4),shifts:__qa.shifts.slice(0,40),errors:__qa.errors,
     innerWidth:window.innerWidth,scrollWidth:d.scrollWidth,overflowX:d.scrollWidth>window.innerWidth+1,
     overflowing:over.slice(0,25),
     images:[].slice.call(document.images).map(function(i){return {src:i.getAttribute('src'),ok:i.complete&&i.naturalWidth>0,nw:i.naturalWidth,rw:Math.round(i.getBoundingClientRect().width)}}),
     videos:[].slice.call(document.querySelectorAll('video')).map(function(v){var s=v.currentSrc||(v.querySelector('source')||{}).src||v.getAttribute('src');
       return {src:s,readyState:v.readyState,error:v.error?v.error.code:null,vw:v.videoWidth,vh:v.videoHeight,
       box:[Math.round(v.getBoundingClientRect().width),Math.round(v.getBoundingClientRect().height)]}}),
     pageHeight:d.scrollHeight};
   var p=document.createElement('pre');p.id='__qa_report';p.style.display='none';p.textContent=JSON.stringify(rep);document.body.appendChild(p);
   try{ if(window.parent!==window){var q=parent.document.createElement('pre');q.id='__qa_report';q.textContent=JSON.stringify(rep);parent.document.body.appendChild(q);} }catch(x){}
 },7000)});})();</script>"""
def free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("site"); ap.add_argument("out")
    ap.add_argument("--widths",default="1440,1024,768,390"); ap.add_argument("--page",default="index.html")
    a=ap.parse_args(); os.makedirs(a.out,exist_ok=True)
    tmp=tempfile.mkdtemp(prefix="qa_site_")
    shutil.copytree(a.site,tmp,dirs_exist_ok=True,ignore=shutil.ignore_patterns(".git","medias"))
    idx=os.path.join(tmp,a.page); s=open(idx,encoding="utf-8").read()
    s=re.sub(r"(<head[^>]*>)",lambda m:m.group(1)+PROBE,s,count=1)
    # QA copy only: full-page captures must not show images that were never decoded
    s=s.replace(' loading="lazy"','').replace(' decoding="async"','')
    open(idx,"w",encoding="utf-8").write(s)
    port=free_port(); srv=subprocess.Popen([sys.executable,"-m","http.server",str(port),"--bind","127.0.0.1"],cwd=tmp,
                                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1.0); url=f"http://127.0.0.1:{port}/{a.page}"; summary={}
    try:
        for w in [int(x) for x in a.widths.split(",")]:
            prof=tempfile.mkdtemp(prefix="qa_chrome_")
            base=["google-chrome","--headless=new","--no-sandbox","--disable-gpu","--hide-scrollbars",
                  "--mute-audio","--autoplay-policy=no-user-gesture-required",f"--user-data-dir={prof}"]
            # Headless Chrome will not lay a window out narrower than 500 px, so phone widths are
            # measured inside an iframe of exactly that width.
            framed = w < 500
            def frame_url(h):
                name=f"__qa_frame_{w}_{h}.html"
                open(os.path.join(tmp,name),"w").write(
                    f'<!DOCTYPE html><html><body style="margin:0;background:#fff">'
                    f'<iframe src="{a.page}" style="border:0;display:block;width:{w}px;height:{h}px"></iframe></body></html>')
                return f"http://127.0.0.1:{port}/{name}"
            win_w = max(w, 500)
            dom=subprocess.run(base+[f"--window-size={win_w},900","--virtual-time-budget=12000","--dump-dom",
                               frame_url(900) if framed else url],
                               capture_output=True,text=True,timeout=180).stdout
            m=re.search(r'<pre id="__qa_report"[^>]*>(.*?)</pre>',dom,re.S)
            rep=json.loads(html.unescape(m.group(1))) if m else {"error":"probe did not report"}
            H=min(max(int(rep.get("pageHeight",8000))+120,1200),32000)
            png=os.path.join(a.out,f"page_{w}.png")
            subprocess.run(base+[f"--window-size={win_w},{H}","--virtual-time-budget=9000",f"--screenshot={png}",
                           frame_url(H) if framed else url], capture_output=True,timeout=240)
            if framed and os.path.exists(png):
                from PIL import Image
                im=Image.open(png); im.crop((0,0,w,im.size[1])).save(png)
            rep["screenshot"]=png; summary[w]=rep; shutil.rmtree(prof,ignore_errors=True)
            bad_v=[v for v in rep.get("videos",[]) if v.get("error") or not v.get("vw")]
            bad_i=[i for i in rep.get("images",[]) if not i.get("ok")]
            print(f"width {w}: height {rep.get('pageHeight')}  CLS {rep.get('cls')}  overflowX {rep.get('overflowX')}"
                  f"  videos {len(rep.get('videos',[]))} (unplayable {len(bad_v)})  images {len(rep.get('images',[]))}"
                  f" (broken {len(bad_i)})  js-errors {len(rep.get('errors',[]))}")
    finally:
        srv.terminate(); shutil.rmtree(tmp,ignore_errors=True)
    json.dump(summary,open(os.path.join(a.out,"qa_report.json"),"w"),indent=1)
if __name__=="__main__": main()
