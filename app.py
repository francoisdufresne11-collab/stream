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

_CSS='*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}\n:root{--b1:#0a0a14;--b2:#12121f;--b3:#1a1a2e;--bi:#070710;--ac:#a78bfa;--a2:#7c3aed;\n--gn:#10b981;--rd:#ef4444;--bl:#3b82f6;--tx:#e8e8f0;--mu:#6b6b8a;--bo:#2a2a4a;--ch:#0d0d1f}\nhtml,body{height:100%;margin:0;padding:0}\nbody{font-family:"Segoe UI",system-ui,sans-serif;background:var(--b1);color:var(--tx);min-height:100vh}\na{color:var(--ac);text-decoration:none}a:hover{color:#c4b5fd}\n@keyframes pl{0%,100%{opacity:1}50%{opacity:.3}}\n@keyframes sp{to{transform:rotate(360deg)}}\n@keyframes fi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}\n@keyframes pu{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}\n.nb{display:flex;align-items:center;justify-content:space-between;padding:0 28px;\nbackground:rgba(18,18,31,.96);backdrop-filter:blur(20px);\nborder-bottom:1px solid rgba(167,139,250,.12);position:sticky;top:0;z-index:200;height:58px}\n.logo{font-size:1.2em;font-weight:900;color:var(--ac)!important;text-decoration:none;display:flex;align-items:center;gap:8px}\n.logo-dot{width:10px;height:10px;background:var(--rd);border-radius:50%;animation:pl 2s infinite}\n.nl{display:flex;gap:6px}\n.nl a{color:var(--mu);font-size:.85em;text-decoration:none;padding:6px 14px;border-radius:20px;transition:.2s;border:1px solid transparent;font-weight:500}\n.nl a:hover{color:var(--ac);border-color:rgba(167,139,250,.3);background:rgba(167,139,250,.08)}\n.mc{max-width:1400px;margin:0 auto;padding:24px}\n.hero{text-align:center;padding:50px 20px 36px}\n.hero h1{font-size:2.6em;font-weight:900;background:linear-gradient(135deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}\n.hero p{color:var(--mu);font-size:1em;margin-bottom:28px}\n.hero-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}\n.rooms{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:28px}\n.room-card{background:var(--b3);border-radius:14px;border:1px solid var(--bo);padding:18px;display:block;color:var(--tx);transition:all .2s;text-decoration:none}\n.room-card:hover{border-color:var(--ac);box-shadow:0 6px 30px rgba(167,139,250,.12);transform:translateY(-2px)}\n.rdot{width:8px;height:8px;background:var(--rd);border-radius:50%;animation:pl 1.5s infinite}\n.room-live{display:flex;align-items:center;gap:8px;margin-bottom:10px}\n.room-title{font-size:1.05em;font-weight:700;margin-bottom:5px}\n.room-meta{color:var(--mu);font-size:.82em;display:flex;gap:14px}\n.no-rooms{grid-column:1/-1;text-align:center;padding:50px 20px;color:var(--mu)}\n.no-rooms h3{color:var(--tx);margin-bottom:6px}\n.bc-page{display:grid;grid-template-columns:1fr 420px;gap:18px;height:calc(100vh - 106px);min-height:500px}\n.bc-preview{background:#000;border-radius:14px;overflow:hidden;display:flex;flex-direction:column}\n.bc-video-wrap{flex:1;position:relative;background:#000;min-height:200px}\n.bc-video-wrap video{width:100%;height:100%;object-fit:contain;display:block;position:absolute;inset:0}\n.bc-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.75);z-index:2}\n.bc-status{padding:12px 18px;background:rgba(18,18,31,.92);display:flex;align-items:center;gap:10px;flex-shrink:0;min-height:46px}\n.bc-status-dot{width:10px;height:10px;border-radius:50%;background:var(--mu);transition:.3s;flex-shrink:0}\n.bc-status-dot.live{background:var(--rd);animation:pl 1.5s infinite}\n.bc-status-dot.ready{background:var(--gn)}\n.bc-panel{display:flex;flex-direction:column;gap:12px;overflow-y:auto;padding-right:2px}\n.panel-card{background:var(--b3);border-radius:12px;border:1px solid var(--bo);padding:16px;flex-shrink:0}\n.panel-card h3{font-size:.8em;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}\n.src-tabs{display:flex;gap:3px;margin-bottom:12px;background:var(--bi);border-radius:8px;padding:3px}\n.src-tab{flex:1;padding:7px 4px;border:none;background:transparent;color:var(--mu);border-radius:6px;cursor:pointer;font-size:.78em;font-weight:600;transition:.2s;text-align:center}\n.src-tab.active{background:var(--a2);color:#fff}\n.src-tab:hover:not(.active){background:rgba(255,255,255,.06);color:var(--tx)}\n.src-panel{display:none}\n.src-panel.show{display:block}\n.device-list{display:flex;flex-direction:column;gap:5px;max-height:160px;overflow-y:auto}\n.device-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;border:1px solid var(--bo);cursor:pointer;transition:.2s}\n.device-item:hover{border-color:rgba(167,139,250,.4);background:rgba(167,139,250,.05)}\n.device-item.selected{border-color:var(--ac);background:rgba(167,139,250,.1)}\n.device-icon{font-size:1.2em;flex-shrink:0;width:24px;text-align:center}\n.device-name{flex:1;font-size:.82em;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n.device-check{width:14px;height:14px;border-radius:50%;border:2px solid var(--bo);flex-shrink:0;transition:.2s}\n.device-item.selected .device-check{background:var(--ac);border-color:var(--ac)}\n.no-dev{text-align:center;color:var(--mu);font-size:.82em;padding:14px}\n/* AUDIO DEVICE SECTION */\n.audio-section{margin-top:10px;padding-top:10px;border-top:1px solid var(--bo)}\n.audio-section .audio-lbl{font-size:.78em;color:var(--mu);margin-bottom:6px;display:flex;align-items:center;gap:6px}\n.audio-badge{background:rgba(16,185,129,.15);color:var(--gn);border:1px solid rgba(16,185,129,.3);padding:2px 8px;border-radius:10px;font-size:.72em;font-weight:700}\n.audio-badge.warn{background:rgba(245,158,11,.15);color:var(--yw);border-color:rgba(245,158,11,.3)}\n.field{margin-bottom:10px}\n.field label{display:block;font-size:.78em;color:var(--mu);margin-bottom:4px}\n.inp{width:100%;padding:9px 11px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:.88em;outline:none;transition:.2s}\n.inp:focus{border-color:var(--ac)}\n.sel{width:100%;padding:9px 11px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:.88em;outline:none;cursor:pointer}\n.sel:focus{border-color:var(--ac)}\n.share-box{background:var(--bi);border:1px solid rgba(167,139,250,.28);border-radius:9px;padding:10px 14px;font-family:monospace;font-size:.78em;color:var(--ac);word-break:break-all;cursor:pointer;transition:.2s}\n.share-box:hover{border-color:var(--ac)}\n/* AUDIO METER */\n.audio-meter-wrap{display:flex;align-items:center;gap:8px;margin-top:6px}\n.audio-meter-lbl{font-size:.75em;color:var(--mu);white-space:nowrap}\n.audio-meter{flex:1;height:6px;background:var(--bo);border-radius:3px;overflow:hidden}\n.audio-meter-bar{height:100%;background:var(--gn);border-radius:3px;width:0%;transition:width .1s}\n/* WATCH */\n.watch-page{display:flex;height:calc(100vh - 58px);overflow:hidden}\n.watch-main{flex:1;display:flex;flex-direction:column;min-width:0;background:#000}\n.watch-vw{flex:1;position:relative;background:#000;overflow:hidden;min-height:0}\n.watch-vw video{width:100%;height:100%;object-fit:contain;display:block;background:#000}\n.watch-meta{padding:9px 16px;background:var(--b2);border-top:1px solid var(--bo);flex-shrink:0;display:flex;align-items:center;justify-content:space-between}\n.watch-sidebar{width:350px;min-width:300px;display:flex;flex-direction:column;background:var(--ch);border-left:1px solid var(--bo)}\n.sb-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--b2);border-bottom:1px solid var(--bo);flex-shrink:0}\n.sb-head h3{font-size:.88em;font-weight:700}\n.chat-msgs{flex:1;overflow-y:auto;padding:8px 12px;display:flex;flex-direction:column;gap:3px;scrollbar-width:thin;scrollbar-color:var(--bo) transparent}\n.chat-msg{padding:4px 7px;border-radius:7px;font-size:.84em;line-height:1.5;word-break:break-word}\n.chat-msg:hover{background:rgba(255,255,255,.03)}\n.chat-new{animation:fi .3s ease}\n.chat-time{color:var(--mu);font-size:.72em;margin-right:4px}\n.chat-user{color:var(--ac);font-weight:700;margin-right:4px}\n.chat-text{color:var(--tx)}\n.chat-sys{text-align:center;color:var(--mu);font-size:.74em;padding:3px;font-style:italic}\n.chat-ia{padding:9px 12px;border-top:1px solid var(--bo);background:var(--b2);flex-shrink:0}\n.chat-name{width:100%;padding:6px 10px;margin-bottom:5px;background:var(--bi);color:var(--ac);border:1px solid var(--bo);border-radius:7px;font-size:.82em;font-weight:600;outline:none}\n.chat-name:focus{border-color:var(--ac)}\n.chat-row{display:flex;gap:5px}\n.chat-in{flex:1;padding:8px 10px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:.86em;outline:none}\n.chat-in:focus{border-color:var(--ac)}\n.chat-send{width:40px;background:var(--a2);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:1.05em;transition:.2s}\n.chat-send:hover{background:var(--ac)}\n.vc-ov{position:absolute;inset:0;z-index:10;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;transition:opacity .4s}\n.vc-in{text-align:center;padding:24px}\n.spinner{width:48px;height:48px;border:4px solid var(--bo);border-top-color:var(--ac);border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 14px}\n.vc-ov p{color:var(--mu);font-size:.9em;margin-bottom:4px}\n.ctrl-bar{position:absolute;bottom:0;left:0;right:0;z-index:30;background:linear-gradient(transparent,rgba(0,0,0,.95) 50%);padding:36px 14px 10px;transition:opacity .3s,transform .3s}\n.ctrl-bar.hidden{opacity:0;transform:translateY(100%);pointer-events:none}\n.ctrl-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}\n.ctrl-live{background:var(--rd);color:#fff;font-size:.67em;font-weight:800;padding:3px 8px;border-radius:4px;animation:pl 2s infinite}\n.ctrl-lat{color:var(--gn);font-size:.7em;font-family:monospace;padding:2px 7px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.2);border-radius:4px}\n.ctrl-btns{display:flex;align-items:center;justify-content:space-between;gap:6px}\n.cl,.cr{display:flex;align-items:center;gap:5px}\n.cb{background:none;border:none;cursor:pointer;width:34px;height:34px;display:flex;align-items:center;justify-content:center;color:#fff;border-radius:7px;transition:background .2s;padding:4px;flex-shrink:0}\n.cb:hover{background:rgba(255,255,255,.15)}\n.cb svg{width:19px;height:19px;fill:currentColor}\n.cb.big svg{width:21px;height:21px}\n.vol-wrap{width:76px;display:flex;align-items:center}\ninput[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:4px;background:rgba(255,255,255,.25);border-radius:2px;outline:none;cursor:pointer}\ninput[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:13px;height:13px;border-radius:50%;background:var(--ac);cursor:pointer}\ninput[type=range]::-moz-range-thumb{width:13px;height:13px;border-radius:50%;background:var(--ac);border:none;cursor:pointer}\n.unmute-btn{position:absolute;bottom:70px;left:50%;transform:translateX(-50%);z-index:20;display:none;align-items:center}\n.unmute-btn button{background:linear-gradient(135deg,var(--a2),#4f46e5);color:#fff;border:none;border-radius:50px;padding:12px 26px;font-size:.92em;font-weight:700;cursor:pointer;box-shadow:0 4px 20px rgba(124,58,237,.4);animation:pu 2s infinite}\n.watch-vw.fa{position:fixed!important;inset:0!important;z-index:9999!important;width:100vw!important;height:100vh!important;background:#000!important}\n.watch-vw.fa video{width:100%!important;height:100%!important;object-fit:contain!important}\nbody.fs .nb,body.fs .watch-meta,body.fs .watch-sidebar{display:none!important}\n.watch-vw:-webkit-full-screen{background:#000}\n.watch-vw:fullscreen{background:#000}\n.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 20px;border-radius:50px;font-weight:700;font-size:.88em;border:none;cursor:pointer;transition:all .2s;text-decoration:none}\n.btn-primary{background:linear-gradient(135deg,var(--a2),#4f46e5);color:#fff;box-shadow:0 4px 14px rgba(124,58,237,.3)}\n.btn-primary:hover{background:linear-gradient(135deg,var(--ac),#818cf8);color:#fff}\n.btn-secondary{background:rgba(255,255,255,.07);color:var(--tx);border:1px solid var(--bo)}\n.btn-secondary:hover{background:rgba(255,255,255,.11);border-color:var(--ac)}\n.btn-danger{background:rgba(239,68,68,.14);color:var(--rd);border:1px solid rgba(239,68,68,.3)}\n.btn-danger:hover{background:var(--rd);color:#fff}\n.btn-sm{padding:6px 14px;font-size:.8em}\n.btn-full{width:100%;justify-content:center}\n.tag{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:20px;font-size:.76em;font-weight:700}\n.tag-live{background:rgba(239,68,68,.14);color:var(--rd);border:1px solid rgba(239,68,68,.28)}\n.tag-v{background:rgba(167,139,250,.1);color:var(--ac);border:1px solid rgba(167,139,250,.2)}\n.tag-ok{background:rgba(16,185,129,.14);color:var(--gn);border:1px solid rgba(16,185,129,.28)}\n.toast{position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:7px}\n.toast-msg{background:var(--b3);border:1px solid var(--bo);border-radius:10px;padding:11px 16px;font-size:.86em;animation:fi .3s ease;box-shadow:0 8px 30px rgba(0,0,0,.5);max-width:300px}\n.toast-ok{border-color:rgba(16,185,129,.4);color:var(--gn)}\n.toast-err{border-color:rgba(239,68,68,.4);color:var(--rd)}\n.toast-info{border-color:rgba(167,139,250,.3);color:var(--ac)}\n.adm-wrap{max-width:1100px;margin:0 auto}\n.adm-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}\n.adm-top h1{font-size:1.4em;font-weight:900}\n.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:20px}\n.sc{background:var(--b3);border:1px solid var(--bo);border-radius:11px;padding:16px;text-align:center}\n.sc .sv{font-size:1.7em;font-weight:900;color:var(--ac);line-height:1}\n.sc .sl{color:var(--mu);font-size:.78em;margin-top:3px}\n.adm-sec{background:var(--b3);border:1px solid var(--bo);border-radius:11px;padding:18px;margin-bottom:14px}\n.adm-sec h2{font-size:.82em;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}\n.room-row{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--bo)}\n.room-row:last-child{border:none}\n.room-id{font-family:monospace;font-size:.78em;color:var(--mu);background:var(--bi);padding:2px 7px;border-radius:4px}\n.room-tn{flex:1;font-weight:600;font-size:.9em}\n.em{text-align:center;color:var(--mu);padding:20px;font-size:.88em}\n.lw{display:flex;align-items:center;justify-content:center;min-height:60vh}\n.lc{background:var(--b3);border:1px solid var(--bo);border-radius:16px;padding:38px;width:100%;max-width:370px}\n.lc h2{margin-bottom:22px;text-align:center;color:var(--ac);font-size:1.2em}\n.fg{margin-bottom:12px}\n.fg label{display:block;margin-bottom:4px;color:var(--mu);font-size:.8em}\n.fi{width:100%;padding:9px 12px;background:var(--bi);color:var(--tx);border:1px solid var(--bo);border-radius:8px;font-size:.88em;outline:none}\n.fi:focus{border-color:var(--ac)}\n.fm{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:8px 12px;color:var(--rd);font-size:.83em;margin-bottom:12px}\n.nr{display:flex;align-items:center;gap:6px;font-size:.82em}\n.sw{position:relative;display:inline-block;width:32px;height:17px}\n.sw input{opacity:0;width:0;height:0}\n.sl{position:absolute;inset:0;cursor:pointer;background:var(--bo);border-radius:17px;transition:.3s}\n.sl::before{content:"";position:absolute;height:11px;width:11px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}\ninput:checked+.sl{background:var(--gn)}\ninput:checked+.sl::before{transform:translateX(15px)}\n@media(max-width:1000px){.bc-page{grid-template-columns:1fr;height:auto}.watch-page{flex-direction:column}.watch-sidebar{width:100%;min-width:0;height:320px}}\n@media(max-width:600px){.hero h1{font-size:1.7em}}'
_SIO='https://cdn.socket.io/4.7.5/socket.io.min.js'

def _page(title,body,js='',head=''):
    return ('<!DOCTYPE html><html lang="fr"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+title+' - StreamCaster</title>'
            '<style>'+_CSS+'</style>'
            '<script src="'+_SIO+'"></script>'
            +head+
            '</head><body>'
            '<nav class="nb"><a href="/" class="logo"><span class="logo-dot"></span>StreamCaster</a>'
            '<div class="nl"><a href="/">Accueil</a><a href="/broadcast">Diffuser</a><a href="/admin">Admin</a></div></nav>'
            '<div class="toast" id="_t"></div>'
            +body+
            '<script>'
            'function toast(m,t){var d=document.createElement("div");d.className="toast-msg toast-"+(t||"info");d.textContent=m;var c=document.getElementById("_t");if(c){c.appendChild(d);setTimeout(function(){if(d.parentNode)d.remove();},3500);}}'
            'function esc(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}'
            '</script>'+js+'</body></html>')

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
        icons={'cam':'&#127909;','capture':'&#127908;','screen':'&#128396;','both':'&#127909;&#128396;'}
        icon=icons.get(r.get('source_type','cam'),'&#127909;')
        has_audio=r.get('has_audio',True)
        audio_tag='' if has_audio else '<span class="tag" style="background:rgba(245,158,11,.14);color:#f59e0b;border:1px solid rgba(245,158,11,.28)">Muet</span>'
        cards+=('<a href="/watch/'+rid+'" class="room-card">'
               '<div class="room-live"><div class="rdot"></div>'
               '<span class="tag tag-live">LIVE</span>'
               '<span class="tag tag-v">&#128065; '+str(vc)+'</span>'
               +audio_tag+
               '</div>'
               '<div class="room-title">'+r['title']+'</div>'
               '<div class="room-meta">'
               '<span>'+icon+' '+r.get('source_label','Camera')+'</span>'
               '<span>&#9679; '+_ts(r['created'])+'</span>'
               '</div></a>')
    if not cards:cards='<div class="no-rooms"><h3>Aucun stream en direct</h3><p style="margin-top:6px">Soyez le premier a diffuser !</p></div>'
    b=('<div class="mc"><div class="hero">'
       '<h1>&#127909; StreamCaster</h1>'
       '<p>Streaming WebRTC temps reel — Camera, Ecran ou Carte de capture USB</p>'
       '<div class="hero-btns"><a href="/broadcast" class="btn btn-primary">&#128308; Commencer a diffuser</a></div>'
       '</div><div class="rooms" id="rooms">'+cards+'</div></div>')
    j='<script>var _io=io({transports:["polling","websocket"],upgrade:true});_io.on("rooms_update",function(){location.reload();});</script>'
    return _page('Accueil',b,j)

@app.route('/broadcast')
def broadcast_page():
    return _page('Diffuser',BC_HTML,'<script>'+BC_JS+'</script>')

@app.route('/watch/<rid>')
def watch_page(rid):
    with _lock:r=_rooms.get(rid)
    if not r:return redirect(url_for('index'))
    safe=r['title'].replace('\\','\\\\').replace('"','\\"')
    has_audio='true' if r.get('has_audio',True) else 'false'
    b=WA_HTML.replace('__TITLE__',r['title'])
    j='<script>var ROOM_ID="'+rid+'";var ROOM_TITLE="'+safe+'";var ROOM_HAS_AUDIO='+has_audio+';'+WA_JS+'</script>'
    return _page(r['title'],b,j)

@app.route('/admin',methods=['GET','POST'])
def admin():
    err=''
    if request.method=='POST':
        if request.form.get('password','')==app.config['ADMIN_PASSWORD']:
            session['admin']=True;return redirect(url_for('admin'))
        err='<div class="fm">Mot de passe incorrect</div>'
    if not session.get('admin'):
        b='<div class="mc"><div class="lw"><div class="lc"><h2>Admin</h2>'+err+'<form method="POST" action="/admin"><div class="fg"><label>Mot de passe</label><input type="password" name="password" class="fi" autofocus placeholder="..."></div><button type="submit" class="btn btn-primary btn-full">Connexion</button></form></div></div></div>'
        return _page('Admin',b)
    with _lock:rl=list(_rooms.values());tv=sum(len(r['viewers']) for r in rl)
    rows=''
    for r in sorted(rl,key=lambda x:-x['created']):
        rid2=r['id'];vc=len(r['viewers'])
        rows+=('<div class="room-row">'
               '<span class="room-id">'+rid2+'</span>'
               '<span class="room-tn">'+r['title']+'</span>'
               '<span class="tag tag-v">'+str(vc)+'v</span>'
               '<a href="/watch/'+rid2+'" class="btn btn-secondary btn-sm" target="_blank">Voir</a>'
               '<form method="POST" action="/admin/kick/'+rid2+'" style="display:inline">'
               '<button type="submit" class="btn btn-danger btn-sm">Stop</button></form></div>')
    if not rows:rows='<div class="em">Aucun stream actif</div>'
    b=('<div class="mc"><div class="adm-wrap">'
       '<div class="adm-top"><h1>Dashboard Admin</h1><a href="/admin/logout" class="btn btn-secondary btn-sm">Deconnexion</a></div>'
       '<div class="stats-grid">'
       '<div class="sc"><div class="sv">'+str(len(rl))+'</div><div class="sl">Streams actifs</div></div>'
       '<div class="sc"><div class="sv">'+str(tv)+'</div><div class="sl">Viewers</div></div>'
       '<div class="sc"><div class="sv">'+str(_stats['rooms'])+'</div><div class="sl">Total streams</div></div>'
       '<div class="sc"><div class="sv">'+str(_stats['msgs'])+'</div><div class="sl">Messages</div></div>'
       '<div class="sc"><div class="sv" style="font-size:.9em;font-family:monospace">'+_up()+'</div><div class="sl">Uptime</div></div>'
       '</div><div class="adm-sec"><h2>Streams</h2>'+rows+'</div>'
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
    with _lock:return jsonify([{'id':r['id'],'title':r['title'],'viewers':len(r['viewers']),'has_audio':r.get('has_audio',True)} for r in _rooms.values()])

@socketio.on('connect')
def on_conn():
    with _lock:_sids[request.sid]={'room_id':None,'role':None,'name':'Anonyme'}
@socketio.on('disconnect')
def on_disc():
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
def on_create(data):
    if not isinstance(data,dict):return
    title=str(data.get('title','Mon Stream'))[:80]
    quality=str(data.get('quality','HD'))
    src_type=str(data.get('source_type','cam'))
    src_label=str(data.get('source_label','Camera'))
    has_audio=bool(data.get('has_audio',True))
    rid=uuid.uuid4().hex[:8]
    with _lock:
        _rooms[rid]={'id':rid,'title':title,'quality':quality,
                     'source_type':src_type,'source_label':src_label,
                     'has_audio':has_audio,
                     'host_sid':request.sid,'viewers':set(),'chat':[],'created':time.time()}
        _sids[request.sid]={'room_id':rid,'role':'host','name':'Diffuseur'}
        _stats['rooms']+=1
    join_room(rid)
    emit('room_created',{'room_id':rid,'title':title,'has_audio':has_audio})
    socketio.emit('rooms_update',{})
@socketio.on('join_viewer')
def on_join_v(data):
    if not isinstance(data,dict):return
    rid=data.get('room_id','');name=str(data.get('name','Anonyme'))[:30]
    with _lock:
        room=_rooms.get(rid)
        if not room:emit('error_msg',{'msg':'Room introuvable'});return
        room['viewers'].add(request.sid)
        _sids[request.sid]={'room_id':rid,'role':'viewer','name':name}
        host_sid=room['host_sid'];vc=len(room['viewers']);ch=room['chat'][-50:]
    join_room(rid)
    emit('joined',{'room_id':rid,'title':room['title'],'chat':ch,'has_audio':room.get('has_audio',True)})
    socketio.emit('viewer_joined',{'viewer_sid':request.sid,'name':name},room=host_sid)
    socketio.emit('viewer_count',{'count':vc},room=rid)
@socketio.on('rtc_offer')
def on_offer(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('rtc_offer',{'sdp':data.get('sdp'),'from':request.sid},room=t)
@socketio.on('rtc_answer')
def on_answer(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('rtc_answer',{'sdp':data.get('sdp'),'from':request.sid},room=t)
@socketio.on('rtc_ice')
def on_ice(data):
    if not isinstance(data,dict):return
    t=data.get('target')
    if t:emit('rtc_ice',{'candidate':data.get('candidate'),'from':request.sid},room=t)
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
    print('StreamCaster http://0.0.0.0:'+str(port))
    socketio.run(app,host='0.0.0.0',port=port,debug=False,
        use_reloader=False,log_output=True,allow_unsafe_werkzeug=True)

BC_HTML=(
'<div class="mc"><div class="bc-page">'
'<div class="bc-preview">'
'<div class="bc-video-wrap" style="min-height:300px">'
'<video id="pv" autoplay playsinline muted></video>'
'<div class="bc-overlay" id="bc-ov">'
'<div style="text-align:center"><div style="font-size:3em;margin-bottom:10px">&#127909;</div>'
'<p style="color:#6b6b8a;font-size:.9em">Selectionnez une source</p>'
'</div></div></div>'
'<div class="bc-status">'
'<div class="bc-status-dot" id="st-dot"></div>'
'<span id="st-txt" style="font-size:.88em;font-weight:600">Pret</span>'
'<div style="margin-left:auto;display:flex;gap:6px;align-items:center" id="st-stats"></div>'
'</div></div>'
'<div class="bc-panel">'
'<div class="panel-card">'
'<h3>Source</h3>'
'<div class="src-tabs" id="src-tabs">'
'<button class="src-tab active" data-tab="cam">&#127909; Camera</button>'
'<button class="src-tab" data-tab="capture">&#127908; Capture USB</button>'
'<button class="src-tab" data-tab="screen">&#128396; Ecran</button>'
'<button class="src-tab" data-tab="both">Ecran+Cam</button>'
'</div>'
'<div class="src-panel show" id="panel-cam">'
'<div class="field"><label>Camera</label>'
'<div class="device-list" id="cam-list"><div class="no-dev">Detection...</div></div></div>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:6px" id="btn-ref1">&#128260; Rafraichir</button>'
'</div>'
'<div class="src-panel" id="panel-capture">'
# VIDEO device
'<div class="field"><label>Carte de capture (video)</label>'
'<div class="device-list" id="cap-list"><div class="no-dev">Detection...</div></div></div>'
# AUDIO device pour capture — C'EST LE FIX PRINCIPAL
'<div class="audio-section">'
'<div class="audio-lbl">&#127925; Source audio de la carte de capture'
'<span class="audio-badge" id="cap-audio-badge">A selectionner</span>'
'</div>'
'<div class="device-list" id="cap-audio-list" style="max-height:120px"><div class="no-dev">Detection...</div></div>'
'<div style="font-size:.75em;color:var(--mu);margin-top:6px;padding:7px;background:var(--bi);border-radius:6px">'
'&#128161; Selectionnez l entree audio de votre carte de capture pour que les spectateurs entendent le son.'
'</div>'
'</div>'
'<div class="audio-meter-wrap" id="cap-meter-wrap" style="display:none">'
'<span class="audio-meter-lbl">&#127925; Niveau :</span>'
'<div class="audio-meter"><div class="audio-meter-bar" id="cap-meter-bar"></div></div>'
'</div>'
'<button class="btn btn-secondary btn-sm" style="width:100%;margin-top:8px" id="btn-ref2">&#128260; Rafraichir les appareils</button>'
'</div>'
'<div class="src-panel" id="panel-screen">'
'<p style="font-size:.84em;color:var(--mu);margin-bottom:10px">Capture d ecran entier ou d une fenetre.</p>'
'<p style="font-size:.76em;color:var(--gn);margin-bottom:8px">&#10003; L audio systeme peut etre inclus lors du partage d ecran.</p>'
'<button class="btn btn-secondary btn-sm btn-full" id="btn-screen">&#128247; Previsualiser l ecran</button>'
'</div>'
'<div class="src-panel" id="panel-both">'
'<p style="font-size:.84em;color:var(--mu);margin-bottom:10px">Ecran + microphone simultanement.</p>'
'<button class="btn btn-secondary btn-sm btn-full" id="btn-both">&#127909; Previsualiser les deux</button>'
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
'<option value="6000000">6 Mbps - Ultra</option>'
'<option value="4000000">4 Mbps - Tres haute qualite</option>'
'<option value="2500000" selected>2.5 Mbps - HD standard</option>'
'<option value="1000000">1 Mbps - Economique</option>'
'<option value="500000">500 kbps - Basse debit</option>'
'</select></div>'
'<div class="field" id="cam-audio-field">'
'<label>Audio (camera/ecran)</label>'
'<select class="sel" id="sel-aud">'
'<option value="true">Micro / Audio source active</option>'
'<option value="false">Aucun audio</option>'
'</select></div>'
'</div>'
'<div class="panel-card">'
'<h3>Stream</h3>'
'<div class="field"><label>Titre</label>'
'<input type="text" class="inp" id="inp-title" placeholder="Mon Stream" maxlength="60" value="Mon Stream"></div>'
'<div id="btn-area">'
'<button class="btn btn-primary btn-full" id="btn-go">&#128308; Demarrer le Stream</button>'
'</div>'
'<div id="share-area" style="display:none;margin-top:10px">'
'<p style="font-size:.76em;color:var(--mu);margin-bottom:5px">Lien spectateurs :</p>'
'<div class="share-box" id="share-lnk" title="Cliquer pour copier">...</div>'
'<p style="font-size:.72em;color:var(--mu);margin-top:4px">&#128203; Cliquez pour copier</p>'
'</div></div>'
'<div class="panel-card" style="flex:1">'
'<h3 id="bc-ch-h">Chat (0 viewers)</h3>'
'<div id="bc-chat" class="chat-msgs" style="max-height:140px"></div>'
'<div style="display:flex;gap:5px;margin-top:8px">'
'<input type="text" class="inp" id="bc-ci" placeholder="Message..." style="font-size:.84em">'
'<button class="btn btn-primary" style="padding:8px 12px" id="bc-cs">&#10148;</button>'
'</div></div>'
'</div></div></div>'
)
BC_JS='\nvar sock=io({transports:["polling","websocket"],upgrade:true});\nvar localStream=null,roomId=null,peers={};\nvar currentTab="cam",selectedVideoId=null,selectedVideoLabel="";\nvar selectedAudioId=null,selectedAudioLabel="";\nvar allVideoDevices=[],allAudioDevices=[];\nvar audioContext=null,analyser=null,meterInterval=null;\n\n// ── TABS ─────────────────────────────────────\ndocument.getElementById("src-tabs").addEventListener("click",function(e){\n  var btn=e.target.closest(".src-tab");\n  if(!btn)return;\n  var tab=btn.getAttribute("data-tab");\n  currentTab=tab;\n  document.querySelectorAll(".src-tab").forEach(function(b){b.classList.remove("active");});\n  btn.classList.add("active");\n  document.querySelectorAll(".src-panel").forEach(function(p){p.classList.remove("show");});\n  var panel=document.getElementById("panel-"+tab);\n  if(panel)panel.classList.add("show");\n  // Afficher/cacher le champ audio generique\n  var camAF=document.getElementById("cam-audio-field");\n  if(camAF)camAF.style.display=(tab==="capture"?"none":"block");\n});\n\n// ── ENUMERER TOUS LES APPAREILS ───────────────\nfunction refreshDevices(){\n  // Demander permission video ET audio pour avoir les labels\n  navigator.mediaDevices.getUserMedia({video:true,audio:true})\n  .then(function(tmp){\n    tmp.getTracks().forEach(function(t){t.stop();});\n    return navigator.mediaDevices.enumerateDevices();\n  }).then(function(devices){\n    allVideoDevices=devices.filter(function(d){return d.kind==="videoinput";});\n    allAudioDevices=devices.filter(function(d){return d.kind==="audioinput";});\n    renderVideoDevices();\n    renderAudioDevices();\n  }).catch(function(){\n    navigator.mediaDevices.enumerateDevices().then(function(devices){\n      allVideoDevices=devices.filter(function(d){return d.kind==="videoinput";});\n      allAudioDevices=devices.filter(function(d){return d.kind==="audioinput";});\n      renderVideoDevices();\n      renderAudioDevices();\n    }).catch(function(e){toast("Permission refusee: "+e.message,"err");});\n  });\n}\n\nfunction isCapture(label){\n  var lc=(label||"").toLowerCase();\n  return lc.indexOf("capture")>=0||lc.indexOf("elgato")>=0||\n    lc.indexOf("avermedia")>=0||lc.indexOf("hdmi")>=0||\n    lc.indexOf("game")>=0||lc.indexOf("usb video")>=0||\n    lc.indexOf("live gamer")>=0||lc.indexOf("4k60")>=0||\n    lc.indexOf("magewell")>=0||lc.indexOf("blackmagic")>=0||\n    lc.indexOf("cam link")>=0;\n}\n\nfunction renderVideoDevices(){\n  var camHtml="",capHtml="";\n  if(!allVideoDevices.length){\n    var nd="<div class=\\"no-dev\\">Aucun appareil video detecte</div>";\n    document.getElementById("cam-list").innerHTML=nd;\n    document.getElementById("cap-list").innerHTML=nd;\n    return;\n  }\n  allVideoDevices.forEach(function(d,i){\n    var label=d.label||("Camera "+(i+1));\n    var cap=isCapture(label);\n    var icon=cap?"&#127908;":"&#127909;";\n    var sel=(d.deviceId===selectedVideoId)?" selected":"";\n    var did=JSON.stringify(d.deviceId),dlbl=JSON.stringify(label);\n    var item=(\n      "<div class=\\"device-item"+sel+"\\" onclick=\\"selectVideo("+did+","+dlbl+")\\">"\n      +"<span class=\\"device-icon\\">"+icon+"</span>"\n      +"<span class=\\"device-name\\">"+label+"</span>"\n      +"<span class=\\"device-check\\"></span></div>"\n    );\n    camHtml+=item;\n    if(cap)capHtml+=item;\n  });\n  document.getElementById("cam-list").innerHTML=camHtml||"<div class=\\"no-dev\\">Aucune camera</div>";\n  document.getElementById("cap-list").innerHTML=capHtml||\n    "<div class=\\"no-dev\\">Aucune carte detectee<br><small>Branchez votre carte et rafraichissez</small></div>";\n}\n\n// ── AUDIO DEVICES — crucial pour la carte de capture ──\nfunction renderAudioDevices(){\n  var capAudioHtml="";\n  if(!allAudioDevices.length){\n    document.getElementById("cap-audio-list").innerHTML=\n      "<div class=\\"no-dev\\">Aucune entree audio detectee</div>";\n    return;\n  }\n  // Trier : d\'abord les entrees de capture, puis les autres\n  var capAudios=[];\n  var otherAudios=[];\n  allAudioDevices.forEach(function(d,i){\n    var label=d.label||("Entree audio "+(i+1));\n    var cap=isCapture(label)||label.toLowerCase().indexOf("analog")>=0||\n      label.toLowerCase().indexOf("digital")>=0;\n    if(cap)capAudios.push({d:d,label:label});\n    else otherAudios.push({d:d,label:label});\n  });\n  // Mettre les audios de capture en premier\n  var sorted=capAudios.concat(otherAudios);\n  sorted.forEach(function(item,i){\n    var d=item.d,label=item.label;\n    var cap=isCapture(label)||capAudios.indexOf(item)>=0;\n    var icon=cap?"&#127908;":"&#127897;";\n    var sel=(d.deviceId===selectedAudioId)?" selected":"";\n    var did=JSON.stringify(d.deviceId),dlbl=JSON.stringify(label);\n    capAudioHtml+=(\n      "<div class=\\"device-item"+sel+"\\" onclick=\\"selectAudio("+did+","+dlbl+")\\">"\n      +"<span class=\\"device-icon\\">"+icon+"</span>"\n      +"<span class=\\"device-name\\">"+label+"</span>"\n      +"<span class=\\"device-check\\"></span></div>"\n    );\n    // Auto-selectionner le premier audio de capture\n    if(i===0&&!selectedAudioId){\n      selectedAudioId=d.deviceId;selectedAudioLabel=label;\n    }\n  });\n  document.getElementById("cap-audio-list").innerHTML=capAudioHtml;\n  updateAudioBadge();\n}\n\nfunction selectVideo(deviceId,label){\n  selectedVideoId=deviceId;selectedVideoLabel=label;\n  document.querySelectorAll("#cap-list .device-item,#cam-list .device-item").forEach(function(el){el.classList.remove("selected");});\n  event.currentTarget.classList.add("selected");\n  // Auto-chercher l audio correspondant\n  autoMatchAudio(label);\n  previewCapture(deviceId,label);\n}\n\nfunction selectAudio(deviceId,label){\n  selectedAudioId=deviceId;selectedAudioLabel=label;\n  document.querySelectorAll("#cap-audio-list .device-item").forEach(function(el){el.classList.remove("selected");});\n  event.currentTarget.classList.add("selected");\n  updateAudioBadge();\n  toast("Audio: "+label,"ok");\n  // Re-previsualiser avec le bon audio\n  if(selectedVideoId&&localStream){\n    previewCapture(selectedVideoId,selectedVideoLabel);\n  }\n}\n\nfunction autoMatchAudio(videoLabel){\n  // Chercher une entree audio avec un nom similaire\n  var vl=videoLabel.toLowerCase();\n  var matched=null;\n  allAudioDevices.forEach(function(d,i){\n    var al=(d.label||"").toLowerCase();\n    // Chercher correspondance par fabricant\n    if(vl.indexOf("elgato")>=0&&al.indexOf("elgato")>=0){matched=d;}\n    else if(vl.indexOf("avermedia")>=0&&al.indexOf("avermedia")>=0){matched=d;}\n    else if(vl.indexOf("magewell")>=0&&al.indexOf("magewell")>=0){matched=d;}\n    else if(vl.indexOf("blackmagic")>=0&&al.indexOf("blackmagic")>=0){matched=d;}\n    else if(al.indexOf("hdmi")>=0&&vl.indexOf("hdmi")>=0){matched=d;}\n    else if(al.indexOf("capture")>=0&&!matched){matched=d;}\n  });\n  if(matched){\n    selectedAudioId=matched.deviceId;\n    selectedAudioLabel=matched.label||"Audio capture";\n    // Mettre a jour l UI\n    document.querySelectorAll("#cap-audio-list .device-item").forEach(function(el,i){\n      el.classList.toggle("selected",allAudioDevices[i]&&allAudioDevices[i].deviceId===matched.deviceId);\n    });\n    // Forcer re-render\n    renderAudioDevices();\n    // Re-selectionner dans la liste\n    setTimeout(function(){\n      var items=document.querySelectorAll("#cap-audio-list .device-item");\n      items.forEach(function(el){\n        if(el.textContent.indexOf(selectedAudioLabel)>=0){el.classList.add("selected");}\n      });\n    },50);\n    updateAudioBadge();\n    toast("Audio auto: "+selectedAudioLabel,"info");\n  }\n}\n\nfunction updateAudioBadge(){\n  var badge=document.getElementById("cap-audio-badge");\n  if(!badge)return;\n  if(selectedAudioId){\n    badge.textContent=selectedAudioLabel||"Selectionne";\n    badge.className="audio-badge";\n  }else{\n    badge.textContent="Non selectionne";\n    badge.className="audio-badge warn";\n  }\n}\n\n// ── PREVISUALISATION CAPTURE ────────────────────\nfunction previewCapture(videoId,label){\n  if(localStream){localStream.getTracks().forEach(function(t){t.stop();});stopAudioMeter();}\n  var res=document.getElementById("sel-res").value.split("x");\n  // IMPORTANT: inclure l audio de la carte de capture\n  var audioConstraint=false;\n  if(selectedAudioId){\n    audioConstraint={deviceId:{exact:selectedAudioId},echoCancellation:false,noiseSuppression:false,autoGainControl:false};\n  }\n  var c={\n    video:{deviceId:{exact:videoId},width:{ideal:parseInt(res[0])},height:{ideal:parseInt(res[1])},frameRate:{ideal:30}},\n    audio:audioConstraint\n  };\n  navigator.mediaDevices.getUserMedia(c)\n  .then(function(s){\n    setStream(s,label,"capture");\n    // Verifier si on a vraiment de l audio\n    var audioTracks=s.getAudioTracks();\n    if(audioTracks.length>0){\n      toast("Video + Audio OK: "+audioTracks[0].label,"ok");\n      startAudioMeter(s);\n    }else{\n      toast("Video OK, mais pas d audio. Selectionnez une entree audio.","info");\n    }\n  }).catch(function(e){\n    toast("Erreur: "+e.message,"err");\n    // Reessayer sans audio specifique\n    if(selectedAudioId){\n      toast("Retry sans audio specifique...","info");\n      navigator.mediaDevices.getUserMedia({\n        video:{deviceId:{exact:videoId},width:{ideal:parseInt(res[0])},height:{ideal:parseInt(res[1])}},\n        audio:true\n      }).then(function(s){setStream(s,label,"capture");}).catch(function(){});\n    }\n  });\n}\n\n// ── AUDIO METER (niveau audio visible) ────────\nfunction startAudioMeter(stream){\n  stopAudioMeter();\n  var wrap=document.getElementById("cap-meter-wrap");\n  if(wrap)wrap.style.display="flex";\n  try{\n    audioContext=new(window.AudioContext||window.webkitAudioContext)();\n    var src=audioContext.createMediaStreamSource(stream);\n    analyser=audioContext.createAnalyser();\n    analyser.fftSize=256;\n    src.connect(analyser);\n    var data=new Uint8Array(analyser.frequencyBinCount);\n    var bar=document.getElementById("cap-meter-bar");\n    meterInterval=setInterval(function(){\n      analyser.getByteFrequencyData(data);\n      var sum=0;for(var i=0;i<data.length;i++)sum+=data[i];\n      var avg=sum/data.length;var pct=Math.min(100,(avg/128)*100);\n      if(bar)bar.style.width=pct+"%";\n      if(bar)bar.style.background=pct>60?"var(--rd)":pct>30?"var(--yw)":"var(--gn)";\n    },100);\n  }catch(e){}\n}\n\nfunction stopAudioMeter(){\n  if(meterInterval){clearInterval(meterInterval);meterInterval=null;}\n  if(audioContext){try{audioContext.close();}catch(e){} audioContext=null;}\n  var wrap=document.getElementById("cap-meter-wrap");\n  if(wrap)wrap.style.display="none";\n}\n\n// ── STREAM SETUP ─────────────────────────────────\nfunction setStream(stream,label,srcType){\n  localStream=stream;\n  document.getElementById("pv").srcObject=stream;\n  document.getElementById("bc-ov").style.display="none";\n  document.querySelector(".bc-status-dot").className="bc-status-dot ready";\n  var audioTracks=stream.getAudioTracks();\n  var audioInfo=audioTracks.length>0?"+ son":"(sans son)";\n  document.getElementById("st-txt").textContent=label+" "+audioInfo+" - Pret";\n  window._srcLabel=label;window._srcType=srcType;\n  window._hasAudio=(audioTracks.length>0);\n  toast(label+": "+audioTracks.length+" piste(s) audio","ok");\n}\n\nfunction getConstraints(){\n  var res=document.getElementById("sel-res").value.split("x");\n  var aud=document.getElementById("sel-aud").value==="true";\n  var c={video:{width:{ideal:parseInt(res[0])},height:{ideal:parseInt(res[1])},frameRate:{ideal:30}},audio:aud};\n  if(selectedVideoId&&(currentTab==="cam"||currentTab==="capture")){\n    c.video.deviceId={exact:selectedVideoId};\n  }\n  if(currentTab==="capture"&&selectedAudioId){\n    c.audio={deviceId:{exact:selectedAudioId},echoCancellation:false,noiseSuppression:false,autoGainControl:false};\n  }\n  return c;\n}\n\n// ── ECRAN / BOTH ──────────────────────────────────\ndocument.getElementById("btn-screen").addEventListener("click",function(){\n  var aud=document.getElementById("sel-aud").value==="true";\n  navigator.mediaDevices.getDisplayMedia({video:true,audio:aud})\n  .then(function(s){setStream(s,"Ecran","screen");})\n  .catch(function(e){toast("Ecran: "+e.message,"err");});\n});\n\ndocument.getElementById("btn-both").addEventListener("click",function(){\n  var aud=document.getElementById("sel-aud").value==="true";\n  Promise.all([\n    navigator.mediaDevices.getDisplayMedia({video:true}),\n    navigator.mediaDevices.getUserMedia({video:false,audio:aud})\n  ]).then(function(s){\n    var c=new MediaStream();\n    s[0].getVideoTracks().forEach(function(t){c.addTrack(t);});\n    s[1].getAudioTracks().forEach(function(t){c.addTrack(t);});\n    setStream(c,"Ecran+Cam","both");\n  }).catch(function(e){toast("Erreur: "+e.message,"err");});\n});\n\n// ── GO LIVE ───────────────────────────────────────\ndocument.getElementById("btn-go").addEventListener("click",function(){\n  if(!localStream){\n    if(currentTab==="capture"&&selectedVideoId){\n      previewCapture(selectedVideoId,selectedVideoLabel||"Capture USB");\n      setTimeout(function(){if(localStream)startStream();},1500);\n    }else if(currentTab==="cam"){\n      navigator.mediaDevices.getUserMedia(getConstraints())\n      .then(function(s){setStream(s,selectedVideoLabel||"Camera","cam");startStream();})\n      .catch(function(e){toast("Erreur source: "+e.message,"err");});\n    }else if(currentTab==="screen"){\n      document.getElementById("btn-screen").click();\n      setTimeout(startStream,1000);\n    }else if(currentTab==="both"){\n      document.getElementById("btn-both").click();\n      setTimeout(startStream,1000);\n    }else{\n      toast("Selectionnez une source !","err");\n    }\n    return;\n  }\n  startStream();\n});\n\nfunction startStream(){\n  if(!localStream){toast("Pas de source !","err");return;}\n  var title=document.getElementById("inp-title").value.trim()||"Mon Stream";\n  var bw=parseInt(document.getElementById("sel-bw").value);\n  var ql=bw>=5000000?"Ultra":bw>=3000000?"Tres haute":bw>=2000000?"HD":bw>=800000?"Moyen":"Bas";\n  var hasAudio=(localStream.getAudioTracks().length>0);\n  sock.emit("create_room",{\n    title:title,quality:ql,bitrate:bw,\n    source_type:window._srcType||currentTab,\n    source_label:window._srcLabel||"Source",\n    has_audio:hasAudio\n  });\n}\n\nsock.on("room_created",function(d){\n  roomId=d.room_id;\n  document.getElementById("btn-area").innerHTML=\n    "<button class=\\"btn btn-danger btn-full\\" id=\\"btn-stop\\">&#9632; Arreter le Stream</button>";\n  document.getElementById("btn-stop").addEventListener("click",stopLive);\n  var lnk=window.location.origin+"/watch/"+roomId;\n  document.getElementById("share-area").style.display="block";\n  document.getElementById("share-lnk").textContent=lnk;\n  document.getElementById("share-lnk").onclick=function(){\n    navigator.clipboard.writeText(lnk).then(function(){toast("Lien copie !","ok");}).catch(function(){});\n  };\n  document.querySelector(".bc-status-dot").className="bc-status-dot live";\n  var hasAud=d.has_audio;\n  document.getElementById("st-txt").textContent="EN DIRECT - "+d.title+(hasAud?"":" (MUET)");\n  if(!hasAud){\n    document.getElementById("st-stats").innerHTML=\n      "<span class=\\"tag\\" style=\\"background:rgba(245,158,11,.14);color:#f59e0b;border-color:rgba(245,158,11,.3)\\">Muet</span>";\n  }\n  toast("Stream demarre !"+(hasAud?"":" (pas d audio)"),"ok");\n});\n\n// ── WEBRTC HOST ────────────────────────────────────\nsock.on("viewer_joined",function(d){createPeer(d.viewer_sid);toast("Viewer: "+d.name,"info");});\nsock.on("viewer_left",function(d){if(peers[d.sid]){peers[d.sid].close();delete peers[d.sid];}});\nsock.on("viewer_count",function(d){\n  var h=document.getElementById("bc-ch-h");\n  if(h)h.textContent="Chat ("+d.count+" viewer"+(d.count>1?"s":"")+")";\n  var ss=document.getElementById("st-stats");\n  if(ss&&!document.querySelector(".bc-status-dot.live")){\n    ss.innerHTML="<span class=\\"tag tag-v\\">&#128065; "+d.count+"</span>";\n  }\n});\n\nfunction getICE(){return [{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}];}\nfunction getBW(){return parseInt(document.getElementById("sel-bw").value||2500000);}\n\nasync function createPeer(vsid){\n  var pc=new RTCPeerConnection({iceServers:getICE()});\n  peers[vsid]=pc;\n  if(localStream){\n    localStream.getTracks().forEach(function(t){\n      pc.addTrack(t,localStream);\n    });\n  }\n  pc.onicecandidate=function(e){if(e.candidate)sock.emit("rtc_ice",{target:vsid,candidate:e.candidate});};\n  pc.onconnectionstatechange=function(){\n    if(pc.connectionState==="failed"||pc.connectionState==="disconnected"){pc.close();delete peers[vsid];}\n  };\n  try{\n    var offer=await pc.createOffer();\n    var sdp=offer.sdp.replace(/b=AS:\\d+/g,"b=AS:"+(getBW()/1000|0));\n    await pc.setLocalDescription({type:"offer",sdp:sdp});\n    sock.emit("rtc_offer",{target:vsid,sdp:pc.localDescription});\n  }catch(e){toast("Offer: "+e.message,"err");}\n}\n\nsock.on("rtc_answer",async function(d){\n  var pc=peers[d.from];if(!pc)return;\n  try{await pc.setRemoteDescription(new RTCSessionDescription(d.sdp));}catch(e){}\n});\nsock.on("rtc_ice",async function(d){\n  var pc=peers[d.from];if(!pc)return;\n  try{await pc.addIceCandidate(new RTCIceCandidate(d.candidate));}catch(e){}\n});\n\nfunction stopLive(){\n  stopAudioMeter();\n  Object.keys(peers).forEach(function(s){peers[s].close();});peers={};\n  if(localStream){localStream.getTracks().forEach(function(t){t.stop();});localStream=null;}\n  location.reload();\n}\n\n// ── CHAT HOST ──────────────────────────────────────\nsock.on("chat",function(m){\n  var c=document.getElementById("bc-chat");if(!c)return;\n  var d=document.createElement("div");d.className="chat-msg chat-new";\n  d.innerHTML="<span class=\\"chat-user\\">"+esc(m.name)+"</span><span class=\\"chat-text\\">"+esc(m.text)+"</span>";\n  c.appendChild(d);c.scrollTop=c.scrollHeight;\n  while(c.children.length>100)c.removeChild(c.firstChild);\n});\ndocument.getElementById("bc-cs").addEventListener("click",function(){\n  var inp=document.getElementById("bc-ci");var t=inp.value.trim();if(!t)return;\n  sock.emit("chat",{text:t});inp.value="";\n});\ndocument.getElementById("bc-ci").addEventListener("keypress",function(e){\n  if(e.key==="Enter")document.getElementById("bc-cs").click();\n});\n\n// ── REFRESH BUTTONS ────────────────────────────────\ndocument.getElementById("btn-ref1").addEventListener("click",refreshDevices);\ndocument.getElementById("btn-ref2").addEventListener("click",refreshDevices);\n\n// Init\nrefreshDevices();\n'

WA_HTML=(
'<div class="watch-page">'
'<div class="watch-main">'
'<div class="watch-vw" id="wvw">'
'<video id="wv" autoplay playsinline></video>'
'<div class="vc-ov" id="wov"><div class="vc-in">'
'<div class="spinner"></div>'
'<p id="wot">Connexion au stream...</p>'
'<p id="wot2" style="font-size:.8em;margin-top:4px;opacity:.5">WebRTC P2P...</p>'
'</div></div>'
'<div class="unmute-btn" id="wub"><button id="wub-btn">&#128266; Activer le son</button></div>'
'<div class="ctrl-bar" id="wctrl">'
'<div class="ctrl-top">'
'<span class="ctrl-live">LIVE</span>'
'<span class="ctrl-lat" id="wlat"></span>'
'<span id="waudio-tag" style="display:none"></span>'
'</div>'
'<div class="ctrl-btns">'
'<div class="cl">'
'<button class="cb" id="wbpl"><svg viewBox="0 0 24 24"><path id="wplp" d="M6 4l15 8-15 8V4z"/></svg></button>'
'<button class="cb" id="wbmu"><svg viewBox="0 0 24 24"><path id="wmup" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></button>'
'<div class="vol-wrap"><input type="range" id="wvol" min="0" max="1" step="0.02" value="1"></div>'
'<span style="color:rgba(255,255,255,.6);font-size:.78em;font-family:monospace">LIVE</span>'
'</div>'
'<div class="cr">'
'<button class="cb big" id="wbfs">'
'<svg viewBox="0 0 24 24" id="wice"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>'
'<svg viewBox="0 0 24 24" id="wicc" style="display:none"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>'
'</button></div></div></div></div>'
'<div class="watch-meta">'
'<div style="display:flex;align-items:center;gap:8px"><div class="rdot"></div>'
'<span style="font-weight:700;font-size:.95em">__TITLE__</span></div>'
'<span id="wvc" class="tag tag-v">0 viewers</span>'
'</div></div>'
'<div class="watch-sidebar">'
'<div class="sb-head"><h3>&#128172; Chat</h3>'
'<div class="nr"><label class="sw"><input type="checkbox" id="wntog" checked><span class="sl"></span></label>'
'<span style="color:var(--mu);font-size:.8em">Notif</span></div></div>'
'<div class="chat-msgs" id="wcm"></div>'
'<div class="chat-ia">'
'<input type="text" class="chat-name" id="wun" placeholder="Pseudo..." maxlength="20">'
'<div class="chat-row">'
'<input type="text" class="chat-in" id="wci" placeholder="Message..." maxlength="500" autocomplete="off">'
'<button class="chat-send" id="wcs">&#10148;</button>'
'</div></div></div>'
'</div>'
'<audio id="wns" preload="auto"><source src="/static/sounds/notification.wav" type="audio/wav"></audio>'
)
WA_JS='\nvar sock=io({transports:["polling","websocket"],upgrade:true});\nvar pc=null,ht=null,fsm=false;\nvar wv=document.getElementById("wv");\nvar wvw=document.getElementById("wvw");\nvar wov=document.getElementById("wov");\nvar wot=document.getElementById("wot");\nvar wctrl=document.getElementById("wctrl");\nvar wbpl=document.getElementById("wbpl");\nvar wplp=document.getElementById("wplp");\nvar wbmu=document.getElementById("wbmu");\nvar wmup=document.getElementById("wmup");\nvar wvol=document.getElementById("wvol");\nvar wbfs=document.getElementById("wbfs");\nvar wice=document.getElementById("wice");\nvar wicc=document.getElementById("wicc");\nvar wub=document.getElementById("wub");\nvar wub_btn=document.getElementById("wub-btn");\nvar wlat=document.getElementById("wlat");\nvar watag=document.getElementById("waudio-tag");\nvar wcm=document.getElementById("wcm");\nvar wci=document.getElementById("wci");\nvar wcs=document.getElementById("wcs");\nvar wun=document.getElementById("wun");\nvar wntog=document.getElementById("wntog");\nvar wns=document.getElementById("wns");\nvar wvc=document.getElementById("wvc");\n\nvar IPL="M6 4l15 8-15 8V4z",IPA="M6 19h4V5H6v14zm8-14v14h4V5h-4z";\nvar IVO="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z";\nvar IMU="M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06A8.99 8.99 0 0 0 17.73 19l2 2L21 19.73l-18-18z";\n\nfunction getICE(){return [{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}];}\n\n// Afficher info si pas d audio\nif(!ROOM_HAS_AUDIO&&watag){\n  watag.style.display="inline-flex";\n  watag.className="tag";\n  watag.style.cssText="display:inline-flex;background:rgba(245,158,11,.14);color:#f59e0b;border:1px solid rgba(245,158,11,.3);padding:2px 9px;border-radius:20px;font-size:.76em;font-weight:700";\n  watag.textContent="Muet";\n}\n\nfunction doUnmute(){\n  wv.muted=false;\n  wv.volume=1;\n  wmup.setAttribute("d",IVO);\n  wvol.value=1;\n  wub.style.display="none";\n  toast("Son active !","ok");\n}\n\nif(wub_btn){\n  wub_btn.addEventListener("click",doUnmute);\n}\n\nfunction hideOv(){wov.style.opacity="0";setTimeout(function(){wov.style.display="none";},400);}\nfunction showOv(m){wot.textContent=m;wov.style.display="flex";wov.style.opacity="1";}\n\nwun.value=localStorage.getItem("sc_name")||"";\n\nsock.on("connect",function(){\n  sock.emit("join_viewer",{room_id:ROOM_ID,name:wun.value.trim()||"Anonyme"});\n});\nsock.on("joined",function(d){\n  d.chat.forEach(function(m){addMsg(m,false);});\n  wcm.scrollTop=wcm.scrollHeight;\n  // Infos sur l audio\n  if(!d.has_audio){\n    var sys=document.createElement("div");\n    sys.className="chat-sys";\n    sys.textContent="Ce stream n a pas de son (carte de capture sans audio configure)";\n    wcm.appendChild(sys);\n  }\n});\n\nsock.on("rtc_offer",async function(d){\n  if(pc){pc.close();pc=null;}\n  pc=new RTCPeerConnection({iceServers:getICE()});\n\n  pc.ontrack=function(e){\n    if(e.streams&&e.streams[0]){\n      wv.srcObject=e.streams[0];\n      var audioTracks=e.streams[0].getAudioTracks();\n      var hasAudio=(audioTracks.length>0);\n\n      // TOUJOURS demarrer sans mute pour tenter le son\n      wv.muted=false;\n      wv.volume=1;\n\n      wv.play().then(function(){\n        hideOv();\n        wub.style.display="none";\n        wmup.setAttribute("d",IVO);\n        wvol.value=1;\n        if(hasAudio){\n          toast("Son + video OK !","ok");\n        }else{\n          toast("Video OK (pas de piste audio)","info");\n        }\n      }).catch(function(err){\n        // Autoplay bloque : jouer en muet d abord puis proposer activation\n        wv.muted=true;\n        wv.volume=1;\n        wv.play().then(function(){\n          hideOv();\n          // Montrer le bouton "Activer le son" SEULEMENT si la stream a de l audio\n          if(hasAudio||ROOM_HAS_AUDIO){\n            wub.style.display="flex";\n            wmup.setAttribute("d",IMU);\n            wvol.value=0;\n          }else{\n            wub.style.display="none";\n          }\n        }).catch(function(){});\n      });\n    }\n  };\n\n  pc.onicecandidate=function(e){\n    if(e.candidate)sock.emit("rtc_ice",{target:d.from,candidate:e.candidate});\n  };\n\n  pc.onconnectionstatechange=function(){\n    if(pc.connectionState==="connected"){\n      wlat.textContent="< 500ms";\n      // Verifier les tracks audio connectes\n      var receivers=pc.getReceivers();\n      var audioRx=receivers.filter(function(r){return r.track&&r.track.kind==="audio";});\n      if(audioRx.length>0){\n        toast("Connexion etablie avec audio","ok");\n      }else if(ROOM_HAS_AUDIO){\n        toast("Connexion etablie (audio en attente)","info");\n      }else{\n        toast("Connexion etablie (stream muet)","info");\n      }\n    }\n    else if(pc.connectionState==="failed"){\n      showOv("Connexion perdue, reconnexion...");\n      setTimeout(function(){location.reload();},3000);\n    }\n  };\n\n  try{\n    await pc.setRemoteDescription(new RTCSessionDescription(d.sdp));\n    var ans=await pc.createAnswer();\n    await pc.setLocalDescription(ans);\n    sock.emit("rtc_answer",{target:d.from,sdp:pc.localDescription});\n  }catch(e){toast("WebRTC: "+e.message,"err");}\n\n  // Mesurer latence\n  setInterval(function(){\n    if(!pc)return;\n    pc.getStats().then(function(s){\n      s.forEach(function(r){\n        if(r.type==="inbound-rtp"&&r.kind==="video"&&r.jitter!==undefined){\n          var ms=Math.round(r.jitter*1000);\n          wlat.textContent=ms<50?"ultra-low":ms<200?"low":ms+"ms";\n        }\n      });\n    }).catch(function(){});\n  },4000);\n});\n\nsock.on("rtc_ice",async function(d){\n  if(!pc)return;\n  try{await pc.addIceCandidate(new RTCIceCandidate(d.candidate));}catch(e){}\n});\nsock.on("room_closed",function(d){\n  if(pc){pc.close();pc=null;}\n  wv.srcObject=null;\n  showOv(d.reason||"Stream termine");\n  setTimeout(function(){location.href="/";},3000);\n});\nsock.on("viewer_count",function(d){wvc.textContent=d.count+" viewer"+(d.count>1?"s":"");});\nsock.on("chat",function(m){\n  addMsg(m,true);\n  if(wntog.checked&&m.name!==(wun.value.trim()||"Anonyme"))pN(m.name,m.text);\n});\nsock.on("error_msg",function(d){showOv(d.msg||"Erreur");});\nsock.on("connect_error",function(e){showOv("Erreur: "+e.message);});\n\nfunction addMsg(m,an){\n  var d=document.createElement("div");d.className="chat-msg"+(an?" chat-new":"");\n  var t=new Date(m.ts*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});\n  d.innerHTML="<span class=\\"chat-time\\">"+t+"</span><span class=\\"chat-user\\">"+esc(m.name)+"</span><span class=\\"chat-text\\">"+esc(m.text)+"</span>";\n  wcm.appendChild(d);wcm.scrollTop=wcm.scrollHeight;\n  while(wcm.children.length>200)wcm.removeChild(wcm.firstChild);\n}\nfunction sendMsg(){\n  var t=wci.value.trim();if(!t)return;\n  var n=wun.value.trim()||"Anonyme";localStorage.setItem("sc_name",n);wun.value=n;\n  sock.emit("chat",{text:t});wci.value="";\n}\nwcs.addEventListener("click",sendMsg);\nwci.addEventListener("keypress",function(e){if(e.key==="Enter")sendMsg();});\n\nwbpl.addEventListener("click",function(){wv.paused?wv.play():wv.pause();});\nwv.addEventListener("play",function(){wplp.setAttribute("d",IPA);});\nwv.addEventListener("pause",function(){wplp.setAttribute("d",IPL);});\nwv.addEventListener("dblclick",tFS);\nwbmu.addEventListener("click",function(){\n  wv.muted=!wv.muted;\n  wmup.setAttribute("d",wv.muted?IMU:IVO);\n  wvol.value=wv.muted?0:Math.max(wv.volume,0.1);\n  if(!wv.muted)wub.style.display="none";\n});\nwvol.addEventListener("input",function(){\n  wv.volume=parseFloat(wvol.value);\n  wv.muted=(wv.volume===0);\n  wmup.setAttribute("d",wv.muted?IMU:IVO);\n  if(!wv.muted)wub.style.display="none";\n});\n\nfunction tFS(){if(!document.fullscreenElement&&!document.webkitFullscreenElement)eFS();else xFS();}\nfunction eFS(){var fn=wvw.requestFullscreen||wvw.webkitRequestFullscreen||wvw.mozRequestFullScreen||wvw.msRequestFullscreen;if(fn)fn.call(wvw);}\nfunction xFS(){var fn=document.exitFullscreen||document.webkitExitFullscreen||document.mozCancelFullScreen||document.msExitFullscreen;if(fn)fn.call(document);}\nfunction onFC(){\n  fsm=!!(document.fullscreenElement||document.webkitFullscreenElement);\n  if(fsm){document.body.classList.add("fs");wvw.classList.add("fa");wice.style.display="none";wicc.style.display="block";sH();}\n  else{document.body.classList.remove("fs");wvw.classList.remove("fa");wice.style.display="block";wicc.style.display="none";wctrl.classList.remove("hidden");document.body.style.cursor="";cH();}\n}\n["fullscreenchange","webkitfullscreenchange","mozfullscreenchange","MSFullscreenChange"].forEach(function(ev){document.addEventListener(ev,onFC);});\nwbfs.addEventListener("click",tFS);\nfunction sH(){cH();wctrl.classList.remove("hidden");document.body.style.cursor="";ht=setTimeout(function(){if(fsm){wctrl.classList.add("hidden");document.body.style.cursor="none";}},3000);}\nfunction cH(){if(ht){clearTimeout(ht);ht=null;}}\nwvw.addEventListener("mousemove",function(){if(fsm)sH();});\nwctrl.addEventListener("mouseenter",function(){cH();wctrl.classList.remove("hidden");document.body.style.cursor="";});\nwctrl.addEventListener("mouseleave",function(){if(fsm)sH();});\ndocument.addEventListener("keydown",function(e){\n  var tg=document.activeElement.tagName;if(tg==="INPUT"||tg==="TEXTAREA")return;\n  if(e.key==="f"||e.key==="F"){e.preventDefault();tFS();}\n  else if(e.key===" "||e.key==="k"||e.key==="K"){e.preventDefault();wv.paused?wv.play():wv.pause();}\n  else if(e.key==="m"||e.key==="M"){e.preventDefault();wbmu.click();}\n  else if(e.key==="ArrowUp"){e.preventDefault();wv.volume=Math.min(1,wv.volume+0.1);wvol.value=wv.volume;}\n  else if(e.key==="ArrowDown"){e.preventDefault();wv.volume=Math.max(0,wv.volume-0.1);wvol.value=wv.volume;}\n  else if(e.key==="Escape"&&fsm){e.preventDefault();xFS();}\n});\nfunction pN(u,t){\n  try{wns.currentTime=0;wns.play().catch(function(){});}catch(e){}\n  if("Notification"in window&&Notification.permission==="granted")new Notification("Message de "+u,{body:t,silent:true});\n}\nif("Notification"in window&&Notification.permission==="default")Notification.requestPermission();\n'
