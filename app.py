import os
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stream_ninja_secret_key_123')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
broadcaster_id = None

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Studio Live</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header {
            padding: 12px 24px;
            background: #1e293b;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
        }

        .logo {
            font-size: 1.2rem;
            font-weight: bold;
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .controls {
            display: flex;
            gap: 12px;
            align-items: center;
        }

        .btn {
            padding: 10px 18px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-broadcast { background: #0284c7; color: white; }
        .btn-broadcast:hover:not(:disabled) { background: #0369a1; }

        .btn-stop { background: #ef4444; color: white; }
        .btn-stop:hover { background: #dc2626; }

        .btn-disabled {
            background: #475569 !important;
            color: #94a3b8 !important;
            cursor: not-allowed !important;
            opacity: 0.7;
        }

        .btn-fullscreen { background: #334155; color: white; }
        .btn-fullscreen:hover { background: #475569; }

        .main-layout {
            display: flex;
            flex: 1;
            height: calc(100vh - 65px);
        }

        .video-container {
            flex: 1;
            background: #000;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        video {
            width: 100%;
            height: 100%;
            object-fit: contain;
            background: #000;
        }

        .status-overlay {
            position: absolute;
            top: 16px;
            left: 16px;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(8px);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .dot { width: 10px; height: 10px; border-radius: 50%; background: #64748b; }
        .dot.live { background: #22c55e; box-shadow: 0 0 8px #22c55e; }

        .chat-panel {
            width: 340px;
            background: #1e293b;
            border-left: 1px solid #334155;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            padding: 16px;
            background: #0f172a;
            font-weight: 600;
            border-bottom: 1px solid #334155;
            font-size: 1rem;
        }

        .chat-messages {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .chat-msg {
            background: #334155;
            padding: 10px 14px;
            border-radius: 10px;
            word-break: break-word;
            font-size: 0.9rem;
        }

        .chat-msg .author {
            font-weight: bold;
            color: #38bdf8;
            margin-bottom: 2px;
            font-size: 0.8rem;
        }

        .chat-input-box {
            padding: 16px;
            background: #0f172a;
            border-top: 1px solid #334155;
            display: flex;
            gap: 8px;
        }

        .chat-input-box input {
            flex: 1;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #ffffff;
            outline: none;
            font-size: 0.9rem;
        }

        .chat-input-box input:focus { border-color: #38bdf8; }
    </style>
</head>
<body>
    <header>
        <div class="logo">🎥 Stream Ninja</div>
        <div class="controls">
            <button id="broadcastBtn" class="btn btn-broadcast" onclick="handleBroadcastToggle()">
                🔴 Diffuser en direct
            </button>
            <button id="fullscreenBtn" class="btn btn-fullscreen" onclick="toggleFullscreen()">
                ⛶ Plein écran
            </button>
        </div>
    </header>

    <div class="main-layout" id="streamContainer">
        <div class="video-container">
            <div class="status-overlay">
                <span class="dot" id="statusDot"></span>
                <span id="statusText">Hors ligne</span>
            </div>
            
            <video id="remoteVideo" autoplay playsinline></video>
            <video id="localVideo" autoplay playsinline muted style="display: none;"></video>
        </div>

        <div class="chat-panel">
            <div class="chat-header">💬 Chat en direct</div>
            <div class="chat-messages" id="chatMessages"></div>
            <div class="chat-input-box">
                <input type="text" id="chatInput" placeholder="Message..." onkeypress="if(event.key==='Enter') sendChatMessage()">
                <button class="btn btn-broadcast" onclick="sendChatMessage()">Envoyer</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        const socket = io();
        let localStream = null;
        let isBroadcaster = false;
        let currentBroadcasterId = null;
        let peerConnections = {}; 
        let viewerPeerConnection = null; 

        const broadcastBtn = document.getElementById('broadcastBtn');
        const localVideo = document.getElementById('localVideo');
        const remoteVideo = document.getElementById('remoteVideo');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const chatMessages = document.getElementById('chatMessages');

        const userId = 'User_' + Math.floor(Math.random() * 1000);

        const rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        socket.on('broadcaster_status', (data) => {
            currentBroadcasterId = data.broadcaster_id;

            if (currentBroadcasterId) {
                if (currentBroadcasterId === socket.id) {
                    broadcastBtn.textContent = '⏹ Arrêter le direct';
                    broadcastBtn.className = 'btn btn-stop';
                    broadcastBtn.disabled = false;
                    statusDot.className = 'dot live';
                    statusText.textContent = 'En direct (Votre caméra)';
                } else {
                    broadcastBtn.textContent = '🔒 Diffusion en cours';
                    broadcastBtn.className = 'btn btn-disabled';
                    broadcastBtn.disabled = true;
                    statusDot.className = 'dot live';
                    statusText.textContent = 'En direct';
                    socket.emit('request_stream');
                }
            } else {
                broadcastBtn.textContent = '🔴 Diffuser en direct';
                broadcastBtn.className = 'btn btn-broadcast';
                broadcastBtn.disabled = false;
                statusDot.className = 'dot';
                statusText.textContent = 'Hors ligne';

                if (isBroadcaster) {
                    stopLocalStream();
                } else if (viewerPeerConnection) {
                    viewerPeerConnection.close();
                    viewerPeerConnection = null;
                    remoteVideo.srcObject = null;
                }
            }
        });

        async function handleBroadcastToggle() {
            if (isBroadcaster) {
                socket.emit('stop_broadcast');
            } else {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    localVideo.srcObject = localStream;
                    localVideo.style.display = 'block';
                    remoteVideo.style.display = 'none';
                    isBroadcaster = true;
                    socket.emit('start_broadcast');
                } catch (err) {
                    alert('Accès caméra/micro refusé : ' + err.message);
                }
            }
        }

        function stopLocalStream() {
            if (localStream) {
                localStream.getTracks().forEach(track => track.stop());
                localStream = null;
            }
            Object.values(peerConnections).forEach(pc => pc.close());
            peerConnections = {};
            localVideo.style.display = 'none';
            remoteVideo.style.display = 'block';
            isBroadcaster = false;
        }

        socket.on('new_viewer', async (data) => {
            if (!isBroadcaster || !localStream) return;
            const viewerId = data.viewer_id;
            const pc = new RTCPeerConnection(rtcConfig);
            peerConnections[viewerId] = pc;

            localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

            pc.onicecandidate = (e) => {
                if (e.candidate) socket.emit('candidate', { target: viewerId, candidate: e.candidate });
            };

            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            socket.emit('offer', { target: viewerId, offer: offer });
        });

        socket.on('offer', async (data) => {
            viewerPeerConnection = new RTCPeerConnection(rtcConfig);
            viewerPeerConnection.ontrack = (e) => { remoteVideo.srcObject = e.streams[0]; };
            viewerPeerConnection.onicecandidate = (e) => {
                if (e.candidate) socket.emit('candidate', { target: data.broadcaster_id, candidate: e.candidate });
            };

            await viewerPeerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await viewerPeerConnection.createAnswer();
            await viewerPeerConnection.setLocalDescription(answer);

            socket.emit('answer', { target: data.broadcaster_id, answer: answer });
        });

        socket.on('answer', async (data) => {
            const pc = peerConnections[data.viewer_id];
            if (pc) await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
        });

        socket.on('candidate', async (data) => {
            const pc = isBroadcaster ? peerConnections[data.from] : viewerPeerConnection;
            if (pc && data.candidate) {
                try { await pc.addIceCandidate(new RTCIceCandidate(data.candidate)); } 
                catch (e) { console.error('Erreur ICE:', e); }
            }
        });

        function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (message) {
                socket.emit('chat_message', { user: userId, text: message });
                input.value = '';
            }
        }

        socket.on('chat_message', (data) => {
            const msgEl = document.createElement('div');
            msgEl.className = 'chat-msg';
            msgEl.innerHTML = `<div class="author">${data.user}</div><div>${escapeHtml(data.text)}</div>`;
            chatMessages.appendChild(msgEl);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        function toggleFullscreen() {
            const elem = document.getElementById('streamContainer');
            if (!document.fullscreenElement) {
                if (elem.requestFullscreen) elem.requestFullscreen();
                else if (elem.webkitRequestFullscreen) elem.webkitRequestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@socketio.on('connect')
def handle_connect():
    global broadcaster_id
    emit('broadcaster_status', {'broadcaster_id': broadcaster_id})

@socketio.on('disconnect')
def handle_disconnect():
    global broadcaster_id
    if request.sid == broadcaster_id:
        broadcaster_id = None
        emit('broadcaster_status', {'broadcaster_id': None}, broadcast=True)

@socketio.on('start_broadcast')
def handle_start_broadcast():
    global broadcaster_id
    if broadcaster_id is None:
        broadcaster_id = request.sid
        emit('broadcaster_status', {'broadcaster_id': broadcaster_id}, broadcast=True)

@socketio.on('stop_broadcast')
def handle_stop_broadcast():
    global broadcaster_id
    if request.sid == broadcaster_id:
        broadcaster_id = None
        emit('broadcaster_status', {'broadcaster_id': None}, broadcast=True)

@socketio.on('request_stream')
def handle_request_stream():
    global broadcaster_id
    if broadcaster_id:
        emit('new_viewer', {'viewer_id': request.sid}, room=broadcaster_id)

@socketio.on('offer')
def handle_offer(data):
    emit('offer', {'offer': data['offer'], 'broadcaster_id': request.sid}, room=data['target'])

@socketio.on('answer')
def handle_answer(data):
    emit('answer', {'answer': data['answer'], 'viewer_id': request.sid}, room=data['target'])

@socketio.on('candidate')
def handle_candidate(data):
    emit('candidate', {'candidate': data['candidate'], 'from': request.sid}, room=data['target'])

@socketio.on('chat_message')
def handle_chat_message(data):
    emit('chat_message', data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port)
