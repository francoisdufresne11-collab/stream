import os,sys,time,uuid,shutil,secrets,threading,datetime
from pathlib import Path
from flask import Flask,request,jsonify,send_from_directory,Response,redirect,url_for,session
from flask_socketio import SocketIO,emit,join_room,leave_room

app=Flask(__name__,static_folder='static',static_url_path='/static')
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH']=500*1024*1024
app.config['ADMIN_PASSWORD']=os.environ.get('ADMIN_PASSWORD','admin2026')
socketio=SocketIO(app,cors_allowed_origins='*',async_mode='threading',
    ping_timeout=60,ping_interval=20,max_http_buffer_size=10_000_000,
    logger=False,engineio_logger=False)
BASE_DIR=Path(__file__).resolve().parent
STREAMS_DIR=BASE_DIR/'streams'
STREAMS_DIR.mkdir(exist_ok=True)
active_streams={};stream_viewers={};chat_history={}
server_stats={'total_streams':0,'total_messages':0,'started':time.time()}
_lock=threading.Lock()
QUALITIES={'1080p':{'res':'1920x1080','vb':'5000k','ab':'192k'},
           '720p': {'res':'1280x720', 'vb':'2500k','ab':'128k'},
           '480p': {'res':'854x480',  'vb':'1200k','ab':'96k'},
           '360p': {'res':'640x360',  'vb':'600k', 'ab':'64k'}}

def _up():
    s=int(time.time()-server_stats['started']);h,r=divmod(s,3600);m,s=divmod(r,60)
    return '%02d:%02d:%02d'%(h,m,s)
def _master(sid):
    sdir=STREAMS_DIR/sid
    bw={'1080p':5200000,'720p':2600000,'480p':1300000,'360p':650000}
    rs={'1080p':'1920x1080','720p':'1280x720','480p':'854x480','360p':'640x360'}
    out=['#EXTM3U']
    for q in QUALITIES:
        if (sdir/(q+'.m3u8')).exists():
            out.append('#EXT-X-STREAM-INF:BANDWIDTH='+str(bw[q])+',RESOLUTION='+rs[q]+',NAME='+q)
            out.append(q+'.m3u8')
    if len(out)>1:(sdir/'master.m3u8').write_text('\n'.join(out)+'\n',encoding='utf-8')
def _cleanup(sid):
    with _lock:
        sdir=STREAMS_DIR/sid
        if sdir.exists():shutil.rmtree(sdir,ignore_errors=True)
        active_streams.pop(sid,None);stream_viewers.pop(sid,None);chat_history.pop(sid,None)
def _ts(v):
    try:return datetime.datetime.fromtimestamp(float(v)).strftime('%H:%M:%S')
    except:return '?'

_CSS='''*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--b1:#0f0f23;--b2:#1a1a2e;--b3:#16213e;--bi:#0a0a1a;--ac:#a78bfa;--a2:#7c3aed;--gn:#10b981;--rd:#ef4444;--bl:#3b82f6;--tx:#e0e0e0;--mu:#888;--bo:#2a2a4a;--ch:#111127}
html,body{height:100%;margin:0;padding:0}
body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--b1);color:var(--tx);min-height:100vh}
a{color:var(--ac);text-decoration:none}a:hover{color:#c4b5fd}
code{background:var(--bi);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:.9em;color:var(--gn)}
.nb{display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:var(--b2);border-bottom:2px solid var(--bo);position:sticky;top:0;z-index:200;height:54px}
.logo{font-size:1.3em;font-weight:800;color:var(--ac)!important;text-decoration:none}
.nl{display:flex;gap:20px}.nl a{color:var(--mu);font-weight:500;font-size:.9em;text-decoration:none}.nl a:hover{color:var(--ac)}
.mc{max-width:1700px;margin:0 auto;padding:20px}
.home h1{margin-bottom:24px;font-size:1.8em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.eh{grid-column:1/-1;text-align:center;padding:80px 20px;color:var(--mu)}.eh p{font-size:1.2em;margin-bottom:20px}
.card{background:var(--b3);border-radius:12px;overflow:hidden;border:1px solid var(--bo);display:block;color:var(--tx);transition:transform .2s,box-shadow .2s;text-decoration:none}
.card:hover{transform:translateY(-4px);box-shadow:0 8px 30px rgba(167,139,250,.15)}
.thumb{height:180px;background:linear-gradient(135deg,#1e1e3f,#2d1b69);display:flex;align-items:flex-start;justify-content:flex-end;padding:10px;position:relative}
.tov{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;opacity:0;transition:.2s;background:rgba(0,0,0,.3)}.card:hover .tov{opacity:1}
.pi{font-size:2em;color:#fff}
.ci{padding:14px}.ci h3{margin-bottom:6px;font-size:1.05em}
.lb{background:var(--rd);color:#fff;padding:3px 8px;border-radius:5px;font-size:.78em;font-weight:700;animation:pl 2s infinite}
@keyframes pl{0%,100%{opacity:1}50%{opacity:.6}}
.wr{display:flex;height:calc(100vh - 54px);overflow:hidden}
.pc{flex:1;display:flex;flex-direction:column;min-width:0;background:#000}
.pw{flex:1;position:relative;background:#000;display:flex;flex-direction:column;overflow:hidden;min-height:0}
.pw video{width:100%;height:100%;object-fit:contain;display:block;background:#000;flex:1;min-height:0}
.pw.fa{position:fixed!important;inset:0!important;z-index:9999!important;width:100vw!important;height:100vh!important;background:#000!important}
.pw.fa video{width:100%!important;height:100%!important;object-fit:contain!important}
.pw:-webkit-full-screen{background:#000;width:100vw;height:100vh}
.pw:fullscreen{background:#000}
body.fs .nb,body.fs .pm,body.fs .cc{display:none!important}
.ov{position:absolute;inset:0;z-index:10;background:rgba(0,0,0,.9);display:flex;align-items:center;justify-content:center;transition:opacity .4s}
.oi{text-align:center;padding:20px}
.sp{width:52px;height:52px;border:4px solid var(--bo);border-top-color:var(--ac);border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 16px}
@keyframes sp{to{transform:rotate(360deg)}}
.ov p{color:var(--mu);font-size:1em;margin-bottom:4px}
.ub{position:absolute;bottom:80px;left:50%;transform:translateX(-50%);z-index:20;display:none;align-items:center;justify-content:center}
.ub button{background:rgba(167,139,250,.92);color:#fff;border:none;border-radius:50px;padding:12px 28px;font-size:1em;font-weight:700;cursor:pointer;animation:pl 2s infinite}
.ub button:hover{background:var(--ac)}
.cb2{position:absolute;bottom:0;left:0;right:0;z-index:30;background:linear-gradient(transparent,rgba(0,0,0,.95) 45%);padding:40px 14px 12px;transition:opacity .3s,transform .3s}
.cb2.ch{opacity:0;transform:translateY(100%);pointer-events:none}
.pr{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.pg{flex:1;height:4px;background:rgba(255,255,255,.2);border-radius:2px;position:relative;cursor:pointer;transition:height .15s}.pg:hover{height:7px}
.pf{position:absolute;inset:0;background:rgba(255,255,255,.3);border-radius:2px;width:0}
.pp{position:absolute;inset:0;background:var(--ac);border-radius:2px;width:0}
.pt{position:absolute;top:50%;transform:translate(-50%,-50%);width:12px;height:12px;border-radius:50%;background:#fff;left:0;opacity:0;transition:opacity .2s;pointer-events:none}.pg:hover .pt{opacity:1}
.lp{background:var(--rd);color:#fff;font-size:.7em;font-weight:700;padding:2px 7px;border-radius:4px;white-space:nowrap;animation:pl 2s infinite}
.lat{color:var(--gn);font-size:.7em;font-family:monospace;padding:2px 6px;background:rgba(16,185,129,.15);border-radius:4px}
.cr{display:flex;align-items:center;justify-content:space-between;gap:6px}
.cl,.crt{display:flex;align-items:center;gap:5px}
.btn2{background:none;border:none;cursor:pointer;width:36px;height:36px;display:flex;align-items:center;justify-content:center;color:#fff;border-radius:6px;transition:background .2s;padding:4px;flex-shrink:0}
.btn2:hover{background:rgba(255,255,255,.15)}.btn2 svg{width:20px;height:20px;fill:currentColor}
.bfs svg{width:22px;height:22px}
.vw{width:80px;display:flex;align-items:center}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:4px;background:rgba(255,255,255,.3);border-radius:2px;outline:none;cursor:pointer}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--ac);cursor:pointer}
input[type=range]::-moz-range-thumb{width:14px;height:14px;border-radius:50%;background:var(--ac);border:none;cursor:pointer}
.ct{color:rgba(255,255,255,.7);font-size:.82em;white-space:nowrap;font-family:monospace}
.cs{background:rgba(0,0,0,.7);color:#fff;border:1px solid rgba(255,255,255,.2);border-radius:6px;padding:4px 7px;font-size:.8em;cursor:pointer;outline:none}.cs:hover{border-color:var(--ac)}
.pm{display:flex;align-items:center;justify-content:space-between;padding:9px 16px;background:var(--b2);border-top:1px solid var(--bo);flex-shrink:0}
.pml{display:flex;align-items:center;gap:10px}.pml h2{font-size:1em}
.ls{font-size:.7em;padding:2px 7px;background:var(--rd);border-radius:4px;color:#fff;font-weight:700;animation:pl 2s infinite;white-space:nowrap}
.pr2{color:var(--mu);font-size:.88em}
.cc{width:360px;min-width:320px;display:flex;flex-direction:column;background:var(--ch);border-left:1px solid var(--bo)}
.ch2{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;background:var(--b2);border-bottom:1px solid var(--bo);flex-shrink:0}.ch2 h3{font-size:.95em}
.nr{display:flex;align-items:center;gap:6px;font-size:.85em}
.sw{position:relative;display:inline-block;width:34px;height:18px}.sw input{opacity:0;width:0;height:0}
.sl{position:absolute;inset:0;cursor:pointer;background:var(--bo);border-radius:18px;transition:.3s}
.sl::before{content:"";position:absolute;height:12px;width:12px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
input:checked+.sl{background:var(--gn)}input:checked+.sl::before{transform:translateX(16px)}
.cm2{flex:1;overflow-y:auto;padding:8px 12px;display:flex;flex-direction:column;gap:2px;scrollbar-width:thin;scrollbar-color:var(--bo) transparent}
.msg{padding:4px 7px;border-radius:6px;font-size:.85em;line-height:1.4;word-break:break-word}.msg:hover{background:rgba(255,255,255,.03)}
.mn{animation:fi .3s ease}@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.mt{color:var(--mu);font-size:.73em;margin-right:4px}.mu{color:var(--ac);font-weight:700;margin-right:4px}.mx{color:var(--tx)}
.sy{text-align:center;color:var(--mu);font-size:.76em;padding:3px;font-style:italic}
.ia{padding:9px 12px;border-top:1px solid var(--bo);background:var(--b2);flex-shrink:0}
#un{width:100%;padding:6px 10px;margin-bottom:6px;background:var(--bi);color:var(--ac);border:1px solid var(--bo);border-radius:6px;font-size:.84em;font-weight:600}
.mr{display:flex;gap:5px}
#mi{flex:1;padding:8px 11px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:.88em}
#mi:focus,#un:focus{outline:none;border-color:var(--ac)}
#sb{width:42px;background:var(--a2);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:1.1em;transition:.2s}#sb:hover{background:var(--ac)}
.btn{display:inline-block;padding:10px 24px;border-radius:8px;font-weight:700;font-size:.95em;border:none;cursor:pointer;transition:.2s;text-decoration:none}
.bp{background:var(--a2);color:#fff}.bp:hover{background:var(--ac)}
.bd{background:var(--rd);color:#fff;padding:8px 18px;border-radius:6px;font-size:.9em;font-weight:700;border:none;cursor:pointer;transition:.2s;text-decoration:none;display:inline-block}.bd:hover{background:#dc2626;color:#fff}
.bsm{padding:4px 10px;border-radius:5px;font-size:.8em;font-weight:700;border:none;cursor:pointer;text-decoration:none;display:inline-block;transition:.2s}
.bb{background:var(--bl);color:#fff}.bb:hover{background:#2563eb;color:#fff}
.br{background:var(--rd);color:#fff}.br:hover{background:#dc2626}
.bc h1{margin-bottom:24px}.bc-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.ic{background:var(--b3);border:1px solid var(--bo);border-radius:12px;padding:24px}.ic h3{margin-bottom:12px;color:var(--ac)}
.ub2{background:var(--bi);border:1px solid var(--ac);color:var(--ac);padding:12px 16px;border-radius:8px;font-family:monospace;font-size:.9em;word-break:break-all;text-align:center}
.how{padding-left:18px;margin-top:6px}.how li{padding:4px 0;color:var(--mu);font-size:.9em}
.asi{display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid var(--bo)}
.lg{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.li{background:var(--bi);border:1px solid var(--bo);border-radius:8px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;font-size:.88em}.li b{color:var(--ac)}
.aw{max-width:1200px;margin:0 auto}.at{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}.at h1{font-size:1.6em}
.sc{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:16px;margin-bottom:28px}
.sv{background:var(--b3);border:1px solid var(--bo);border-radius:12px;padding:20px;text-align:center;transition:.2s}.sv:hover{border-color:var(--ac)}
.si{font-size:.85em;color:var(--mu);margin-bottom:8px;font-weight:600;text-transform:uppercase}
.sv2{font-size:2em;font-weight:900;color:var(--ac);line-height:1}.sm{font-family:monospace;font-size:1.3em}.sl2{color:var(--mu);font-size:.85em;margin-top:4px}
.as{background:var(--b3);border:1px solid var(--bo);border-radius:12px;padding:24px;margin-bottom:20px}.as h2{margin-bottom:16px;font-size:1.1em;color:var(--ac)}
.at2{width:100%;border-collapse:collapse;font-size:.9em}.at2 th{text-align:left;padding:10px 12px;border-bottom:1px solid var(--bo);color:var(--mu);font-size:.82em;text-transform:uppercase}
.at2 td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04)}.at2 tr:hover td{background:rgba(255,255,255,.02)}
.em{text-align:center;color:var(--mu);padding:32px}
.cg{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.cfg{display:flex;align-items:center;gap:10px;padding:10px;background:var(--bi);border-radius:8px;border:1px solid var(--bo)}.ck{color:var(--mu);font-size:.85em;min-width:105px}
.ar{text-align:center;color:var(--mu);font-size:.8em;margin-top:16px}
.lw{display:flex;align-items:center;justify-content:center;min-height:60vh}
.lc{background:var(--b3);border:1px solid var(--bo);border-radius:16px;padding:40px;width:100%;max-width:380px}.lc h2{margin-bottom:24px;text-align:center;color:var(--ac)}
.fg{margin-bottom:16px}.fg label{display:block;margin-bottom:6px;color:var(--mu);font-size:.9em}
.fi{width:100%;padding:10px 14px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:1em}.fi:focus{outline:none;border-color:var(--ac)}
.fb{margin-bottom:16px}.fm{background:rgba(167,139,250,.15);border:1px solid var(--ac);border-radius:8px;padding:10px 16px;color:var(--ac);font-size:.9em;margin-bottom:6px}
@media(max-width:900px){.wr{flex-direction:column;height:auto}.cc{width:100%;min-width:0;height:350px}.bc-grid{grid-template-columns:1fr}.vw{width:60px}}
@media(max-width:560px){.ct{display:none}.cc{height:300px}.sc{grid-template-columns:repeat(2,1fr)}}'''
_SIO='https://cdn.socket.io/4.7.5/socket.io.min.js'
_HLS='https://cdn.jsdelivr.net/npm/hls.js@1.5.13'

def _page(title,body,js='',head=''):
    return ('<!DOCTYPE html><html lang="fr"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>'+title+'</title>'
        '<style>'+_CSS+'</style>'
        '<script src="'+_SIO+'"></script>'
        '<script src="'+_HLS+'"></script>'
        +head+
        '</head><body>'
        '<nav class="nb" id="_nb">'
        '<a href="/" class="logo">&#128225; StreamCaster</a>'
        '<div class="nl">'
        '<a href="/">Accueil</a>'
        '<a href="/broadcast">Diffuser</a>'
        '<a href="/admin">Admin</a>'
        '</div></nav>'
        '<main class="mc">'+body+'</main>'
        +js+
        '</body></html>')

@app.errorhandler(404)
def e404(e):return _page('404','<div style="text-align:center;padding:80px"><h1 style="font-size:5em;color:#a78bfa">404</h1><p style="color:#888">Page introuvable</p><a href="/" class="btn bp">Retour</a></div>'),404
@app.errorhandler(500)
def e500(e):return _page('500','<div style="text-align:center;padding:80px"><h1 style="font-size:5em;color:#ef4444">500</h1><p style="color:#888">Erreur interne</p><a href="/" class="btn bp">Retour</a></div>'),500

@app.route('/')
def index():
    cards=''
    for s in active_streams.values():
        i2=s['id']
        cards+='<a href="/watch/'+i2+'" class="card" data-id="'+i2+'">'
        cards+='<div class="thumb"><span class="lb">LIVE</span><div class="tov"><span class="pi">&#9654;</span></div></div>'
        cards+='<div class="ci"><h3>'+s['title']+'</h3><span id="v-'+i2+'">'+str(s['viewers'])+' viewers</span></div></a>'
    es=' style="display:none"' if active_streams else ''
    b=('<div class="home"><h1>&#127916; Streams en direct</h1>'
       '<div id="gr" class="grid">'
       '<div id="em" class="eh"'+es+'>'
       '<p>Aucun stream en direct...</p>'
       '<a href="/broadcast" class="btn bp">Commencer a diffuser</a>'
       '</div>'+cards+'</div></div>')
    j=('<script>'
       'var _io=io({transports:["polling","websocket"],upgrade:true});'
       'function load(){'
       '  fetch("/api/streams").then(function(r){return r.json();}).then(function(st){'
       '    var g=document.getElementById("gr"),e=document.getElementById("em");'
       '    if(!st.length){e.style.display="block";return;}e.style.display="none";'
       '    var ids={};st.forEach(function(s){ids[s.id]=true;});'
       '    var cs=g.querySelectorAll(".card");for(var i=0;i<cs.length;i++){if(!ids[cs[i].dataset.id])cs[i].remove();}'
       '    st.forEach(function(s){'
       '      var c=g.querySelector("[data-id=\""+s.id+"\"]");'
       '      if(!c){'
       '        c=document.createElement("a");c.href="/watch/"+s.id;c.className="card";c.dataset.id=s.id;'
       '        c.innerHTML="<div class=\\"thumb\\"><span class=\\"lb\\">LIVE</span><div class=\\"tov\\"><span class=\\"pi\\">&#9654;</span></div></div><div class=\\"ci\\"><h3>"+s.title+"</h3><span id=\\"v-"+s.id+"\\">"+s.viewers+" viewers</span></div>";'
       '        g.appendChild(c);}else{var v=document.getElementById("v-"+s.id);if(v)v.textContent=s.viewers+" viewers";}'
       '    });}).catch(function(){});}'
       'load();setInterval(load,5000);'
       '_io.on("stream_created",load);_io.on("stream_ended",load);'
       '</script>')
    return _page('StreamCaster',b,j)

@app.route('/broadcast')
def broadcast_page():
    b=('<div class="bc"><h1>&#128225; Centre de diffusion</h1><div class="bc-grid">'
       '<div class="ic"><h3>Diffuser depuis votre PC</h3>'
       '<p style="margin-bottom:10px">URL du serveur :</p>'
       '<div class="ub2" id="su">...</div>'
       '<button class="btn bp" style="margin-top:10px;width:100%" id="cb">Copier l URL</button>'
       '<div style="margin-top:20px"><p style="color:#a78bfa;font-weight:700;margin-bottom:8px">Instructions :</p>'
       '<ol class="how">'
       '<li>Clonez le projet localement</li>'
       '<li>Lancez python broadcaster.py</li>'
       '<li>Collez cette URL dans le champ serveur</li>'
       '<li>Selectionnez votre carte de capture USB</li>'
       '<li>Cliquez sur Demarrer le Stream</li>'
       '</ol></div></div>'
       '<div class="ic"><h3>Streams actifs</h3><div id="al"><p style="color:#888">Chargement...</p></div>'
       '<h3 style="margin-top:24px">Statistiques</h3><div id="ls" class="lg"></div>'
       '</div></div></div>')
    j=('<script>'
       'document.getElementById("su").textContent=window.location.origin;'
       'document.getElementById("cb").onclick=function(){navigator.clipboard.writeText(document.getElementById("su").textContent).then(function(){document.getElementById("cb").textContent="Copie!";}).catch(function(){});};'
       'function lbc(){'
       '  fetch("/api/streams").then(function(r){return r.json();}).then(function(st){'
       '    var l=document.getElementById("al");'
       '    if(!st.length){l.innerHTML="<p style=\\"color:#888\\">Aucun stream actif</p>";return;}'
       '    l.innerHTML=st.map(function(s){return "<div class=\\"asi\\"><a href=\\"/watch/"+s.id+"\\">"+s.title+"</a><span style=\\"margin-left:auto\\">"+s.viewers+"v</span></div>";}).join("");});'
       '  fetch("/api/stats").then(function(r){return r.json();}).then(function(d){'
       '    document.getElementById("ls").innerHTML="<div class=\\"li\\"><span>Streams</span><b>"+d.streams+"</b></div><div class=\\"li\\"><span>Viewers</span><b>"+d.viewers+"</b></div><div class=\\"li\\"><span>Messages</span><b>"+d.messages+"</b></div><div class=\\"li\\"><span>Uptime</span><b>"+d.uptime+"</b></div>";'
       '  }).catch(function(){});}'
       'lbc();setInterval(lbc,5000);'
       '</script>')
    return _page('Diffuser',b,j)

@app.route('/watch/<sid>')
def watch_page(sid):
    s=active_streams.get(sid)
    if not s:return redirect(url_for('index'))
    safe=s['title'].replace('\\','\\\\').replace('"','\\"')
    j='<script>var SID="'+sid+'";var TITLE="'+safe+'";'+_WJS+'</script>'
    return _page(s['title'],_WH,j)

@app.route('/admin',methods=['GET','POST'])
def admin():
    err=''
    if request.method=='POST':
        if request.form.get('password','')==app.config['ADMIN_PASSWORD']:
            session['admin']=True;return redirect(url_for('admin'))
        err='<div class="fb"><div class="fm">Mot de passe incorrect</div></div>'
    if not session.get('admin'):
        b=(err+'<div class="lw"><div class="lc"><h2>Administration</h2>'
           '<form method="POST" action="/admin">'
           '<div class="fg"><label>Mot de passe</label>'
           '<input type="password" name="password" class="fi" autofocus placeholder="..."></div>'
           '<button type="submit" class="btn bp" style="width:100%;margin-top:8px">Connexion</button>'
           '</form></div></div>')
        return _page('Admin',b)
    rows=''
    for s in active_streams.values():
        i2=s['id']
        rows+='<tr><td><code>'+i2+'</code></td><td>'+s['title']+'</td><td>'+str(s['viewers'])+'</td><td>'+_ts(s['created'])+'</td>'
        rows+='<td><a href="/watch/'+i2+'" class="bsm bb" target="_blank">Voir</a> '
        rows+='<form method="POST" action="/admin/kick/'+i2+'" style="display:inline" onsubmit="return confirm(&quot;Arreter ?&quot;)"><button type="submit" class="bsm br">Stop</button></form></td></tr>'
    tbl=('<table class="at2"><thead><tr><th>ID</th><th>Titre</th><th>V</th><th>Debut</th><th>Act</th></tr></thead><tbody>'+rows+'</tbody></table>') if rows else '<div class="em">Aucun stream actif</div>'
    tv=sum(len(v) for v in stream_viewers.values())
    b=('<div class="aw">'
       '<div class="at"><h1>Dashboard Admin</h1><a href="/admin/logout" class="btn bd">Deconnexion</a></div>'
       '<div class="sc">'
       '<div class="sv"><div class="si">Live</div><div class="sv2">'+str(len(active_streams))+'</div><div class="sl2">Streams</div></div>'
       '<div class="sv"><div class="si">Viewers</div><div class="sv2">'+str(tv)+'</div><div class="sl2">Actuels</div></div>'
       '<div class="sv"><div class="si">Chat</div><div class="sv2">'+str(server_stats['total_messages'])+'</div><div class="sl2">Messages</div></div>'
       '<div class="sv"><div class="si">Total</div><div class="sv2">'+str(server_stats['total_streams'])+'</div><div class="sl2">Streams</div></div>'
       '<div class="sv"><div class="si">Up</div><div class="sv2 sm">'+_up()+'</div><div class="sl2">Uptime</div></div>'
       '</div><div class="as"><h2>Streams</h2>'+tbl+'</div>'
       '<div class="as"><h2>Config</h2><div class="cg">'
       '<div class="cfg"><span class="ck">Python</span><code>3.11 Docker</code></div>'
       '<div class="cfg"><span class="ck">Worker</span><code>gthread</code></div>'
       '<div class="cfg"><span class="ck">CSS</span><code>Inline</code></div>'
       '</div></div><p class="ar">Actualisation toutes les 10s</p></div>')
    return _page('Dashboard Admin',b,head='<meta http-equiv="refresh" content="10">')

@app.route('/admin/logout')
def admin_logout():session.pop('admin',None);return redirect(url_for('index'))
@app.route('/admin/kick/<sid>',methods=['POST'])
def admin_kick(sid):
    if not session.get('admin'):return jsonify({'error':'non autorise'}),403
    _cleanup(sid);socketio.emit('stream_ended',{'stream_id':sid})
    return redirect(url_for('admin'))
@app.route('/api/streams')
def api_streams():return jsonify(list(active_streams.values()))
@app.route('/api/stats')
def api_stats():
    return jsonify({'streams':len(active_streams),'viewers':sum(len(v) for v in stream_viewers.values()),
        'total_streams':server_stats['total_streams'],'total_messages':server_stats['total_messages'],'uptime':_up()})
@app.route('/api/stream/create',methods=['POST'])
def api_create():
    data=request.get_json(silent=True) or {};sid=uuid.uuid4().hex[:8];title=str(data.get('title','Stream'))[:80]
    (STREAMS_DIR/sid).mkdir(parents=True,exist_ok=True)
    meta={'id':sid,'title':title,'created':time.time(),'status':'live','viewers':0}
    with _lock:
        active_streams[sid]=meta;stream_viewers[sid]=set();chat_history[sid]=[];server_stats['total_streams']+=1
    socketio.emit('stream_created',meta);return jsonify({'stream_id':sid,'status':'ok'})
@app.route('/api/stream/<sid>/upload',methods=['POST'])
def api_upload(sid):
    if sid not in active_streams:return jsonify({'error':'stream inconnu'}),404
    raw=request.headers.get('X-Filename','')
    if not raw:return jsonify({'error':'X-Filename manquant'}),400
    fname=Path(raw).name
    if not fname.endswith(('.m3u8','.ts')):return jsonify({'error':'type non autorise'}),400
    (STREAMS_DIR/sid/fname).write_bytes(request.data)
    if fname.endswith('.m3u8'):_master(sid)
    return jsonify({'ok':True})
@app.route('/api/stream/<sid>/stop',methods=['POST'])
def api_stop(sid):
    if sid not in active_streams:return jsonify({'error':'inconnu'}),404
    _cleanup(sid);socketio.emit('stream_ended',{'stream_id':sid});return jsonify({'status':'stopped'})
@app.route('/api/stream/<sid>/info')
def api_info(sid):
    if sid not in active_streams:return jsonify({'error':'inconnu'}),404
    m=dict(active_streams[sid]);m['chat_count']=len(chat_history.get(sid,[]))
    return jsonify(m)
@app.route('/streams/<sid>/<path:fn>')
def serve_hls(sid,fn):
    safe=Path(fn).name;sdir=STREAMS_DIR/sid
    if not (sdir/safe).exists():return Response('Not Found',status=404)
    resp=send_from_directory(str(sdir),safe)
    resp.headers['Cache-Control']='no-cache, no-store'
    resp.headers['Access-Control-Allow-Origin']='*'
    if safe.endswith('.m3u8'):resp.headers['Content-Type']='application/vnd.apple.mpegurl'
    elif safe.endswith('.ts'):resp.headers['Content-Type']='video/MP2T'
    return resp

@socketio.on('connect')
def _co():pass
@socketio.on('join_stream')
def _jo(data):
    if not isinstance(data,dict):return
    sid=data.get('stream_id','');u=str(data.get('username','Anonyme'))[:30]
    if not sid or sid not in active_streams:return
    join_room(sid)
    with _lock:
        stream_viewers.setdefault(sid,set()).add(request.sid)
        cnt=len(stream_viewers[sid]);active_streams[sid]['viewers']=cnt
    emit('chat_history',{'messages':chat_history.get(sid,[])[-50:]})
    emit('system_msg',{'text':'Bienvenue '+u,'ts':time.time()},to=sid)
    emit('viewer_count',{'count':cnt},to=sid)
@socketio.on('leave_stream')
def _le(data):
    if not isinstance(data,dict):return
    sid=data.get('stream_id','');leave_room(sid)
    with _lock:
        if sid in stream_viewers:
            stream_viewers[sid].discard(request.sid);cnt=len(stream_viewers[sid])
            if sid in active_streams:active_streams[sid]['viewers']=cnt
        else:cnt=0
    emit('viewer_count',{'count':cnt},to=sid)
@socketio.on('disconnect')
def _dc():
    rsid=request.sid
    with _lock:
        for s in stream_viewers.values():s.discard(rsid)
        for k,m in active_streams.items():m['viewers']=len(stream_viewers.get(k,set()))
@socketio.on('chat_msg')
def _cm(data):
    if not isinstance(data,dict):return
    sid=data.get('stream_id','');u=str(data.get('username','Anonyme'))[:30]
    text=str(data.get('text','')).strip()[:500]
    if not text or not sid or sid not in active_streams:return
    msg={'username':u,'text':text,'ts':time.time(),'id':uuid.uuid4().hex[:6]}
    with _lock:
        chat_history.setdefault(sid,[]).append(msg);chat_history[sid]=chat_history[sid][-300:]
        server_stats['total_messages']+=1
    emit('new_chat_msg',msg,to=sid)

_WH=(
'<div class="wr"><div class="pc">'
'<div class="pw" id="pw">'
'<video id="v" autoplay playsinline></video>'
'<div class="ov" id="ov"><div class="oi"><div class="sp"></div>'
'<p id="ot">Connexion au stream...</p>'
'<p id="ot2" style="font-size:.82em;margin-top:6px;opacity:.55">Demarrage...</p>'
'</div></div>'
'<div class="ub" id="ub"><button onclick="dU()">&#128266; Cliquez pour activer le son</button></div>'
'<div class="cb2" id="cb">'
'<div class="pr"><div class="pg" id="pg"><div class="pf" id="pf"></div><div class="pp" id="pp"></div><div class="pt" id="pt"></div></div>'
'<span class="lp">LIVE</span><span class="lat" id="lat"></span></div>'
'<div class="cr">'
'<div class="cl">'
'<button class="btn2" id="bp"><svg viewBox="0 0 24 24"><path id="plp" d="M6 4l15 8-15 8V4z"/></svg></button>'
'<button class="btn2" id="bm"><svg viewBox="0 0 24 24"><path id="mp" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></button>'
'<div class="vw"><input type="range" id="vl" min="0" max="1" step="0.02" value="1"></div>'
'<span class="ct" id="ct">00:00</span>'
'</div><div class="crt">'
'<select class="cs" id="ss"><option value="0.5">0.5x</option><option value="1" selected>1x</option><option value="1.5">1.5x</option><option value="2">2x</option></select>'
'<select class="cs" id="qs"><option value="-1">Auto</option></select>'
'<button class="btn2 bfs" id="bf">'
'<svg viewBox="0 0 24 24" id="ie"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>'
'<svg viewBox="0 0 24 24" id="ic" style="display:none"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>'
'</button></div></div></div>'
'</div>'
'<div class="pm" id="_pm">'
'<div class="pml"><span class="ls">LIVE</span><h2 id="st">Stream</h2></div>'
'<span id="vc" class="pr2">0 viewers</span>'
'</div></div>'
'<div class="cc" id="_cc">'
'<div class="ch2"><h3>&#128172; Chat</h3>'
'<div class="nr"><label class="sw"><input type="checkbox" id="nt" checked><span class="sl"></span></label><span>Notif</span></div>'
'</div><div class="cm2" id="cm"></div>'
'<div class="ia">'
'<input type="text" id="un" placeholder="Pseudo..." maxlength="20">'
'<div class="mr"><input type="text" id="mi" placeholder="Message..." maxlength="500" autocomplete="off"><button id="sb">&#10148;</button></div>'
'</div></div></div>'
'<audio id="ns" preload="auto"><source src="/static/sounds/notification.wav" type="audio/wav"></audio>'
)

_WJS=(
'if(document.getElementById("st"))document.getElementById("st").textContent=TITLE;'
'var sock=io({transports:["polling","websocket"],upgrade:true});'
'var vid=document.getElementById("v"),pw=document.getElementById("pw");'
'var ov=document.getElementById("ov"),ot=document.getElementById("ot");'
'var cb=document.getElementById("cb"),bp=document.getElementById("bp");'
'var plp=document.getElementById("plp"),bm=document.getElementById("bm");'
'var mp=document.getElementById("mp"),vl=document.getElementById("vl");'
'var ct=document.getElementById("ct"),lat=document.getElementById("lat");'
'var ss=document.getElementById("ss"),qs=document.getElementById("qs");'
'var bf=document.getElementById("bf"),ie=document.getElementById("ie"),ic=document.getElementById("ic");'
'var pg=document.getElementById("pg"),pf=document.getElementById("pf");'
'var pp2=document.getElementById("pp"),pt=document.getElementById("pt");'
'var cm=document.getElementById("cm"),mi=document.getElementById("mi");'
'var sb=document.getElementById("sb"),un=document.getElementById("un");'
'var nt=document.getElementById("nt"),ns=document.getElementById("ns");'
'var vc=document.getElementById("vc"),ub=document.getElementById("ub");'
'var hls=null,ht=null,fsm=false,rc=0;'
'var IPL="M6 4l15 8-15 8V4z",IPA="M6 19h4V5H6v14zm8-14v14h4V5h-4z";'
'var IVO="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z";'
'var IMU="M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06A8.99 8.99 0 0 0 17.73 19l2 2L21 19.73l-18-18z";'
'function dU(){vid.muted=false;vid.volume=1;mp.setAttribute("d",IVO);vl.value=1;ub.style.display="none";}'
'function initP(){'
'  var src="/streams/"+SID+"/master.m3u8";'
'  if(typeof Hls!=="undefined"&&Hls.isSupported()){'
'    if(hls){hls.destroy();hls=null;}'
'    hls=new Hls({lowLatencyMode:true,liveSyncDurationCount:1,liveMaxLatencyDurationCount:3,'
'      maxLiveSyncPlaybackRate:1.5,maxBufferLength:4,maxMaxBufferLength:8,backBufferLength:4,startLevel:-1,'
'      manifestLoadingMaxRetry:20,manifestLoadingRetryDelay:500,fragLoadingMaxRetry:20,fragLoadingRetryDelay:500});'
'    hls.loadSource(src);hls.attachMedia(vid);'
'    hls.on(Hls.Events.MANIFEST_PARSED,function(e,d){'
'      hoO();qs.innerHTML="<option value=\"-1\">Auto</option>";'
'      d.levels.forEach(function(lv,i){var o=document.createElement("option");o.value=i;o.textContent=lv.height+"p";qs.appendChild(o);});'
'      rc=0;vid.muted=false;vid.volume=1;'
'      vid.play().then(function(){ub.style.display="none";mp.setAttribute("d",IVO);vl.value=1;'
'      }).catch(function(){vid.muted=true;vid.play().catch(function(){});ub.style.display="flex";mp.setAttribute("d",IMU);vl.value=0;});'
'    });'
'    hls.on(Hls.Events.ERROR,function(e,d){if(d.fatal){rc++;ot.textContent="Reconnexion...";ov.style.display="flex";ov.style.opacity="1";setTimeout(tryI,Math.min(1000*rc,4000));}});'
'    hls.on(Hls.Events.FRAG_BUFFERED,function(){if(vid.buffered.length&&vid.duration){var e=hls.liveSyncPosition||vid.duration;var dl=e-vid.currentTime;lat.textContent=dl>0?Math.round(dl)+"s":"";} });'
'    qs.onchange=function(){hls.currentLevel=parseInt(qs.value);};'
'  }else if(vid.canPlayType("application/vnd.apple.mpegurl")){'
'    vid.src=src;vid.addEventListener("loadedmetadata",hoO,{once:true});'
'    vid.muted=false;vid.play().catch(function(){vid.muted=true;vid.play().catch(function(){});ub.style.display="flex";});'
'  }'
'}'
'function tryI(){ot.textContent="Connexion...";fetch("/streams/"+SID+"/master.m3u8",{cache:"no-store"}).then(function(r){if(r.ok)initP();else setTimeout(tryI,1000);}).catch(function(){setTimeout(tryI,1000);});}'
'tryI();'
'function hoO(){ov.style.opacity="0";setTimeout(function(){ov.style.display="none";},400);}'
'function shO(m){ot.textContent=m;var s=ov.querySelector(".sp");if(s)s.style.display="none";ov.style.display="flex";ov.style.opacity="1";}'
'bp.onclick=function(){vid.paused?vid.play():vid.pause();};'
'vid.addEventListener("play",function(){plp.setAttribute("d",IPA);});'
'vid.addEventListener("pause",function(){plp.setAttribute("d",IPL);});'
'vid.addEventListener("dblclick",tFS);'
'bm.onclick=function(){vid.muted=!vid.muted;mp.setAttribute("d",vid.muted?IMU:IVO);vl.value=vid.muted?0:Math.max(vid.volume,0.1);if(!vid.muted)ub.style.display="none";};'
'vl.oninput=function(){vid.volume=parseFloat(vl.value);vid.muted=(vid.volume===0);mp.setAttribute("d",vid.muted?IMU:IVO);if(!vid.muted)ub.style.display="none";};'
'ss.onchange=function(){vid.playbackRate=parseFloat(ss.value);};'
'vid.addEventListener("timeupdate",function(){var t=Math.floor(vid.currentTime);ct.textContent=String(Math.floor(t/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0");if(vid.duration){var p=(vid.currentTime/vid.duration)*100;pp2.style.width=p+"%";pt.style.left=p+"%";if(vid.buffered.length)pf.style.width=(vid.buffered.end(vid.buffered.length-1)/vid.duration*100)+"%";}});'
'pg.onclick=function(e){if(!vid.duration)return;var r=pg.getBoundingClientRect();vid.currentTime=((e.clientX-r.left)/r.width)*vid.duration;};'
'function tFS(){if(!document.fullscreenElement&&!document.webkitFullscreenElement)eFS();else xFS();}'
'function eFS(){var fn=pw.requestFullscreen||pw.webkitRequestFullscreen||pw.mozRequestFullScreen||pw.msRequestFullscreen;if(fn)fn.call(pw);}'
'function xFS(){var fn=document.exitFullscreen||document.webkitExitFullscreen||document.mozCancelFullScreen||document.msExitFullscreen;if(fn)fn.call(document);}'
'function onFC(){fsm=!!(document.fullscreenElement||document.webkitFullscreenElement);if(fsm){document.body.classList.add("fs");pw.classList.add("fa");ie.style.display="none";ic.style.display="block";sH();}else{document.body.classList.remove("fs");pw.classList.remove("fa");ie.style.display="block";ic.style.display="none";cb.classList.remove("ch");document.body.style.cursor="";cH();}}'
'["fullscreenchange","webkitfullscreenchange","mozfullscreenchange","MSFullscreenChange"].forEach(function(ev){document.addEventListener(ev,onFC);});'
'bf.onclick=tFS;'
'function sH(){cH();cb.classList.remove("ch");document.body.style.cursor="";ht=setTimeout(function(){if(fsm){cb.classList.add("ch");document.body.style.cursor="none";}},3000);}'
'function cH(){if(ht){clearTimeout(ht);ht=null;}}'
'pw.addEventListener("mousemove",function(){if(fsm)sH();});'
'cb.addEventListener("mouseenter",function(){cH();cb.classList.remove("ch");document.body.style.cursor="";});'
'cb.addEventListener("mouseleave",function(){if(fsm)sH();});'
'document.addEventListener("keydown",function(e){var tg=document.activeElement.tagName;if(tg==="INPUT"||tg==="TEXTAREA"||tg==="SELECT")return;if(e.key==="f"||e.key==="F"){e.preventDefault();tFS();}else if(e.key===" "||e.key==="k"||e.key==="K"){e.preventDefault();vid.paused?vid.play():vid.pause();}else if(e.key==="m"||e.key==="M"){e.preventDefault();bm.onclick();}else if(e.key==="ArrowUp"){e.preventDefault();vid.volume=Math.min(1,vid.volume+0.1);vl.value=vid.volume;}else if(e.key==="ArrowDown"){e.preventDefault();vid.volume=Math.max(0,vid.volume-0.1);vl.value=vid.volume;}else if(e.key==="Escape"&&fsm){e.preventDefault();xFS();}});'
'un.value=localStorage.getItem("sc_un")||"";'
'sock.on("connect",function(){sock.emit("join_stream",{stream_id:SID,username:un.value.trim()||"Anonyme"});});'
'sock.on("connect_error",function(e){console.warn("Socket:",e.message);});'
'sock.on("chat_history",function(d){d.messages.forEach(function(m){aM(m,false);});cm.scrollTop=cm.scrollHeight;});'
'sock.on("new_chat_msg",function(m){aM(m,true);cm.scrollTop=cm.scrollHeight;if(nt.checked&&m.username!==(un.value.trim()||"Anonyme"))pN(m.username,m.text);});'
'sock.on("system_msg",function(d){var div=document.createElement("div");div.className="sy";div.textContent=d.text;cm.appendChild(div);cm.scrollTop=cm.scrollHeight;});'
'sock.on("viewer_count",function(d){vc.textContent=d.count+" viewers";});'
'sock.on("stream_ended",function(d){if(d.stream_id===SID)shO("Stream termine");});'
'function aM(m,an){var d=document.createElement("div");d.className="msg"+(an?" mn":"");var t=new Date(m.ts*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});d.innerHTML="<span class=\\"mt\\">" +t+"</span><span class=\\"mu\\">"+esc(m.username)+"</span><span class=\\"mx\\">"+esc(m.text)+"</span>";cm.appendChild(d);while(cm.children.length>200)cm.removeChild(cm.firstChild);}'
'function esc(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}'
'function sM(){var t=mi.value.trim();if(!t)return;var n=un.value.trim()||"Anonyme";localStorage.setItem("sc_un",n);un.value=n;sock.emit("chat_msg",{stream_id:SID,username:n,text:t});mi.value="";}'
'sb.onclick=sM;mi.addEventListener("keypress",function(e){if(e.key==="Enter")sM();});'
'function pN(u,t){try{ns.currentTime=0;ns.play().catch(function(){});}catch(e){}if("Notification"in window&&Notification.permission==="granted")new Notification("Message de "+u,{body:t,silent:true});}'
'if("Notification"in window&&Notification.permission==="default")Notification.requestPermission();'
)

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    print('StreamCaster http://0.0.0.0:'+str(port))
    socketio.run(app,host='0.0.0.0',port=port,debug=False,
        use_reloader=False,log_output=True,allow_unsafe_werkzeug=True)