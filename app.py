import os,sys,time,uuid,shutil,secrets,threading,datetime
from pathlib import Path
from flask import Flask,render_template,request,jsonify,send_from_directory,Response,redirect,url_for,session,flash
from flask_socketio import SocketIO,emit,join_room,leave_room

app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"]=500*1024*1024
app.config["ADMIN_PASSWORD"]=os.environ.get("ADMIN_PASSWORD","admin2026")

socketio=SocketIO(app,cors_allowed_origins="*",async_mode="threading",
    ping_timeout=60,ping_interval=20,max_http_buffer_size=10_000_000,
    logger=False,engineio_logger=False)

BASE_DIR=Path(__file__).resolve().parent
STREAMS_DIR=BASE_DIR/"streams"
STREAMS_DIR.mkdir(exist_ok=True)
active_streams={}
stream_viewers={}
chat_history={}
server_stats={"total_streams":0,"total_messages":0,"started":time.time()}
_lock=threading.Lock()
QUALITIES={"1080p":{"res":"1920x1080","vb":"5000k","ab":"192k"},"720p":{"res":"1280x720","vb":"2500k","ab":"128k"},"480p":{"res":"854x480","vb":"1200k","ab":"96k"},"360p":{"res":"640x360","vb":"600k","ab":"64k"}}

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
            lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={bw[q]},RESOLUTION={rs[q]},NAME=\"{q}\"")
            lines.append(f"{q}.m3u8")
    if len(lines)>1:(sdir/"master.m3u8").write_text("\n".join(lines)+"\n",encoding="utf-8")

def _cleanup(sid):
    with _lock:
        sdir=STREAMS_DIR/sid
        if sdir.exists():shutil.rmtree(sdir,ignore_errors=True)
        active_streams.pop(sid,None);stream_viewers.pop(sid,None);chat_history.pop(sid,None)

@app.template_filter("ts")
def _ts(v):
    try:return datetime.datetime.fromtimestamp(float(v)).strftime("%H:%M:%S")
    except:return "?"

@app.errorhandler(404)
def e404(e):return render_template("error.html",code=404,msg="Page introuvable"),404
@app.errorhandler(500)
def e500(e):return render_template("error.html",code=500,msg="Erreur interne"),500
@app.errorhandler(413)
def e413(e):return render_template("error.html",code=413,msg="Fichier trop volumineux"),413

@app.route("/")
def index():return render_template("index.html",streams=list(active_streams.values()))
@app.route("/broadcast")
def broadcast_page():return render_template("broadcast.html")
@app.route("/watch/<sid>")
def watch_page(sid):
    s=active_streams.get(sid)
    if not s:return redirect(url_for("index"))
    return render_template("watch.html",stream_id=sid,stream=s)

@app.route("/admin",methods=["GET","POST"])
def admin():
    if request.method=="POST":
        if request.form.get("password","")==app.config["ADMIN_PASSWORD"]:
            session["admin"]=True;return redirect(url_for("admin"))
        flash("Mot de passe incorrect")
    if not session.get("admin"):return render_template("admin_login.html")
    stats={"streams":len(active_streams),"viewers":sum(len(v) for v in stream_viewers.values()),
           "messages":server_stats["total_messages"],"total_streams":server_stats["total_streams"],
           "uptime":_uptime(),"active":list(active_streams.values())}
    return render_template("admin.html",stats=stats)

@app.route("/admin/logout")
def admin_logout():session.pop("admin",None);return redirect(url_for("index"))

@app.route("/admin/kick/<sid>",methods=["POST"])
def admin_kick(sid):
    if not session.get("admin"):return jsonify({"error":"non autorise"}),403
    _cleanup(sid);socketio.emit("stream_ended",{"stream_id":sid})
    flash(f"Stream {sid} arrete");return redirect(url_for("admin"))

@app.route("/api/streams")
def api_streams():return jsonify(list(active_streams.values()))

@app.route("/api/stats")
def api_stats():
    return jsonify({"streams":len(active_streams),"viewers":sum(len(v) for v in stream_viewers.values()),
        "total_streams":server_stats["total_streams"],"total_messages":server_stats["total_messages"],"uptime":_uptime()})

@app.route("/api/stream/create",methods=["POST"])
def api_create():
    data=request.get_json(silent=True) or {};sid=uuid.uuid4().hex[:8];title=str(data.get("title","Stream"))[:80]
    (STREAMS_DIR/sid).mkdir(parents=True,exist_ok=True)
    meta={"id":sid,"title":title,"created":time.time(),"status":"live","viewers":0}
    with _lock:
        active_streams[sid]=meta;stream_viewers[sid]=set();chat_history[sid]=[];server_stats["total_streams"]+=1
    socketio.emit("stream_created",meta);return jsonify({"stream_id":sid,"status":"ok"})

@app.route("/api/stream/<sid>/upload",methods=["POST"])
def api_upload(sid):
    if sid not in active_streams:return jsonify({"error":"stream inconnu"}),404
    raw=request.headers.get("X-Filename","")
    if not raw:return jsonify({"error":"X-Filename manquant"}),400
    fname=Path(raw).name
    if not fname.endswith((".m3u8",".ts")):return jsonify({"error":"type non autorise"}),400
    (STREAMS_DIR/sid/fname).write_bytes(request.data)
    if fname.endswith(".m3u8"):_master(sid)
    return jsonify({"ok":True,"file":fname})

@app.route("/api/stream/<sid>/stop",methods=["POST"])
def api_stop(sid):
    if sid not in active_streams:return jsonify({"error":"inconnu"}),404
    _cleanup(sid);socketio.emit("stream_ended",{"stream_id":sid});return jsonify({"status":"stopped"})

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
    emit("system_msg",{"text":f"Bonjour {u}","ts":time.time()},to=sid)
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
        chat_history.setdefault(sid,[]).append(msg);chat_history[sid]=chat_history[sid][-300:]
        server_stats["total_messages"]+=1
    emit("new_chat_msg",msg,to=sid)

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"StreamCaster http://0.0.0.0:{port}  Python {sys.version.split()[0]}")
    socketio.run(app,host="0.0.0.0",port=port,debug=False,use_reloader=False,
        log_output=True,allow_unsafe_werkzeug=True)
