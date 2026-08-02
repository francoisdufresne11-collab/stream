import os,time,uuid,shutil,secrets,threading,datetime
from pathlib import Path
from flask import (
    Flask,render_template_string,request,jsonify,
    send_from_directory,Response,redirect,url_for,session,flash
)
from flask_socketio import SocketIO,emit,join_room,leave_room

# ── App ─────────────────────────────────────
app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"]=500*1024*1024
app.config["ADMIN_PASSWORD"]=os.environ.get("ADMIN_PASSWORD","admin2026")

socketio=SocketIO(
    app,cors_allowed_origins="*",async_mode="threading",
    ping_timeout=60,ping_interval=20,
    max_http_buffer_size=10_000_000,
    logger=False,engineio_logger=False,
)

BASE_DIR=Path(__file__).resolve().parent
STREAMS_DIR=BASE_DIR/"streams"
STREAMS_DIR.mkdir(exist_ok=True)

active_streams={}
stream_viewers={}
chat_history={}
server_stats={"total_streams":0,"total_messages":0,"started":time.time()}
_lock=threading.Lock()

QUALITIES={
    "1080p":{"res":"1920x1080","vb":"5000k","ab":"192k"},
    "720p": {"res":"1280x720", "vb":"2500k","ab":"128k"},
    "480p": {"res":"854x480",  "vb":"1200k","ab":"96k"},
    "360p": {"res":"640x360",  "vb":"600k", "ab":"64k"},
}

# ── Templates inline (jamais de TemplateNotFound) ──
_BASE="""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}StreamCaster{% endblock %}</title>
<link rel="stylesheet" href="/static/css/style.css">
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.13"></script>
{% block head %}{% endblock %}
</head><body>
<nav class="navbar" id="main-navbar">
  <a href="/" class="logo">StreamCaster</a>
  <div class="nav-links"><a href="/">Accueil</a><a href="/broadcast">Diffuser</a><a href="/admin">Admin</a></div>
</nav>
<main class="main-content">
{% with messages=get_flashed_messages() %}{% if messages %}
<div class="flash-box">{% for m in messages %}<div class="flash-msg">{{ m }}</div>{% endfor %}</div>
{% endif %}{% endwith %}
{% block content %}{% endblock %}
</main>
{% block scripts %}{% endblock %}
</body></html>"""

_INDEX=_BASE.replace("{% block title %}StreamCaster{% endblock %}","{% block title %}StreamCaster{% endblock %}")\
.replace("{% block head %}{% endblock %}","{% block head %}{% endblock %}")\
.replace("{% block content %}{% endblock %}",'''
<div class="home"><h1>Streams en direct</h1>
<div id="grid" class="grid">
<div id="empty" class="empty-home"{% if streams %} style="display:none"{% endif %}>
<p>Aucun stream en direct...</p>
<a href="/broadcast" class="btn btn-p">Commencer a diffuser</a>
</div>
{% for s in streams %}
<a href="/watch/{{ s.id }}" class="card" data-id="{{ s.id }}">
<div class="thumb"><span class="lb">LIVE</span><div class="tov"><span class="pi">&#9654;</span></div></div>
<div class="cinfo"><h3>{{ s.title }}</h3><span id="vc-{{ s.id }}">{{ s.viewers }} viewers</span></div>
</a>{% endfor %}
</div></div>''')\
.replace("{% block scripts %}{% endblock %}",'''
<script>
var socket=io({transports:["polling","websocket"],upgrade:true});
function load(){
fetch("/api/streams").then(function(r){return r.json();}).then(function(st){
var g=document.getElementById("grid"),e=document.getElementById("empty");
if(!st.length){e.style.display="block";return;}e.style.display="none";
var ids={};st.forEach(function(s){ids[s.id]=true;});
var cs=g.querySelectorAll(".card");for(var i=0;i<cs.length;i++){if(!ids[cs[i].dataset.id])cs[i].remove();}
st.forEach(function(s){
var c=g.querySelector('[data-id="'+s.id+'"]');
if(!c){c=document.createElement("a");c.href="/watch/"+s.id;c.className="card";c.dataset.id=s.id;
c.innerHTML='<div class="thumb"><span class="lb">LIVE</span><div class="tov"><span class="pi">&#9654;</span></div></div><div class="cinfo"><h3>'+s.title+'</h3><span id="vc-'+s.id+'">'+s.viewers+' viewers</span></div>';
g.appendChild(c);}else{var v=document.getElementById("vc-"+s.id);if(v)v.textContent=s.viewers+" viewers";}
});}).catch(function(){});}
load();setInterval(load,5000);
socket.on("stream_created",load);socket.on("stream_ended",load);
</script>''')

def _uptime():
    s=int(time.time()-server_stats["started"]);h,r=divmod(s,3600);m,s=divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def _master(sid):
    sdir=STREAMS_DIR/sid
    bw={"1080p":5200000,"720p":2600000,"480p":1300000,"360p":650000}
    rs={"1080p":"1920x1080","720p":"1280x720","480p":"854x480","360p":"640x360"}
    lines=["#EXTM3U"]
    for q in QUALITIES:
        if (sdir/f"{q}.m3u8").exists():
            lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bw[q]},RESOLUTION={rs[q]},NAME="{q}"')
            lines.append(f"{q}.m3u8")
    if len(lines)>1:(sdir/"master.m3u8").write_text("\n".join(lines)+"\n",encoding="utf-8")

def _cleanup(sid):
    with _lock:
        sdir=STREAMS_DIR/sid
        if sdir.exists():shutil.rmtree(sdir,ignore_errors=True)
        active_streams.pop(sid,None);stream_viewers.pop(sid,None);chat_history.pop(sid,None)

def _ts(v):
    try:return datetime.datetime.fromtimestamp(float(v)).strftime("%H:%M:%S")
    except:return "?"

# ── Erreurs HTTP ─────────────────────────────
@app.errorhandler(404)
def e404(e):
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>404</title>
    <style>body{font-family:sans-serif;background:#0f0f23;color:#e0e0e0;text-align:center;padding:80px}
    h1{font-size:5em;color:#a78bfa}a{color:#a78bfa}</style></head>
    <body><h1>404</h1><p>Page introuvable</p><a href="/">Retour</a></body></html>""",404

@app.errorhandler(500)
def e500(e):
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>500</title>
    <style>body{font-family:sans-serif;background:#0f0f23;color:#e0e0e0;text-align:center;padding:80px}
    h1{font-size:5em;color:#ef4444}a{color:#a78bfa}</style></head>
    <body><h1>500</h1><p>Erreur interne</p><a href="/">Retour</a></body></html>""",500

# ── Routes ───────────────────────────────────
@app.route("/")
def index():
    from flask import render_template_string
    return render_template_string(_INDEX,streams=list(active_streams.values()))

@app.route("/broadcast")
def broadcast_page():
    from flask import render_template_string
    tpl=_BASE.replace("{% block title %}StreamCaster{% endblock %}","{% block title %}Diffuser{% endblock %}")\
    .replace("{% block content %}{% endblock %}",'''
<div class="bc"><h1>Centre de diffusion</h1>
<div class="bc-grid">
<div class="icard"><h3>Diffuser depuis votre PC</h3>
<p>URL du serveur :</p><div class="url-box" id="surl"></div>
<button class="btn btn-p" style="margin-top:10px;width:100%" id="copybtn">Copier l URL</button>
<div style="margin-top:20px"><p style="color:#a78bfa;font-weight:700;margin-bottom:8px">Instructions :</p>
<ol class="how"><li>Clonez le projet localement</li><li>Lancez python broadcaster.py</li>
<li>Collez cette URL dans le champ serveur</li><li>Selectionnez votre carte de capture USB</li>
<li>Cliquez sur Demarrer le Stream</li></ol></div></div>
<div class="icard"><h3>Streams actifs</h3><div id="asl"><p>Chargement...</p></div>
<h3 style="margin-top:24px">Stats</h3><div id="lstats" class="ls-grid"></div>
</div></div></div>''')\
    .replace("{% block scripts %}{% endblock %}",'''
<script>
document.getElementById("surl").textContent=window.location.origin;
document.getElementById("copybtn").onclick=function(){
navigator.clipboard.writeText(document.getElementById("surl").textContent)
.then(function(){document.getElementById("copybtn").textContent="Copie!";}).catch(function(){});};
function loadBc(){
fetch("/api/streams").then(function(r){return r.json();}).then(function(st){
var l=document.getElementById("asl");
if(!st.length){l.innerHTML="<p>Aucun stream actif</p>";return;}
l.innerHTML=st.map(function(s){return '<div class="asi"><a href="/watch/'+s.id+'">'+s.title+'</a><span style="margin-left:auto">'+s.viewers+'v</span></div>';}).join("");});
fetch("/api/stats").then(function(r){return r.json();}).then(function(d){
document.getElementById("lstats").innerHTML='<div class="lsi"><span>Streams</span><b>'+d.streams+'</b></div>'+'<div class="lsi"><span>Viewers</span><b>'+d.viewers+'</b></div>'+'<div class="lsi"><span>Messages</span><b>'+d.messages+'</b></div>'+'<div class="lsi"><span>Uptime</span><b>'+d.uptime+'</b></div>';}).catch(function(){});}
loadBc();setInterval(loadBc,5000);
</script>''')
    return render_template_string(tpl)

@app.route("/watch/<sid>")
def watch_page(sid):
    from flask import render_template_string
    s=active_streams.get(sid)
    if not s:return redirect(url_for("index"))
    tpl=_BASE\
    .replace("{% block title %}StreamCaster{% endblock %}","{% block title %}"+s["title"]+"{% endblock %}")\
    .replace("{% block head %}{% endblock %}","")\
    .replace("{% block content %}{% endblock %}",_WATCH_HTML)\
    .replace("{% block scripts %}{% endblock %}","<script>"+_WATCH_JS.replace("__SID__",sid)+"</script>")
    return render_template_string(tpl,stream=s,stream_id=sid)

@app.route("/admin",methods=["GET","POST"])
def admin():
    from flask import render_template_string
    if request.method=="POST":
        if request.form.get("password","")==app.config["ADMIN_PASSWORD"]:
            session["admin"]=True;return redirect(url_for("admin"))
        flash("Mot de passe incorrect")
    if not session.get("admin"):
        tpl=_BASE.replace("{% block title %}StreamCaster{% endblock %}","{% block title %}Admin{% endblock %}")\
        .replace("{% block content %}{% endblock %}",'''
<div class="login-wrap"><div class="login-card"><h2>Administration</h2>
<form method="POST" action="/admin">
<div class="fg"><label>Mot de passe</label><input type="password" name="password" class="fi" autofocus placeholder="..."></div>
<button type="submit" class="btn btn-p" style="width:100%;margin-top:8px">Connexion</button>
</form></div></div>''')
        return render_template_string(tpl)
    stats={"streams":len(active_streams),"viewers":sum(len(v) for v in stream_viewers.values()),
           "messages":server_stats["total_messages"],"total_streams":server_stats["total_streams"],
           "uptime":_uptime(),"active":list(active_streams.values())}
    rows="".join(f'<tr><td><code>{s["id"]}</code></td><td>{s["title"]}</td><td>{s["viewers"]}</td><td>{_ts(s["created"])}</td>'
                 f'<td><a href="/watch/{s["id"]}" class="bsm bb" target="_blank">Voir</a>'
                 f'<form method="POST" action="/admin/kick/{s["id"]}" style="display:inline" onsubmit="return confirm('Arreter ?')"><button class="bsm br">Stop</button></form></td></tr>'
                 for s in stats["active"])
    tbl=f'<table class="adm-tbl"><thead><tr><th>ID</th><th>Titre</th><th>Viewers</th><th>Debut</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table>' if stats["active"] else '<div class="empty">Aucun stream actif</div>'
    tpl=_BASE.replace("{% block title %}StreamCaster{% endblock %}","{% block title %}Dashboard Admin{% endblock %}")\
    .replace("{% block head %}{% endblock %}","<meta http-equiv=\"refresh\" content=\"10\">")\
    .replace("{% block content %}{% endblock %}",f'''
<div class="adm-wrap">
<div class="adm-top"><h1>Dashboard Admin</h1><a href="/admin/logout" class="btn btn-d">Deconnexion</a></div>
<div class="stat-cards">
<div class="sc"><div class="si">Live</div><div class="sv">{stats["streams"]}</div><div class="sl2">Streams</div></div>
<div class="sc"><div class="si">View</div><div class="sv">{stats["viewers"]}</div><div class="sl2">Viewers</div></div>
<div class="sc"><div class="si">Chat</div><div class="sv">{stats["messages"]}</div><div class="sl2">Messages</div></div>
<div class="sc"><div class="si">Total</div><div class="sv">{stats["total_streams"]}</div><div class="sl2">Streams</div></div>
<div class="sc"><div class="si">Up</div><div class="sv sm">{stats["uptime"]}</div><div class="sl2">Uptime</div></div>
</div>
<div class="adm-sec"><h2>Streams en direct</h2>{tbl}</div>
<div class="adm-sec"><h2>Config</h2>
<div class="cfg-grid">
<div class="ci"><span class="ck">Worker</span><code>gthread</code></div>
<div class="ci"><span class="ck">async_mode</span><code>threading</code></div>
<div class="ci"><span class="ck">WebSocket</span><code>simple-websocket</code></div>
<div class="ci"><span class="ck">Python</span><code>3.11-slim</code></div>
</div></div>
<p class="adm-ref">Actualisation toutes les 10s</p>
</div>''')
    return render_template_string(tpl)

@app.route("/admin/logout")
def admin_logout():session.pop("admin",None);return redirect(url_for("index"))

@app.route("/admin/kick/<sid>",methods=["POST"])
def admin_kick(sid):
    if not session.get("admin"):return jsonify({"error":"non autorise"}),403
    _cleanup(sid);socketio.emit("stream_ended",{"stream_id":sid})
    flash(f"Stream {sid} arrete");return redirect(url_for("admin"))

# ── API ──────────────────────────────────────
@app.route("/api/streams")
def api_streams():return jsonify(list(active_streams.values()))

@app.route("/api/stats")
def api_stats():
    return jsonify({"streams":len(active_streams),
        "viewers":sum(len(v) for v in stream_viewers.values()),
        "total_streams":server_stats["total_streams"],
        "total_messages":server_stats["total_messages"],
        "uptime":_uptime()})

@app.route("/api/stream/create",methods=["POST"])
def api_create():
    data=request.get_json(silent=True) or {}
    sid=uuid.uuid4().hex[:8];title=str(data.get("title","Stream"))[:80]
    (STREAMS_DIR/sid).mkdir(parents=True,exist_ok=True)
    meta={"id":sid,"title":title,"created":time.time(),"status":"live","viewers":0}
    with _lock:
        active_streams[sid]=meta;stream_viewers[sid]=set()
        chat_history[sid]=[];server_stats["total_streams"]+=1
    socketio.emit("stream_created",meta)
    return jsonify({"stream_id":sid,"status":"ok"})

@app.route("/api/stream/<sid>/upload",methods=["POST"])
def api_upload(sid):
    if sid not in active_streams:return jsonify({"error":"stream inconnu"}),404
    raw=request.headers.get("X-Filename","")
    if not raw:return jsonify({"error":"X-Filename manquant"}),400
    fname=Path(raw).name
    if not fname.endswith((".m3u8",".ts")):return jsonify({"error":"type non autorise"}),400
    (STREAMS_DIR/sid/fname).write_bytes(request.data)
    if fname.endswith(".m3u8"):_master(sid)
    return jsonify({"ok":True})

@app.route("/api/stream/<sid>/stop",methods=["POST"])
def api_stop(sid):
    if sid not in active_streams:return jsonify({"error":"inconnu"}),404
    _cleanup(sid);socketio.emit("stream_ended",{"stream_id":sid})
    return jsonify({"status":"stopped"})

@app.route("/api/stream/<sid>/info")
def api_info(sid):
    if sid not in active_streams:return jsonify({"error":"inconnu"}),404
    m=dict(active_streams[sid]);m["chat_count"]=len(chat_history.get(sid,[]))
    return jsonify(m)

@app.route("/streams/<sid>/<path:fn>")
def serve_hls(sid,fn):
    safe=Path(fn).name;sdir=STREAMS_DIR/sid
    if not (sdir/safe).exists():return Response("Not Found",status=404)
    resp=send_from_directory(str(sdir),safe)
    resp.headers["Cache-Control"]="no-cache, no-store"
    resp.headers["Access-Control-Allow-Origin"]="*"
    if safe.endswith(".m3u8"):resp.headers["Content-Type"]="application/vnd.apple.mpegurl"
    elif safe.endswith(".ts"):resp.headers["Content-Type"]="video/MP2T"
    return resp

# ── Socket.IO ─────────────────────────────────
@socketio.on("connect")
def _conn():pass

@socketio.on("join_stream")
def _join(data):
    if not isinstance(data,dict):return
    sid=data.get("stream_id","");u=str(data.get("username","Anonyme"))[:30]
    if not sid or sid not in active_streams:return
    join_room(sid)
    with _lock:
        stream_viewers.setdefault(sid,set()).add(request.sid)
        cnt=len(stream_viewers[sid]);active_streams[sid]["viewers"]=cnt
    emit("chat_history",{"messages":chat_history.get(sid,[])[-50:]})
    emit("system_msg",{"text":f"Bienvenue {u}","ts":time.time()},to=sid)
    emit("viewer_count",{"count":cnt},to=sid)

@socketio.on("leave_stream")
def _leave(data):
    if not isinstance(data,dict):return
    sid=data.get("stream_id","");leave_room(sid)
    with _lock:
        if sid in stream_viewers:
            stream_viewers[sid].discard(request.sid);cnt=len(stream_viewers[sid])
            if sid in active_streams:active_streams[sid]["viewers"]=cnt
        else:cnt=0
    emit("viewer_count",{"count":cnt},to=sid)

@socketio.on("disconnect")
def _disc():
    rsid=request.sid
    with _lock:
        for s in stream_viewers.values():s.discard(rsid)
        for k,m in active_streams.items():m["viewers"]=len(stream_viewers.get(k,set()))

@socketio.on("chat_msg")
def _msg(data):
    if not isinstance(data,dict):return
    sid=data.get("stream_id","");u=str(data.get("username","Anonyme"))[:30]
    text=str(data.get("text","")).strip()[:500]
    if not text or not sid or sid not in active_streams:return
    msg={"username":u,"text":text,"ts":time.time(),"id":uuid.uuid4().hex[:6]}
    with _lock:
        chat_history.setdefault(sid,[]).append(msg)
        chat_history[sid]=chat_history[sid][-300:]
        server_stats["total_messages"]+=1
    emit("new_chat_msg",msg,to=sid)

# ── HTML watch (inline) ──────────────────────
_WATCH_HTML="""
<div class="watch-root">
<div class="pcol"><div class="pfsw" id="pfsw">
<video id="vid" autoplay playsinline></video>
<div class="ov" id="ov"><div class="ov-in"><div class="spin"></div><p id="ovt">Connexion...</p></div></div>
<div class="cbar" id="cbar">
<div class="prow"><div class="pbg" id="pbg"><div class="pbuf" id="pbuf"></div><div class="pp" id="pp"></div><div class="pt" id="pt"></div></div><span class="lpill">LIVE</span></div>
<div class="crow"><div class="cl">
<button class="cb" id="bpl"><svg viewBox="0 0 24 24"><path id="plp" d="M6 4l15 8-15 8V4z"/></svg></button>
<button class="cb" id="bmu"><svg viewBox="0 0 24 24"><path id="mup" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></button>
<div class="vw"><input type="range" id="vol" min="0" max="1" step="0.02" value="1"></div>
<span class="ctime" id="ctime">00:00</span>
</div><div class="cr">
<select class="csel" id="ssel"><option value="0.5">0.5x</option><option value="1" selected>1x</option><option value="1.5">1.5x</option><option value="2">2x</option></select>
<select class="csel" id="qsel"><option value="-1">Auto</option></select>
<button class="cb cbt" id="bcht">Chat</button>
<button class="cb" id="bpip"><svg viewBox="0 0 24 24"><path d="M19 7h-8v6h8V7zm2-4H3c-1.1 0-2 .9-2 2v14c0 1.1.9 1.98 2 1.98h18c1.1 0 2-.88 2-1.98V5c0-1.1-.9-2-2-2zm0 16.01H3V4.98h18v14.03z"/></svg></button>
<button class="cb cbfs" id="bfs"><svg viewBox="0 0 24 24" id="ice"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg><svg viewBox="0 0 24 24" id="icc" style="display:none"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg></button>
</div></div></div>
<div class="cfs" id="cfs"><div class="cfsh"><span>Chat</span><button class="cfsx" id="cfsx">X</button></div>
<div class="cfsm" id="cfsm"></div>
<div class="cfsi"><input type="text" id="fsun" placeholder="Pseudo..." maxlength="20">
<div class="cfsir"><input type="text" id="fsci" placeholder="Message..." maxlength="500" autocomplete="off"><button id="fscs">OK</button></div></div>
</div></div>
<div class="pmeta" id="pmeta"><div class="pml"><span class="lbsm">LIVE</span><h2 id="stitle"></h2></div><span id="vc" class="pmr">0 viewers</span></div>
</div>
<div class="chatcol" id="chatcol">
<div class="chath"><h3>Chat en direct</h3><div class="nrow"><label class="sw"><input type="checkbox" id="ntog" checked><span class="sl"></span></label><span>Notif</span></div></div>
<div class="chatm" id="chatm"></div>
<div class="chatia"><input type="text" id="uname" placeholder="Pseudo..." maxlength="20">
<div class="mrow"><input type="text" id="ci" placeholder="Message..." maxlength="500" autocomplete="off"><button id="cs">OK</button></div>
</div></div></div>
<audio id="ns" preload="auto"><source src="/static/sounds/notification.wav" type="audio/wav"></audio>
"""

_WATCH_JS="""
var SID="__SID__";
var socket=io({transports:["polling","websocket"],upgrade:true});
function G(id){return document.getElementById(id);}
var vid=G("vid"),pfsw=G("pfsw"),ov=G("ov"),ovt=G("ovt"),cbar=G("cbar"),
bpl=G("bpl"),plp=G("plp"),bmu=G("bmu"),mup=G("mup"),vol=G("vol"),ctime=G("ctime"),
ssel=G("ssel"),qsel=G("qsel"),bpip=G("bpip"),bfs=G("bfs"),ice=G("ice"),icc=G("icc"),
bcht=G("bcht"),pbg=G("pbg"),pbuf=G("pbuf"),pp=G("pp"),pt=G("pt"),
chatm=G("chatm"),ci=G("ci"),cs=G("cs"),uname=G("uname"),ntog=G("ntog"),
ns=G("ns"),vc=G("vc"),cfs=G("cfs"),cfsm=G("cfsm"),fsun=G("fsun"),
fsci=G("fsci"),fscs=G("fscs"),cfsx=G("cfsx");
var hls=null,ht=null,fsm=false,cfv=true;
function initP(){var src="/streams/"+SID+"/master.m3u8";
if(Hls.isSupported()){if(hls){hls.destroy();hls=null;}
hls=new Hls({enableWorker:true,lowLatencyMode:true,backBufferLength:10,maxBufferLength:5,liveSyncDurationCount:2,liveMaxLatencyDurationCount:5});
hls.loadSource(src);hls.attachMedia(vid);
hls.on(Hls.Events.MANIFEST_PARSED,function(e,d){hideO();qsel.innerHTML='<option value="-1">Auto</option>';
d.levels.forEach(function(lv,i){var o=document.createElement("option");o.value=i;o.textContent=lv.height+"p";qsel.appendChild(o);});
vid.play().catch(function(){});});
hls.on(Hls.Events.ERROR,function(e,d){if(d.fatal)setTimeout(tryI,3000);});
qsel.onchange=function(){hls.currentLevel=parseInt(qsel.value);};
}else if(vid.canPlayType("application/vnd.apple.mpegurl")){
vid.src=src;vid.addEventListener("loadedmetadata",hideO,{once:true});vid.play().catch(function(){});}}
function tryI(){fetch("/streams/"+SID+"/master.m3u8").then(function(r){if(r.ok)initP();else setTimeout(tryI,2000);}).catch(function(){setTimeout(tryI,2000);});}
tryI();
function hideO(){ov.style.opacity="0";setTimeout(function(){ov.style.display="none";},500);}
function showO(m){ovt.textContent=m;var s=ov.querySelector(".spin");if(s)s.style.display="none";ov.style.display="flex";ov.style.opacity="1";}
var IPL="M6 4l15 8-15 8V4z",IPA="M6 19h4V5H6v14zm8-14v14h4V5h-4z",
IVO="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z",
IMU="M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06A8.99 8.99 0 0 0 17.73 19l2 2L21 19.73l-18-18z";
bpl.onclick=function(){vid.paused?vid.play():vid.pause();};
vid.addEventListener("play",function(){plp.setAttribute("d",IPA);});
vid.addEventListener("pause",function(){plp.setAttribute("d",IPL);});
vid.addEventListener("dblclick",tFS);
bmu.onclick=function(){vid.muted=!vid.muted;mup.setAttribute("d",vid.muted?IMU:IVO);vol.value=vid.muted?0:vid.volume;};
vol.oninput=function(){vid.volume=parseFloat(vol.value);vid.muted=vid.volume===0;mup.setAttribute("d",vid.muted?IMU:IVO);};
ssel.onchange=function(){vid.playbackRate=parseFloat(ssel.value);};
vid.addEventListener("timeupdate",function(){
var t=Math.floor(vid.currentTime);
ctime.textContent=String(Math.floor(t/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0");
if(vid.duration){var p=(vid.currentTime/vid.duration)*100;pp.style.width=p+"%";pt.style.left=p+"%";
if(vid.buffered.length)pbuf.style.width=(vid.buffered.end(vid.buffered.length-1)/vid.duration*100)+"%";}});
pbg.onclick=function(e){if(!vid.duration)return;var r=pbg.getBoundingClientRect();vid.currentTime=((e.clientX-r.left)/r.width)*vid.duration;};
bpip.onclick=function(){if(document.pictureInPictureElement)document.exitPictureInPicture().catch(function(){});else vid.requestPictureInPicture().catch(function(){});};
function tFS(){if(!document.fullscreenElement&&!document.webkitFullscreenElement)eFS();else xFS();}
function eFS(){var fn=pfsw.requestFullscreen||pfsw.webkitRequestFullscreen||pfsw.mozRequestFullScreen||pfsw.msRequestFullscreen;if(fn)fn.call(pfsw);}
function xFS(){var fn=document.exitFullscreen||document.webkitExitFullscreen||document.mozCancelFullScreen||document.msExitFullscreen;if(fn)fn.call(document);}
function onFC(){
fsm=!!(document.fullscreenElement||document.webkitFullscreenElement);
if(fsm){document.body.classList.add("is-fs");pfsw.classList.add("fs-a");ice.style.display="none";icc.style.display="block";fsun.value=uname.value;cfs.style.display=cfv?"flex":"none";sH();
}else{document.body.classList.remove("is-fs");pfsw.classList.remove("fs-a");ice.style.display="block";icc.style.display="none";cfs.style.display="none";cbar.classList.remove("ch");document.body.style.cursor="";cH();}}
["fullscreenchange","webkitfullscreenchange","mozfullscreenchange","MSFullscreenChange"].forEach(function(ev){document.addEventListener(ev,onFC);});
bfs.onclick=tFS;
function sH(){cH();cbar.classList.remove("ch");document.body.style.cursor="";
ht=setTimeout(function(){if(fsm){cbar.classList.add("ch");document.body.style.cursor="none";}},3000);}
function cH(){if(ht){clearTimeout(ht);ht=null;}}
pfsw.addEventListener("mousemove",function(){if(fsm)sH();});
cbar.addEventListener("mouseenter",function(){cH();cbar.classList.remove("ch");document.body.style.cursor="";});
cbar.addEventListener("mouseleave",function(){if(fsm)sH();});
cfs.addEventListener("mouseenter",function(){cH();});cfs.addEventListener("mouseleave",function(){if(fsm)sH();});
function tCF(){cfv=!cfv;cfs.style.display=cfv?"flex":"none";bcht.style.opacity=cfv?"1":"0.45";}
bcht.onclick=tCF;cfsx.onclick=tCF;
document.addEventListener("keydown",function(e){
var tag=document.activeElement.tagName;
if(tag==="INPUT"||tag==="TEXTAREA"||tag==="SELECT")return;
if(e.key==="f"||e.key==="F"){e.preventDefault();tFS();}
else if(e.key===" "||e.key==="k"||e.key==="K"){e.preventDefault();vid.paused?vid.play():vid.pause();}
else if(e.key==="m"||e.key==="M"){e.preventDefault();vid.muted=!vid.muted;mup.setAttribute("d",vid.muted?IMU:IVO);vol.value=vid.muted?0:vid.volume;}
else if(e.key==="ArrowUp"){e.preventDefault();vid.volume=Math.min(1,vid.volume+0.1);vol.value=vid.volume;}
else if(e.key==="ArrowDown"){e.preventDefault();vid.volume=Math.max(0,vid.volume-0.1);vol.value=vid.volume;}
else if((e.key==="c"||e.key==="C")&&fsm){e.preventDefault();tCF();}
else if(e.key==="Escape"&&fsm){e.preventDefault();xFS();}
});
uname.value=localStorage.getItem("sc_un")||"";
socket.on("connect",function(){socket.emit("join_stream",{stream_id:SID,username:uname.value.trim()||"Anonyme"});});
socket.on("connect_error",function(e){console.warn("Socket:",e.message);});
socket.on("chat_history",function(d){d.messages.forEach(function(m){aM(chatm,m,false);});chatm.scrollTop=chatm.scrollHeight;d.messages.slice(-30).forEach(function(m){aM(cfsm,m,false);});cfsm.scrollTop=cfsm.scrollHeight;});
socket.on("new_chat_msg",function(m){aM(chatm,m,true);chatm.scrollTop=chatm.scrollHeight;aM(cfsm,m,true);cfsm.scrollTop=cfsm.scrollHeight;if(ntog.checked&&m.username!==(uname.value.trim()||"Anonyme"))pN(m.username,m.text);});
socket.on("system_msg",function(d){[chatm,cfsm].forEach(function(el){var div=document.createElement("div");div.className="smsg";div.textContent=d.text;el.appendChild(div);el.scrollTop=el.scrollHeight;});});
socket.on("viewer_count",function(d){vc.textContent=d.count+" viewers";});
socket.on("stream_ended",function(d){if(d.stream_id===SID)showO("Stream termine");});
function aM(c,m,an){var d=document.createElement("div");d.className="cm"+(an?" cmn":"");
var t=new Date(m.ts*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});
d.innerHTML='<span class="ct">'+t+'</span><span class="cu">'+esc(m.username)+'</span><span class="cx">'+esc(m.text)+'</span>';
c.appendChild(d);while(c.children.length>200)c.removeChild(c.firstChild);}
function esc(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}
function sM(i,u){var t=i.value.trim();if(!t)return;var n=u.value.trim()||"Anonyme";
localStorage.setItem("sc_un",n);uname.value=n;fsun.value=n;
socket.emit("chat_msg",{stream_id:SID,username:n,text:t});i.value="";}
cs.onclick=function(){sM(ci,uname);};ci.addEventListener("keypress",function(e){if(e.key==="Enter")sM(ci,uname);});
fscs.onclick=function(){sM(fsci,fsun);};fsci.addEventListener("keypress",function(e){if(e.key==="Enter")sM(fsci,fsun);});
uname.addEventListener("change",function(){fsun.value=uname.value;});
fsun.addEventListener("change",function(){uname.value=fsun.value;});
function pN(u,t){try{ns.currentTime=0;ns.play().catch(function(){});}catch(e){}
if("Notification"in window&&Notification.permission==="granted")new Notification("Message de "+u,{body:t,silent:true});}
if("Notification"in window&&Notification.permission==="default")Notification.requestPermission();
"""

if __name__=="__main__":
    import sys
    port=int(os.environ.get("PORT",5000))
    print(f"StreamCaster http://0.0.0.0:{port}")
    socketio.run(app,host="0.0.0.0",port=port,debug=False,
        use_reloader=False,log_output=True,allow_unsafe_werkzeug=True)
