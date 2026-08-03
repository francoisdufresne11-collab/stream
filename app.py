import os,sys,time,uuid,shutil,secrets,threading,datetime
from pathlib import Path
from flask import Flask,request,jsonify,send_from_directory,Response,redirect,url_for,session
from flask_socketio import SocketIO,emit,join_room,leave_room

app=Flask(__name__,static_folder='static',static_url_path='/static')
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config['ADMIN_PASSWORD']=os.environ.get('ADMIN_PASSWORD','admin2026')
socketio=SocketIO(app,cors_allowed_origins='*',async_mode='threading',
    ping_timeout=60,ping_interval=20,max_http_buffer_size=50_000_000,
    logger=False,engineio_logger=False)

_rooms={};_sids={};_lock=threading.Lock()
_stats={'rooms':0,'msgs':0,'started':time.time()}

def _up():
    s=int(time.time()-_stats['started']);h,r=divmod(s,3600);m,s=divmod(r,60)
    return '%02d:%02d:%02d'%(h,m,s)
def _ts(v):
    try:return datetime.datetime.fromtimestamp(float(v)).strftime('%H:%M:%S')
    except:return '?'

_CSS='''
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--b1:#0a0a14;--b2:#12121f;--b3:#1a1a2e;--bi:#070710;--ac:#a78bfa;--a2:#7c3aed;
  --gn:#10b981;--rd:#ef4444;--bl:#3b82f6;--yw:#f59e0b;
  --tx:#e8e8f0;--mu:#6b6b8a;--bo:#2a2a4a;--ch:#0d0d1f}
html,body{height:100%;margin:0;padding:0}
body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--b1);color:var(--tx);min-height:100vh}
a{color:var(--ac);text-decoration:none}a:hover{color:#c4b5fd}
.nb{display:flex;align-items:center;justify-content:space-between;padding:0 28px;
  background:rgba(18,18,31,.96);backdrop-filter:blur(20px);
  border-bottom:1px solid rgba(167,139,250,.12);position:sticky;top:0;z-index:200;height:58px}
.logo{font-size:1.2em;font-weight:900;color:var(--ac)!important;text-decoration:none;display:flex;align-items:center;gap:8px}
.logo-dot{width:10px;height:10px;background:var(--rd);border-radius:50%;animation:pl 2s infinite}
.nl{display:flex;gap:6px}
.nl a{color:var(--mu);font-weight:500;font-size:.85em;text-decoration:none;padding:6px 14px;
  border-radius:20px;transition:.2s;border:1px solid transparent}
.nl a:hover{color:var(--ac);border-color:rgba(167,139,250,.3);background:rgba(167,139,250,.08)}
.mc{max-width:1400px;margin:0 auto;padding:24px}
@keyframes pl{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes sp{to{transform:rotate(360deg)}}
@keyframes fi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes pu{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
.hero{text-align:center;padding:50px 20px 36px}
.hero h1{font-size:2.6em;font-weight:900;background:linear-gradient(135deg,#a78bfa,#60a5fa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}
.hero p{color:var(--mu);font-size:1em;margin-bottom:28px}
.hero-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.rooms{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:28px}
.room-card{background:var(--b3);border-radius:14px;border:1px solid var(--bo);padding:18px;
  display:block;color:var(--tx);transition:all .2s;text-decoration:none}
.room-card:hover{border-color:var(--ac);box-shadow:0 6px 30px rgba(167,139,250,.12);transform:translateY(-2px)}
.room-live{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.rdot{width:8px;height:8px;background:var(--rd);border-radius:50%;animation:pl 1.5s infinite}
.room-title{font-size:1.05em;font-weight:700;margin-bottom:5px}
.room-meta{color:var(--mu);font-size:.82em;display:flex;gap:14px}
.no-rooms{grid-column:1/-1;text-align:center;padding:50px 20px;color:var(--mu)}
.no-rooms h3{font-size:1.1em;margin-bottom:6px;color:var(--tx)}
.bc-page{display:grid;grid-template-columns:1fr 400px;gap:18px;height:calc(100vh - 106px)}
.bc-preview{background:#000;border-radius:14px;overflow:hidden;position:relative;display:flex;flex-direction:column}
.bc-video-wrap{flex:1;position:relative;background:#000}
.bc-video-wrap video{width:100%;height:100%;object-fit:contain;display:block}
.bc-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.75)}
.bc-overlay-inner{text-align:center}
.bc-status{padding:12px 18px;background:rgba(18,18,31,.92);display:flex;align-items:center;gap:10px;flex-shrink:0}
.bc-status-dot{width:10px;height:10px;border-radius:50%;background:var(--mu);transition:.3s}
.bc-status-dot.live{background:var(--rd);animation:pl 1.5s infinite}
.bc-status-dot.ready{background:var(--gn)}
.bc-panel{display:flex;flex-direction:column;gap:12px;overflow-y:auto}
.panel-card{background:var(--b3);border-radius:12px;border:1px solid var(--bo);padding:16px}
.panel-card h3{font-size:.8em;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
.field{margin-bottom:10px}
.field label{display:block;font-size:.8em;color:var(--mu);margin-bottom:4px}
.inp{width:100%;padding:9px 11px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);
  border-radius:8px;font-size:.88em;outline:none;transition:.2s}
.inp:focus{border-color:var(--ac)}
.sel{width:100%;padding:9px 11px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);
  border-radius:8px;font-size:.88em;outline:none;cursor:pointer}
.sel:focus{border-color:var(--ac)}
.btn-row{display:flex;gap:6px;flex-wrap:wrap}
/* SOURCE TABS */
.src-tabs{display:flex;gap:4px;margin-bottom:12px;background:var(--bi);border-radius:8px;padding:3px}
.src-tab{flex:1;padding:7px;border:none;background:transparent;color:var(--mu);
  border-radius:6px;cursor:pointer;font-size:.82em;font-weight:600;transition:.2s;text-align:center}
.src-tab.active{background:var(--a2);color:#fff}
.src-tab:hover:not(.active){background:rgba(255,255,255,.06);color:var(--tx)}
/* DEVICE LIST */
.device-list{display:flex;flex-direction:column;gap:6px;max-height:200px;overflow-y:auto}
.device-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;
  border:1px solid var(--bo);cursor:pointer;transition:.2s}
.device-item:hover{border-color:rgba(167,139,250,.4);background:rgba(167,139,250,.05)}
.device-item.selected{border-color:var(--ac);background:rgba(167,139,250,.1)}
.device-icon{font-size:1.3em;flex-shrink:0;width:28px;text-align:center}
.device-name{flex:1;font-size:.84em;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.device-type{font-size:.72em;color:var(--mu)}
.device-check{width:16px;height:16px;border-radius:50%;border:2px solid var(--bo);flex-shrink:0}
.device-item.selected .device-check{background:var(--ac);border-color:var(--ac)}
.no-devices{text-align:center;color:var(--mu);font-size:.84em;padding:16px}
/* WATCH */
.watch-page{display:flex;height:calc(100vh - 58px);overflow:hidden}
.watch-main{flex:1;display:flex;flex-direction:column;min-width:0;background:#000}
.watch-video-wrap{flex:1;position:relative;background:#000;overflow:hidden;min-height:0}
.watch-video-wrap video{width:100%;height:100%;object-fit:contain;display:block;background:#000}
.watch-meta{padding:9px 16px;background:var(--b2);border-top:1px solid var(--bo);flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between}
.watch-sidebar{width:350px;min-width:300px;display:flex;flex-direction:column;background:var(--ch);border-left:1px solid var(--bo)}
.sidebar-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;
  background:var(--b2);border-bottom:1px solid var(--bo);flex-shrink:0}
.sidebar-head h3{font-size:.88em;font-weight:700}
.chat-msgs{flex:1;overflow-y:auto;padding:8px 12px;display:flex;flex-direction:column;gap:3px;
  scrollbar-width:thin;scrollbar-color:var(--bo) transparent}
.chat-msg{padding:4px 7px;border-radius:7px;font-size:.84em;line-height:1.5;word-break:break-word}
.chat-msg:hover{background:rgba(255,255,255,.03)}
.chat-new{animation:fi .3s ease}
.chat-time{color:var(--mu);font-size:.72em;margin-right:4px}
.chat-user{color:var(--ac);font-weight:700;margin-right:4px}
.chat-text{color:var(--tx)}
.chat-sys{text-align:center;color:var(--mu);font-size:.75em;padding:3px;font-style:italic}
.chat-inp-area{padding:9px 12px;border-top:1px solid var(--bo);background:var(--b2);flex-shrink:0}
.chat-name{width:100%;padding:6px 10px;margin-bottom:5px;background:var(--bi);color:var(--ac);
  border:1px solid var(--bo);border-radius:7px;font-size:.82em;font-weight:600;outline:none}
.chat-name:focus{border-color:var(--ac)}
.chat-row{display:flex;gap:5px}
.chat-in{flex:1;padding:8px 10px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);
  border-radius:8px;font-size:.86em;outline:none}
.chat-in:focus{border-color:var(--ac)}
.chat-send{width:40px;background:var(--a2);color:#fff;border:none;border-radius:8px;
  cursor:pointer;font-size:1.05em;transition:.2s}
.chat-send:hover{background:var(--ac)}
/* VIDEO CONTROLS */
.vc-overlay{position:absolute;inset:0;z-index:10;background:rgba(0,0,0,.88);
  display:flex;align-items:center;justify-content:center;transition:opacity .4s}
.vc-inner{text-align:center;padding:24px}
.spinner{width:48px;height:48px;border:4px solid var(--bo);border-top-color:var(--ac);
  border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 14px}
.vc-overlay p{color:var(--mu);font-size:.9em;margin-bottom:4px}
.ctrl-bar{position:absolute;bottom:0;left:0;right:0;z-index:30;
  background:linear-gradient(transparent,rgba(0,0,0,.95) 50%);
  padding:36px 14px 10px;transition:opacity .3s,transform .3s}
.ctrl-bar.hidden{opacity:0;transform:translateY(100%);pointer-events:none}
.ctrl-progress{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.ctrl-live{background:var(--rd);color:#fff;font-size:.67em;font-weight:800;
  padding:3px 8px;border-radius:4px;animation:pl 2s infinite}
.ctrl-lat{color:var(--gn);font-size:.7em;font-family:monospace;padding:2px 7px;
  background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.2);border-radius:4px}
.ctrl-btns{display:flex;align-items:center;justify-content:space-between;gap:6px}
.ctrl-l,.ctrl-r{display:flex;align-items:center;gap:5px}
.cb3{background:none;border:none;cursor:pointer;width:34px;height:34px;display:flex;align-items:center;
  justify-content:center;color:#fff;border-radius:7px;transition:background .2s;padding:4px;flex-shrink:0}
.cb3:hover{background:rgba(255,255,255,.15)}
.cb3 svg{width:18px;height:18px;fill:currentColor}
.cb3.big svg{width:21px;height:21px}
.vol-wrap{width:76px;display:flex;align-items:center}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:4px;
  background:rgba(255,255,255,.25);border-radius:2px;outline:none;cursor:pointer}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:13px;height:13px;
  border-radius:50%;background:var(--ac);cursor:pointer}
input[type=range]::-moz-range-thumb{width:13px;height:13px;border-radius:50%;
  background:var(--ac);border:none;cursor:pointer}
.ctrl-time{color:rgba(255,255,255,.65);font-size:.78em;font-family:monospace;white-space:nowrap}
.unmute-btn{position:absolute;bottom:72px;left:50%;transform:translateX(-50%);
  z-index:20;display:none;align-items:center}
.unmute-btn button{background:linear-gradient(135deg,var(--a2),#4f46e5);color:#fff;border:none;
  border-radius:50px;padding:12px 26px;font-size:.92em;font-weight:700;cursor:pointer;
  box-shadow:0 4px 20px rgba(124,58,237,.4);animation:pu 2s infinite}
.watch-video-wrap.fa{position:fixed!important;inset:0!important;z-index:9999!important;
  width:100vw!important;height:100vh!important;background:#000!important}
.watch-video-wrap.fa video{width:100%!important;height:100%!important;object-fit:contain!important}
body.fs .nb,body.fs .watch-meta,body.fs .watch-sidebar{display:none!important}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 20px;border-radius:50px;
  font-weight:700;font-size:.88em;border:none;cursor:pointer;transition:all .2s;text-decoration:none}
.btn-primary{background:linear-gradient(135deg,var(--a2),#4f46e5);color:#fff;box-shadow:0 4px 14px rgba(124,58,237,.3)}
.btn-primary:hover{background:linear-gradient(135deg,var(--ac),#818cf8);color:#fff}
.btn-secondary{background:rgba(255,255,255,.07);color:var(--tx);border:1px solid var(--bo)}
.btn-secondary:hover{background:rgba(255,255,255,.11);border-color:var(--ac)}
.btn-danger{background:rgba(239,68,68,.14);color:var(--rd);border:1px solid rgba(239,68,68,.3)}
.btn-danger:hover{background:var(--rd);color:#fff}
.btn-sm{padding:6px 14px;font-size:.8em}
.btn-full{width:100%;justify-content:center}
.tag{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:20px;font-size:.76em;font-weight:700}
.tag-live{background:rgba(239,68,68,.14);color:var(--rd);border:1px solid rgba(239,68,68,.28)}
.tag-viewers{background:rgba(167,139,250,.1);color:var(--ac);border:1px solid rgba(167,139,250,.2)}
.share-box{background:var(--bi);border:1px solid rgba(167,139,250,.28);border-radius:9px;
  padding:10px 14px;font-family:monospace;font-size:.8em;color:var(--ac);
  word-break:break-all;cursor:pointer;transition:.2s}
.share-box:hover{border-color:var(--ac)}
.stats-row{display:flex;gap:6px;flex-wrap:wrap}
.stat-box{flex:1;min-width:70px;background:var(--b2);border-radius:7px;border:1px solid var(--bo);
  padding:7px 10px;text-align:center}
.stat-val{font-size:1em;font-weight:900;color:var(--ac)}
.stat-lbl{font-size:.7em;color:var(--mu);margin-top:1px}
.toast{position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:7px}
.toast-msg{background:var(--b3);border:1px solid var(--bo);border-radius:10px;padding:11px 16px;
  font-size:.86em;animation:fi .3s ease;box-shadow:0 8px 30px rgba(0,0,0,.5);max-width:300px}
.toast-ok{border-color:rgba(16,185,129,.4);color:var(--gn)}
.toast-err{border-color:rgba(239,68,68,.4);color:var(--rd)}
.toast-info{border-color:rgba(167,139,250,.3);color:var(--ac)}
.adm-wrap{max-width:1100px;margin:0 auto}
.adm-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.adm-top h1{font-size:1.4em;font-weight:900}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:20px}
.sc{background:var(--b3);border:1px solid var(--bo);border-radius:11px;padding:16px;text-align:center}
.sc .sv{font-size:1.7em;font-weight:900;color:var(--ac);line-height:1}
.sc .sl{color:var(--mu);font-size:.78em;margin-top:3px}
.adm-sec{background:var(--b3);border:1px solid var(--bo);border-radius:11px;padding:18px;margin-bottom:14px}
.adm-sec h2{font-size:.82em;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}
.room-row{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--bo)}
.room-row:last-child{border:none}
.room-id{font-family:monospace;font-size:.78em;color:var(--mu);background:var(--bi);padding:2px 7px;border-radius:4px}
.room-tname{flex:1;font-weight:600;font-size:.9em}
.em{text-align:center;color:var(--mu);padding:20px;font-size:.88em}
.lw{display:flex;align-items:center;justify-content:center;min-height:60vh}
.lc{background:var(--b3);border:1px solid var(--bo);border-radius:16px;padding:38px;width:100%;max-width:370px}
.lc h2{margin-bottom:22px;text-align:center;color:var(--ac);font-size:1.2em}
.fg{margin-bottom:12px}
.fg label{display:block;margin-bottom:4px;color:var(--mu);font-size:.8em}
.fi{width:100%;padding:9px 12px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);
  border-radius:8px;font-size:.88em;outline:none}
.fi:focus{border-color:var(--ac)}
.fm{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;
  padding:8px 12px;color:var(--rd);font-size:.83em;margin-bottom:12px}
/* NR = notif row */
.nr{display:flex;align-items:center;gap:6px;font-size:.82em}
.sw{position:relative;display:inline-block;width:32px;height:17px}
.sw input{opacity:0;width:0;height:0}
.sl{position:absolute;inset:0;cursor:pointer;background:var(--bo);border-radius:17px;transition:.3s}
.sl::before{content:"";position:absolute;height:11px;width:11px;left:3px;bottom:3px;
  background:#fff;border-radius:50%;transition:.3s}
input:checked+.sl{background:var(--gn)}
input:checked+.sl::before{transform:translateX(15px)}
@media(max-width:1000px){.bc-page{grid-template-columns:1fr;height:auto}.watch-page{flex-direction:column}.watch-sidebar{width:100%;min-width:0;height:320px}}
@media(max-width:600px){.hero h1{font-size:1.7em}.ctrl-time{display:none}}
'''
_SIO='https://cdn.socket.io/4.7.5/socket.io.min.js'

def _page(title,body,js='',head=''):
    return ('<!DOCTYPE html><html lang="fr"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+title+' — StreamCaster</title>'
            '<style>'+_CSS+'</style>'
            '<script src="'+_SIO+'"></script>'
            +head+
            '</head><body>'
            '<nav class="nb">'
            '<a href="/" class="logo"><span class="logo-dot"></span>StreamCaster</a>'
            '<div class="nl">'
            '<a href="/">Accueil</a>'
            '<a href="/broadcast">Diffuser</a>'
            '<a href="/admin">Admin</a>'
            '</div></nav>'
            '<div class="toast" id="_toast"></div>'
            +body+
            '<script>'
            'function toast(m,t){var d=document.createElement("div");d.className="toast-msg toast-"+(t||"info");d.textContent=m;var c=document.getElementById("_toast");c.appendChild(d);setTimeout(function(){if(d.parentNode)d.remove();},3500);}'
            'function esc(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}'
            '</script>'
            +js+
            '</body></html>')

@app.errorhandler(404)
def e404(e):return _page('404','<div style="text-align:center;padding:80px"><h1 style="font-size:4em;color:var(--ac)">404</h1><p style="color:var(--mu);margin:12px 0 24px">Page introuvable</p><a href="/" class="btn btn-primary">Retour</a></div>'),404
@app.errorhandler(500)
def e500(e):return _page('500','<div style="text-align:center;padding:80px"><h1 style="font-size:4em;color:var(--rd)">500</h1><p style="color:var(--mu);margin:12px 0 24px">Erreur interne</p><a href="/" class="btn btn-primary">Retour</a></div>'),500

@app.route('/')
def index():
    with _lock:rl=list(_rooms.values())
    cards=''
    for r in sorted(rl,key=lambda x:-x['created']):
        rid=r['id'];vc=len(r['viewers'])
        src_icon='&#128247;' if r.get('source_type','cam')=='cam' else '&#128396;' if r.get('source_type')=='screen' else '&#127909;' if r.get('source_type')=='capture' else '&#128247;'
        cards+=('<a href="/watch/'+rid+'" class="room-card">'
               '<div class="room-live"><div class="rdot"></div>'
               '<span class="tag tag-live">LIVE</span>'
               '<span class="tag tag-viewers">&#128065; '+str(vc)+'</span>'
               '</div>'
               '<div class="room-title">'+r['title']+'</div>'
               '<div class="room-meta">'
               '<span>'+src_icon+' '+r.get('source_label','Camera')+'</span>'
               '<span>&#9679; '+_ts(r['created'])+'</span>'
               '</div></a>')
    if not cards:cards='<div class="no-rooms"><h3>Aucun stream en direct</h3><p>Soyez le premier a diffuser !</p></div>'
    b=('<div class="mc">'
       '<div class="hero">'
       '<h1>&#127909; StreamCaster</h1>'
       '<p>Streaming WebRTC temps reel — Camera, Ecran ou Carte de capture USB</p>'
       '<div class="hero-btns">'
       '<a href="/broadcast" class="btn btn-primary">&#128308; Commencer a diffuser</a>'
       '</div></div>'
       '<div class="rooms" id="rooms">'+cards+'</div>'
       '</div>')
    j='<script>var _io=io({transports:["polling","websocket"],upgrade:true});_io.on("rooms_update",function(){location.reload();});</script>'
    return _page('Accueil',b,j)

@app.route('/broadcast')
def broadcast_page():
    b=BROADCAST_HTML
    j='<script>'+BROADCAST_JS+'</script>'
    return _page('Diffuser',b,j)

@app.route('/watch/<rid>')
def watch_page(rid):
    with _lock:r=_rooms.get(rid)
    if not r:return redirect(url_for('index'))
    safe=r['title'].replace('\\','\\\\').replace('"','\\"')
    b=WATCH_HTML.replace('__TITLE__',r['title'])
    j='<script>var ROOM_ID="'+rid+'";var ROOM_TITLE="'+safe+'";'+WATCH_JS+'</script>'
    return _page(r['title'],b,j)

@app.route('/admin',methods=['GET','POST'])
def admin():
    err=''
    if request.method=='POST':
        if request.form.get('password','')==app.config['ADMIN_PASSWORD']:
            session['admin']=True;return redirect(url_for('admin'))
        err='<div class="fm">Mot de passe incorrect</div>'
    if not session.get('admin'):
        b='<div class="mc"><div class="lw"><div class="lc"><h2>&#9878; Admin</h2>'+err+'<form method="POST" action="/admin"><div class="fg"><label>Mot de passe</label><input type="password" name="password" class="fi" autofocus placeholder="••••••••"></div><button type="submit" class="btn btn-primary btn-full">Connexion</button></form></div></div></div>'
        return _page('Admin',b)
    with _lock:
        rl=list(_rooms.values())
        tv=sum(len(r['viewers']) for r in rl)
    rows=''
    for r in sorted(rl,key=lambda x:-x['created']):
        rid2=r['id'];vc=len(r['viewers'])
        rows+=('<div class="room-row">'
               '<span class="room-id">'+rid2+'</span>'
               '<span class="room-tname">'+r['title']+'</span>'
               '<span class="tag tag-viewers">'+str(vc)+'v</span>'
               '<a href="/watch/'+rid2+'" class="btn btn-secondary btn-sm" target="_blank">Voir</a>'
               '<form method="POST" action="/admin/kick/'+rid2+'" style="display:inline">'
               '<button type="submit" class="btn btn-danger btn-sm">Stop</button>'
               '</form></div>')
    if not rows:rows='<div class="em">Aucun stream actif</div>'
    b=('<div class="mc"><div class="adm-wrap">'
       '<div class="adm-top"><h1>&#9878; Dashboard Admin</h1><a href="/admin/logout" class="btn btn-secondary btn-sm">Deconnexion</a></div>'
       '<div class="stats-grid">'
       '<div class="sc"><div class="sv">'+str(len(rl))+'</div><div class="sl">Streams actifs</div></div>'
       '<div class="sc"><div class="sv">'+str(tv)+'</div><div class="sl">Viewers</div></div>'
       '<div class="sc"><div class="sv">'+str(_stats['rooms'])+'</div><div class="sl">Total streams</div></div>'
       '<div class="sc"><div class="sv">'+str(_stats['msgs'])+'</div><div class="sl">Messages</div></div>'
       '<div class="sc"><div class="sv" style="font-size:.95em;font-family:monospace">'+_up()+'</div><div class="sl">Uptime</div></div>'
       '</div>'
       '<div class="adm-sec"><h2>Streams</h2>'+rows+'</div>'
       '</div></div>')
    return _page('Dashboard Admin',b,head='<meta http-equiv="refresh" content="15">')

@app.route('/admin/logout')
def admin_logout():session.pop('admin',None);return redirect(url_for('index'))
@app.route('/admin/kick/<rid>',methods=['POST'])
def admin_kick(rid):
    if not session.get('admin'):return jsonify({'error':'non autorise'}),403
    socketio.emit('room_closed',{'reason':'Admin a ferme ce stream'},room=rid)
    with _lock:_rooms.pop(rid,None)
    socketio.emit('rooms_update',{})
    return redirect(url_for('admin'))
@app.route('/api/rooms')
def api_rooms():
    with _lock:return jsonify([{'id':r['id'],'title':r['title'],'viewers':len(r['viewers']),'source_label':r.get('source_label','')} for r in _rooms.values()])

@socketio.on('connect')
def on_connect():
    with _lock:_sids[request.sid]={'room_id':None,'role':None,'name':'Anonyme'}
@socketio.on('disconnect')
def on_disconnect():
    sid=request.sid
    with _lock:
        info=_sids.pop(sid,{})
        rid=info.get('room_id');role=info.get('role')
        if rid and rid in _rooms:
            room=_rooms[rid]
            if role=='host':
                del _rooms[rid]
                socketio.emit('room_closed',{'reason':'Le diffuseur a quitte'},room=rid)
                socketio.emit('rooms_update',{})
            elif role=='viewer':
                room['viewers'].discard(sid)
                socketio.emit('viewer_count',{'count':len(room['viewers'])},room=rid)
                socketio.emit('viewer_left',{'sid':sid},room=rid)

@socketio.on('create_room')
def on_create_room(data):
    if not isinstance(data,dict):return
    title=str(data.get('title','Mon Stream'))[:80]
    quality=str(data.get('quality','HD'))
    src_type=str(data.get('source_type','cam'))
    src_label=str(data.get('source_label','Camera'))
    rid=uuid.uuid4().hex[:8]
    with _lock:
        _rooms[rid]={'id':rid,'title':title,'quality':quality,
                     'source_type':src_type,'source_label':src_label,
                     'host_sid':request.sid,'viewers':set(),'chat':[],'created':time.time()}
        _sids[request.sid]={'room_id':rid,'role':'host','name':'Diffuseur'}
        _stats['rooms']+=1
    join_room(rid)
    emit('room_created',{'room_id':rid,'title':title})
    socketio.emit('rooms_update',{})

@socketio.on('join_room_viewer')
def on_join_viewer(data):
    if not isinstance(data,dict):return
    rid=data.get('room_id','');name=str(data.get('name','Anonyme'))[:30]
    with _lock:
        room=_rooms.get(rid)
        if not room:emit('error',{'msg':'Room introuvable'});return
        room['viewers'].add(request.sid)
        _sids[request.sid]={'room_id':rid,'role':'viewer','name':name}
        host_sid=room['host_sid'];vc=len(room['viewers']);ch=room['chat'][-50:]
    join_room(rid)
    emit('joined',{'room_id':rid,'title':room['title'],'chat':ch})
    socketio.emit('viewer_joined',{'viewer_sid':request.sid,'name':name},room=host_sid)
    socketio.emit('viewer_count',{'count':vc},room=rid)

@socketio.on('webrtc_offer')
def on_offer(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('webrtc_offer',{'sdp':data.get('sdp'),'from':request.sid},room=t)
@socketio.on('webrtc_answer')
def on_answer(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('webrtc_answer',{'sdp':data.get('sdp'),'from':request.sid},room=t)
@socketio.on('webrtc_ice')
def on_ice(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('webrtc_ice',{'candidate':data.get('candidate'),'from':request.sid},room=t)

@socketio.on('chat')
def on_chat(data):
    if not isinstance(data,dict):return
    with _lock:
        info=_sids.get(request.sid,{})
        rid=info.get('room_id');name=info.get('name','Anonyme')
        if not rid or rid not in _rooms:return
        text=str(data.get('text','')).strip()[:500]
        if not text:return
        msg={'name':name,'text':text,'ts':time.time(),'id':uuid.uuid4().hex[:6]}
        _rooms[rid]['chat'].append(msg)
        _rooms[rid]['chat']=_rooms[rid]['chat'][-200:]
        _stats['msgs']+=1
    socketio.emit('chat',msg,room=rid)

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    print('StreamCaster WebRTC http://0.0.0.0:'+str(port))
    socketio.run(app,host='0.0.0.0',port=port,debug=False,
        use_reloader=False,log_output=True,allow_unsafe_werkzeug=True)

BROADCAST_HTML=(
'<div class="mc"><div class="bc-page">'

'<div class="bc-preview">'
'<div class="bc-video-wrap">'
'<video id="preview" autoplay playsinline muted style="width:100%;height:100%;object-fit:contain;display:block;background:#000"></video>'
'<div class="bc-overlay" id="bc-ov">'
'<div class="bc-overlay-inner">'
'<div style="font-size:3em;margin-bottom:12px">&#127909;</div>'
'<p style="color:#6b6b8a;font-size:.9em">Selectionnez une source</p>'
'</div></div></div>'
'<div class="bc-status">'
'<div class="bc-status-dot" id="st-dot"></div>'
'<span id="st-txt" style="font-size:.88em;font-weight:600">Pret</span>'
'<div style="margin-left:auto" id="st-stats"></div>'
'</div></div>'

'<div class="bc-panel">'

'<div class="panel-card">'
'<h3>Source</h3>'
'<div class="src-tabs">'
'<button class="src-tab active" id="tab-cam" onclick="switchTab(event,&apos;cam&apos;)">&#127909; Camera</button>'
'<button class="src-tab" id="tab-capture" onclick="switchTab(event,&apos;capture&apos;)">&#127908; Capture USB</button>'
'<button class="src-tab" id="tab-screen" onclick="switchTab(event,&apos;screen&apos;)">&#128396; Ecran</button>'
'<button class="src-tab" id="tab-both" onclick="switchTab(event,&apos;both&apos;)">&#127909;+&#128396;</button>'
'</div>'

'<div id="panel-cam">'
'<div class="field"><label>Camera</label>'
'<div class="device-list" id="cam-list">'
'<div class="no-devices">Detection en cours...</div>'
'</div></div>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:6px" onclick="refreshDevices()">&#128260; Rafraichir</button>'
'</div>'

'<div id="panel-capture" style="display:none">'
'<div class="field"><label>Carte de capture USB</label>'
'<div class="device-list" id="capture-list">'
'<div class="no-devices">Detection en cours...</div>'
'</div></div>'
'<div style="font-size:.78em;color:var(--mu);margin-top:6px;padding:8px;background:var(--bi);border-radius:6px">'
'&#128161; Les cartes de capture USB (Elgato, AVerMedia...) apparaissent comme des cameras dans le navigateur.'
'</div>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:6px" onclick="refreshDevices()">&#128260; Rafraichir</button>'
'</div>'

'<div id="panel-screen" style="display:none">'
'<p style="font-size:.84em;color:var(--mu);margin-bottom:8px">Partage d ecran — capture tout ou une fenetre specifique.</p>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:4px" onclick="previewScreen()">&#128247; Previsualiser l ecran</button>'
'</div>'

'<div id="panel-both" style="display:none">'
'<p style="font-size:.84em;color:var(--mu);margin-bottom:8px">Ecran + microphone simultanement.</p>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:4px" onclick="previewBoth()">&#127909;+&#128396; Previsualiser</button>'
'</div>'

'</div>'

'<div class="panel-card">'
'<h3>Qualite</h3>'
'<div class="field"><label>Resolution</label>'
'<select class="sel" id="sel-res">'
'<option value="1920x1080">1080p Full HD</option>'
'<option value="1280x720" selected>720p HD</option>'
'<option value="854x480">480p</option>'
'<option value="640x360">360p</option>'
'</select></div>'
'<div class="field"><label>Bitrate video</label>'
'<select class="sel" id="sel-bw">'
'<option value="6000000">6 Mbps — Ultra (Jeux/Sport)</option>'
'<option value="4000000">4 Mbps — Tres haute qualite</option>'
'<option value="2500000" selected>2.5 Mbps — HD standard</option>'
'<option value="1000000">1 Mbps — Economique</option>'
'<option value="500000">500 kbps — Basse deb.</option>'
'</select></div>'
'<div class="field"><label>Audio</label>'
'<select class="sel" id="sel-aud">'
'<option value="true">Micro / Audio source</option>'
'<option value="false">Aucun audio</option>'
'</select></div>'
'</div>'

'<div class="panel-card">'
'<h3>Stream</h3>'
'<div class="field"><label>Titre du stream</label>'
'<input type="text" class="inp" id="inp-title" placeholder="Mon stream" maxlength="60" value="Mon Stream"></div>'
'<div id="btn-area">'
'<button class="btn btn-primary btn-full" id="btn-go" onclick="goLive()">&#128308; Demarrer le Stream</button>'
'</div>'
'<div id="share-area" style="display:none;margin-top:10px">'
'<p style="font-size:.78em;color:var(--mu);margin-bottom:5px">Lien spectateurs :</p>'
'<div class="share-box" id="share-link" onclick="copyLink()" title="Cliquer pour copier">...</div>'
'<p style="font-size:.73em;color:var(--mu);margin-top:4px">&#128203; Cliquez pour copier</p>'
'</div></div>'

'<div class="panel-card" id="bc-chat-panel" style="flex:1">'
'<h3 id="bc-ch-h">Chat (0 viewers)</h3>'
'<div style="max-height:180px;overflow-y:auto" id="bc-chat-msgs" class="chat-msgs"></div>'
'<div style="display:flex;gap:5px;margin-top:8px">'
'<input type="text" class="inp" id="bc-chat-in" placeholder="Message..." style="font-size:.84em">'
'<button class="btn btn-primary" style="padding:8px 12px" onclick="bcSend()">&#10148;</button>'
'</div></div>'

'</div></div></div>'
)
BROADCAST_JS=(
'var sock=io({transports:["polling","websocket"],upgrade:true});'
'var localStream=null,roomId=null,peers={},currentTab="cam",selectedDeviceId=null;'
'var allDevices=[];'

'// Detecter tous les peripheriques video'
'function refreshDevices(){'
'  // Demander permission dabord pour avoir les labels'
'  navigator.mediaDevices.getUserMedia({video:true,audio:false})'
'  .then(function(tmp){'
'    tmp.getTracks().forEach(function(t){t.stop();});'
'    return navigator.mediaDevices.enumerateDevices();'
'  }).then(function(devices){'
'    allDevices=devices.filter(function(d){return d.kind==="videoinput";});'
'    renderDevices();'
'  }).catch(function(){'
'    // Sans permission, essayer quand meme'
'    navigator.mediaDevices.enumerateDevices().then(function(devices){'
'      allDevices=devices.filter(function(d){return d.kind==="videoinput";});'
'      renderDevices();'
'    }).catch(function(e){toast("Acces devices: "+e.message,"err");});'
'  });'
'}'

'function renderDevices(){'
'  var camList=document.getElementById("cam-list");'
'  var capList=document.getElementById("capture-list");'
'  if(allDevices.length===0){'
'    var msg="<div class=\\"no-devices\\">Aucune camera detectee<br><small>Verifiez les permissions</small></div>";'
'    camList.innerHTML=msg;capList.innerHTML=msg;return;'
'  }'
'  var camHtml="",capHtml="";'
'  allDevices.forEach(function(d,i){'
'    var label=d.label||"Camera "+(i+1);'
'    var isCapture=(label.toLowerCase().indexOf("capture")>=0'
'      ||label.toLowerCase().indexOf("elgato")>=0'
'      ||label.toLowerCase().indexOf("avermedia")>=0'
'      ||label.toLowerCase().indexOf("hdmi")>=0'
'      ||label.toLowerCase().indexOf("game")>=0'
'      ||label.toLowerCase().indexOf("usb video")>=0'
'      ||label.toLowerCase().indexOf("live gamer")>=0'
'      ||label.toLowerCase().indexOf("4k60")>=0'
'      ||label.toLowerCase().indexOf("magewell")>=0'
'      ||label.toLowerCase().indexOf("blackmagic")>=0);'
'    var icon=isCapture?"&#127908;":"&#127909;";'
'    var type=isCapture?"Carte de capture USB":"Camera";'
'    var sel=(d.deviceId===selectedDeviceId)?" selected":"";'
'    var item="<div class=\\"device-item"+sel+"\\" onclick=\\"selectDevice("+JSON.stringify(d.deviceId)+","+JSON.stringify(label)+")\\">'
'       <span class=\\"device-icon\\">"+icon+"</span>'
'       <div class=\\"device-name\\">"+(d.label||\"Camera "+(i+1)+"\")+"</div>'
'       <div class=\\"device-check\\"></div>'
'       </div>";'
'    if(isCapture)capHtml+=item;'
'    camHtml+=item;'
'  });'
'  camList.innerHTML=camHtml||"<div class=\\"no-devices\\">Aucune camera</div>";'
'  capList.innerHTML=capHtml||"<div class=\\"no-devices\\">Aucune carte de capture detectee<br><small style=\\"font-size:.85em\\">Branchez votre carte USB et cliquez Rafraichir</small></div>";'
'}'

'function selectDevice(deviceId,label){'
'  selectedDeviceId=deviceId;'
'  document.querySelectorAll(".device-item").forEach(function(el){el.classList.remove("selected");});'
'  event.currentTarget.classList.add("selected");'
'  document.querySelector(".bc-status-dot").className="bc-status-dot ready";'
'  document.getElementById("st-txt").textContent="Selectionne: "+label;'
'  previewDevice(deviceId,label);'
'}'

'function previewDevice(deviceId,label){'
'  if(localStream){localStream.getTracks().forEach(function(t){t.stop();});}'
'  var res=document.getElementById("sel-res").value.split("x");'
'  var aud=document.getElementById("sel-aud").value==="true";'
'  var constraints={'
'    video:{deviceId:{exact:deviceId},width:{ideal:parseInt(res[0])},height:{ideal:parseInt(res[1])},frameRate:{ideal:30}},'
'    audio:aud'
'  };'
'  navigator.mediaDevices.getUserMedia(constraints)'
'  .then(function(s){'
'    setStream(s,label,"capture");'
'  }).catch(function(e){'
'    toast("Erreur device: "+e.message,"err");'
'  });'
'}'

'function switchTab(event,tab){'
'  currentTab=tab;'
'  document.querySelectorAll(".src-tab").forEach(function(b){b.classList.remove("active");});'
'  event.target.classList.add("active");'
'  ["cam","capture","screen","both"].forEach(function(t){'
'    var p=document.getElementById("panel-"+t);'
'    if(p)p.style.display=(t===tab?"block":"none");'
'  });'
'}'

'function getConstraints(){'
'  var res=document.getElementById("sel-res").value.split("x");'
'  var aud=document.getElementById("sel-aud").value==="true";'
'  var c={video:{width:{ideal:parseInt(res[0])},height:{ideal:parseInt(res[1])},frameRate:{ideal:30}},audio:aud};'
'  if(selectedDeviceId&&(currentTab==="cam"||currentTab==="capture"))c.video.deviceId={exact:selectedDeviceId};'
'  return c;'
'}'

'function previewScreen(){'
'  var aud=document.getElementById("sel-aud").value==="true";'
'  navigator.mediaDevices.getDisplayMedia({video:true,audio:aud})'
'  .then(function(s){setStream(s,"Ecran","screen");}).catch(function(e){toast("Ecran: "+e.message,"err");});'
'}'

'function previewBoth(){'
'  var aud=document.getElementById("sel-aud").value==="true";'
'  Promise.all(['
'    navigator.mediaDevices.getDisplayMedia({video:true}),'
'    navigator.mediaDevices.getUserMedia({video:false,audio:aud})'
'  ]).then(function(s){'
'    var c=new MediaStream();'
'    s[0].getVideoTracks().forEach(function(t){c.addTrack(t);});'
'    s[1].getAudioTracks().forEach(function(t){c.addTrack(t);});'
'    setStream(c,"Ecran+Micro","both");'
'  }).catch(function(e){toast("Erreur: "+e.message,"err");});'
'}'

'function setStream(stream,label,srcType){'
'  localStream=stream;'
'  document.getElementById("preview").srcObject=stream;'
'  document.getElementById("bc-ov").style.display="none";'
'  document.querySelector(".bc-status-dot").className="bc-status-dot ready";'
'  document.getElementById("st-txt").textContent=label+" — Pret";'
'  toast(label+" active !","ok");'
'  // Stocker label et type pour le stream'
'  window._srcLabel=label;window._srcType=srcType;'
'}'

'function goLive(){'
'  if(!localStream){'
'    if(currentTab==="cam"||currentTab==="capture"){'
'      navigator.mediaDevices.getUserMedia(getConstraints())'
'      .then(function(s){setStream(s,selectedDeviceId?"Capture USB":"Camera",currentTab);goLive();})'
'      .catch(function(e){toast("Erreur source: "+e.message,"err");});'
'      return;'
'    }else if(currentTab==="screen"){previewScreen();return;}'
'    else if(currentTab==="both"){previewBoth();return;}'
'    toast("Selectionnez une source !","err");return;'
'  }'
'  var title=document.getElementById("inp-title").value.trim()||"Mon Stream";'
'  var bw=parseInt(document.getElementById("sel-bw").value);'
'  var ql=bw>=5000000?"Ultra":bw>=3000000?"Tres haute":bw>=2000000?"HD":bw>=800000?"Moyen":"Bas";'
'  sock.emit("create_room",{title:title,quality:ql,bitrate:bw,'
'    source_type:window._srcType||currentTab,'
'    source_label:window._srcLabel||"Source"});'
'}'

'sock.on("room_created",function(d){'
'  roomId=d.room_id;'
'  document.getElementById("btn-area").innerHTML='
'    "<button class=\\"btn btn-danger btn-full\\" onclick=\\"stopLive()\\">&#9632; Arreter le Stream</button>";'
'  var lnk=window.location.origin+"/watch/"+roomId;'
'  document.getElementById("share-area").style.display="block";'
'  document.getElementById("share-link").textContent=lnk;'
'  document.querySelector(".bc-status-dot").className="bc-status-dot live";'
'  document.getElementById("st-txt").textContent="EN DIRECT — "+d.title;'
'  toast("Stream demarre !","ok");'
'});'

'function copyLink(){'
'  var lnk=window.location.origin+"/watch/"+roomId;'
'  navigator.clipboard.writeText(lnk).then(function(){toast("Lien copie !","ok");}).catch(function(){});'
'}'

'sock.on("viewer_joined",function(d){'
'  createPeerHost(d.viewer_sid);'
'  toast("Nouveau viewer: "+d.name,"info");'
'});'
'sock.on("viewer_left",function(d){'
'  if(peers[d.sid]){peers[d.sid].close();delete peers[d.sid];}});'
'sock.on("viewer_count",function(d){'
'  var h=document.getElementById("bc-ch-h");'
'  if(h)h.textContent="Chat ("+d.count+" viewer"+(d.count>1?"s":"")+")";'
'  var ss=document.getElementById("st-stats");'
'  ss.innerHTML="<span class=\\"tag tag-viewers\\">&#128065; "+d.count+"</span>";'
'});'

'function getICE(){return [{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}];}'
'function getBW(){return parseInt(document.getElementById("sel-bw").value);}'

'async function createPeerHost(vsid){'
'  var pc2=new RTCPeerConnection({iceServers:getICE()});'
'  peers[vsid]=pc2;'
'  localStream.getTracks().forEach(function(t){pc2.addTrack(t,localStream);});'
'  pc2.onicecandidate=function(e){if(e.candidate)sock.emit("webrtc_ice",{target:vsid,candidate:e.candidate});};'
'  pc2.onconnectionstatechange=function(){'
'    if(pc2.connectionState==="failed"||pc2.connectionState==="disconnected"){'
'      pc2.close();delete peers[vsid];}};'
'  try{'
'    var offer=await pc2.createOffer();'
'    var sdp=offer.sdp.replace(/b=AS:\d+/g,"b=AS:"+(getBW()/1000|0));'
'    await pc2.setLocalDescription({type:"offer",sdp:sdp});'
'    sock.emit("webrtc_offer",{target:vsid,sdp:pc2.localDescription});'
'  }catch(e){toast("Offer: "+e.message,"err");}'
'}'
'sock.on("webrtc_answer",async function(d){'
'  var pc2=peers[d.from];if(!pc2)return;'
'  try{await pc2.setRemoteDescription(new RTCSessionDescription(d.sdp));}catch(e){}});'
'sock.on("webrtc_ice",async function(d){'
'  var pc2=peers[d.from];if(!pc2)return;'
'  try{await pc2.addIceCandidate(new RTCIceCandidate(d.candidate));}catch(e){}});'

'function stopLive(){'
'  Object.keys(peers).forEach(function(s){peers[s].close();});peers={};'
'  if(localStream){localStream.getTracks().forEach(function(t){t.stop();});localStream=null;}'
'  location.reload();'
'}'

'sock.on("chat",function(m){'
'  var c=document.getElementById("bc-chat-msgs");if(!c)return;'
'  var d=document.createElement("div");d.className="chat-msg chat-new";'
'  d.innerHTML="<span class=\\"chat-user\\">"+esc(m.name)+"</span><span class=\\"chat-text\\">"+esc(m.text)+"</span>";'
'  c.appendChild(d);c.scrollTop=c.scrollHeight;'
'  while(c.children.length>100)c.removeChild(c.firstChild);'
'});'
'function bcSend(){'
'  var inp=document.getElementById("bc-chat-in");var t=inp.value.trim();if(!t)return;'
'  sock.emit("chat",{text:t});inp.value="";'
'}'
'document.getElementById("bc-chat-in").addEventListener("keypress",function(e){if(e.key==="Enter")bcSend();});'
'// Lancer la detection au chargement'
'refreshDevices();'
)
WATCH_HTML=(
'<div class="watch-page">'
'<div class="watch-main">'
'<div class="watch-video-wrap" id="wvw">'
'<video id="wv" autoplay playsinline style="width:100%;height:100%;object-fit:contain;background:#000;display:block"></video>'
'<div class="vc-overlay" id="wov">'
'<div class="vc-inner"><div class="spinner"></div>'
'<p id="wot">Connexion au stream...</p>'
'<p id="wot2" style="font-size:.8em;margin-top:4px;opacity:.5">WebRTC P2P...</p>'
'</div></div>'
'<div class="unmute-btn" id="wub"><button onclick="doUnmute()">&#128266; Activer le son</button></div>'
'<div class="ctrl-bar" id="wctrl">'
'<div class="ctrl-progress">'
'<span class="ctrl-live">LIVE</span>'
'<span class="ctrl-lat" id="wlat"></span>'
'</div>'
'<div class="ctrl-btns">'
'<div class="ctrl-l">'
'<button class="cb3" id="wbpl"><svg viewBox="0 0 24 24"><path id="wplp" d="M6 4l15 8-15 8V4z"/></svg></button>'
'<button class="cb3" id="wbmu"><svg viewBox="0 0 24 24"><path id="wmup" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></button>'
'<div class="vol-wrap"><input type="range" id="wvol" min="0" max="1" step="0.02" value="1"></div>'
'<span class="ctrl-time">LIVE</span>'
'</div>'
'<div class="ctrl-r">'
'<button class="cb3 big" id="wbfs">'
'<svg viewBox="0 0 24 24" id="wice"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>'
'<svg viewBox="0 0 24 24" id="wicc" style="display:none"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>'
'</button>'
'</div></div></div>'
'</div>'
'<div class="watch-meta">'
'<div style="display:flex;align-items:center;gap:8px">'
'<div class="rdot"></div>'
'<span style="font-weight:700;font-size:.95em">__TITLE__</span>'
'</div>'
'<span id="wvc" class="tag tag-viewers">0 viewers</span>'
'</div></div>'
'<div class="watch-sidebar">'
'<div class="sidebar-head"><h3>&#128172; Chat en direct</h3>'
'<div class="nr"><label class="sw"><input type="checkbox" id="wntog" checked><span class="sl"></span></label><span style="color:var(--mu);font-size:.8em">Notif</span></div>'
'</div>'
'<div class="chat-msgs" id="wcm"></div>'
'<div class="chat-inp-area">'
'<input type="text" class="chat-name" id="wun" placeholder="Pseudo..." maxlength="20">'
'<div class="chat-row">'
'<input type="text" class="chat-in" id="wci" placeholder="Message..." maxlength="500" autocomplete="off">'
'<button class="chat-send" id="wcs">&#10148;</button>'
'</div></div></div>'
'</div>'
'<audio id="wns" preload="auto"><source src="/static/sounds/notification.wav" type="audio/wav"></audio>'
)
WATCH_JS=(
'var sock=io({transports:["polling","websocket"],upgrade:true});'
'var pc=null,ht=null,fsm=false;'
'var wv=document.getElementById("wv"),wvw=document.getElementById("wvw");'
'var wov=document.getElementById("wov"),wot=document.getElementById("wot");'
'var wctrl=document.getElementById("wctrl");'
'var wbpl=document.getElementById("wbpl"),wplp=document.getElementById("wplp");'
'var wbmu=document.getElementById("wbmu"),wmup=document.getElementById("wmup");'
'var wvol=document.getElementById("wvol");'
'var wbfs=document.getElementById("wbfs"),wice=document.getElementById("wice"),wicc=document.getElementById("wicc");'
'var wub=document.getElementById("wub"),wlat=document.getElementById("wlat");'
'var wcm=document.getElementById("wcm"),wci=document.getElementById("wci");'
'var wcs=document.getElementById("wcs"),wun=document.getElementById("wun");'
'var wntog=document.getElementById("wntog"),wns=document.getElementById("wns");'
'var wvc=document.getElementById("wvc");'
'var IPL="M6 4l15 8-15 8V4z",IPA="M6 19h4V5H6v14zm8-14v14h4V5h-4z";'
'var IVO="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z";'
'var IMU="M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06A8.99 8.99 0 0 0 17.73 19l2 2L21 19.73l-18-18z";'
'function getICE(){return [{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}];}'
'function doUnmute(){wv.muted=false;wv.volume=1;wmup.setAttribute("d",IVO);wvol.value=1;wub.style.display="none";}'
'function hideOv(){wov.style.opacity="0";setTimeout(function(){wov.style.display="none";},400);}'
'function showOv(m){wot.textContent=m;wov.style.display="flex";wov.style.opacity="1";}'
'wun.value=localStorage.getItem("sc_name")||"";'
'sock.on("connect",function(){'
'  sock.emit("join_room_viewer",{room_id:ROOM_ID,name:wun.value.trim()||"Anonyme"});'
'});'
'sock.on("joined",function(d){'
'  d.chat.forEach(function(m){addMsg(m,false);});wcm.scrollTop=wcm.scrollHeight;'
'});'
'sock.on("webrtc_offer",async function(d){'
'  if(pc){pc.close();pc=null;}'
'  pc=new RTCPeerConnection({iceServers:getICE()});'
'  pc.ontrack=function(e){'
'    if(e.streams&&e.streams[0]){'
'      wv.srcObject=e.streams[0];'
'      wv.muted=false;wv.volume=1;'
'      wv.play().then(function(){'
'        hideOv();wub.style.display="none";wmup.setAttribute("d",IVO);wvol.value=1;'
'      }).catch(function(){'
'        wv.muted=true;wv.play().catch(function(){});'
'        hideOv();wub.style.display="flex";wmup.setAttribute("d",IMU);wvol.value=0;'
'      });'
'    }'
'  };'
'  pc.onicecandidate=function(e){'
'    if(e.candidate)sock.emit("webrtc_ice",{target:d.from,candidate:e.candidate});'
'  };'
'  pc.onconnectionstatechange=function(){'
'    if(pc.connectionState==="connected"){wlat.textContent="< 500ms";}'
'    else if(pc.connectionState==="failed"){'
'      showOv("Connexion perdue...");setTimeout(function(){location.reload();},3000);}'
'  };'
'  try{'
'    await pc.setRemoteDescription(new RTCSessionDescription(d.sdp));'
'    var ans=await pc.createAnswer();'
'    await pc.setLocalDescription(ans);'
'    sock.emit("webrtc_answer",{target:d.from,sdp:pc.localDescription});'
'  }catch(e){toast("WebRTC: "+e.message,"err");}'
'  setInterval(function(){'
'    if(!pc)return;'
'    pc.getStats().then(function(s){'
'      s.forEach(function(r){'
'        if(r.type==="inbound-rtp"&&r.kind==="video"&&r.jitter!==undefined){'
'          var ms=Math.round(r.jitter*1000+r.roundTripTime*500||0);'
'          wlat.textContent=ms<50?"ultra-low":ms<200?"low":ms+"ms";}'
'      });}).catch(function(){});'
'  },4000);'
'});'
'sock.on("webrtc_ice",async function(d){'
'  if(!pc)return;try{await pc.addIceCandidate(new RTCIceCandidate(d.candidate));}catch(e){}});'
'sock.on("room_closed",function(d){'
'  if(pc){pc.close();pc=null;}wv.srcObject=null;'
'  showOv(d.reason||"Stream termine");'
'  setTimeout(function(){location.href="/";},3000);'
'});'
'sock.on("viewer_count",function(d){wvc.textContent=d.count+" viewer"+(d.count>1?"s":"");});'
'sock.on("chat",function(m){'
'  addMsg(m,true);'
'  if(wntog.checked&&m.name!==(wun.value.trim()||"Anonyme"))pN(m.name,m.text);'
'});'
'sock.on("connect_error",function(e){showOv("Erreur: "+e.message);});'
'function addMsg(m,an){'
'  var d=document.createElement("div");d.className="chat-msg"+(an?" chat-new":"");'
'  var t=new Date(m.ts*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});'
'  d.innerHTML="<span class=\\"chat-time\\">"+t+"</span><span class=\\"chat-user\\">"+esc(m.name)+"</span><span class=\\"chat-text\\">"+esc(m.text)+"</span>";'
'  wcm.appendChild(d);wcm.scrollTop=wcm.scrollHeight;'
'  while(wcm.children.length>200)wcm.removeChild(wcm.firstChild);'
'}'
'function sendMsg(){'
'  var t=wci.value.trim();if(!t)return;'
'  var n=wun.value.trim()||"Anonyme";localStorage.setItem("sc_name",n);wun.value=n;'
'  sock.emit("chat",{text:t});wci.value="";'
'}'
'wcs.onclick=sendMsg;wci.addEventListener("keypress",function(e){if(e.key==="Enter")sendMsg();});'
'wbpl.onclick=function(){wv.paused?wv.play():wv.pause();};'
'wv.addEventListener("play",function(){wplp.setAttribute("d",IPA);});'
'wv.addEventListener("pause",function(){wplp.setAttribute("d",IPL);});'
'wv.addEventListener("dblclick",tFS);'
'wbmu.onclick=function(){wv.muted=!wv.muted;wmup.setAttribute("d",wv.muted?IMU:IVO);wvol.value=wv.muted?0:Math.max(wv.volume,0.1);if(!wv.muted)wub.style.display="none";};'
'wvol.oninput=function(){wv.volume=parseFloat(wvol.value);wv.muted=(wv.volume===0);wmup.setAttribute("d",wv.muted?IMU:IVO);if(!wv.muted)wub.style.display="none";};'
'function tFS(){if(!document.fullscreenElement&&!document.webkitFullscreenElement)eFS();else xFS();}'
'function eFS(){var fn=wvw.requestFullscreen||wvw.webkitRequestFullscreen||wvw.mozRequestFullScreen||wvw.msRequestFullscreen;if(fn)fn.call(wvw);}'
'function xFS(){var fn=document.exitFullscreen||document.webkitExitFullscreen||document.mozCancelFullScreen||document.msExitFullscreen;if(fn)fn.call(document);}'
'function onFC(){'
'  fsm=!!(document.fullscreenElement||document.webkitFullscreenElement);'
'  if(fsm){document.body.classList.add("fs");wvw.classList.add("fa");wice.style.display="none";wicc.style.display="block";sH();}'
'  else{document.body.classList.remove("fs");wvw.classList.remove("fa");wice.style.display="block";wicc.style.display="none";wctrl.classList.remove("hidden");document.body.style.cursor="";cH();}'
'}'
'["fullscreenchange","webkitfullscreenchange","mozfullscreenchange","MSFullscreenChange"].forEach(function(ev){document.addEventListener(ev,onFC);});'
'wbfs.onclick=tFS;'
'function sH(){cH();wctrl.classList.remove("hidden");document.body.style.cursor="";ht=setTimeout(function(){if(fsm){wctrl.classList.add("hidden");document.body.style.cursor="none";}},3000);}'
'function cH(){if(ht){clearTimeout(ht);ht=null;}}'
'wvw.addEventListener("mousemove",function(){if(fsm)sH();});'
'wctrl.addEventListener("mouseenter",function(){cH();wctrl.classList.remove("hidden");document.body.style.cursor="";});'
'wctrl.addEventListener("mouseleave",function(){if(fsm)sH();});'
'document.addEventListener("keydown",function(e){'
'  var tg=document.activeElement.tagName;if(tg==="INPUT"||tg==="TEXTAREA")return;'
'  if(e.key==="f"||e.key==="F"){e.preventDefault();tFS();}'
'  else if(e.key===" "||e.key==="k"||e.key==="K"){e.preventDefault();wv.paused?wv.play():wv.pause();}'
'  else if(e.key==="m"||e.key==="M"){e.preventDefault();wbmu.onclick();}'
'  else if(e.key==="ArrowUp"){e.preventDefault();wv.volume=Math.min(1,wv.volume+0.1);wvol.value=wv.volume;}'
'  else if(e.key==="ArrowDown"){e.preventDefault();wv.volume=Math.max(0,wv.volume-0.1);wvol.value=wv.volume;}'
'  else if(e.key==="Escape"&&fsm){e.preventDefault();xFS();}'
'});'
'function pN(u,t){'
'  try{wns.currentTime=0;wns.play().catch(function(){});}catch(e){}'
'  if("Notification"in window&&Notification.permission==="granted")'
'    new Notification("Message de "+u,{body:t,silent:true});'
'}'
'if("Notification"in window&&Notification.permission==="default")Notification.requestPermission();'
)