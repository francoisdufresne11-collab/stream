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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0f172a">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Stream Ninja Live</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            -webkit-tap-highlight-color: transparent;
        }

        header {
            padding: 8px 12px;
            background: #1e293b;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            min-height: 50px;
            flex-shrink: 0;
        }

        .logo {
            font-size: 1rem;
            font-weight: bold;
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }

        .header-btns {
            display: flex;
            gap: 6px;
            align-items: center;
        }

        .btn {
            padding: 8px 12px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
            -webkit-user-select: none;
            user-select: none;
        }

        .btn-broadcast { background: #0284c7; color: white; }
        .btn-broadcast:hover:not(:disabled) { background: #0369a1; }
        .btn-screen { background: #7c3aed; color: white; }
        .btn-screen:hover:not(:disabled) { background: #6d28d9; }
        .btn-capture { background: #059669; color: white; }
        .btn-capture:hover:not(:disabled) { background: #047857; }
        .btn-stop { background: #ef4444; color: white; }
        .btn-stop:hover { background: #dc2626; }
        .btn-fullscreen { background: #334155; color: white; }
        .btn-fullscreen:hover { background: #475569; }
        .btn-share { background: #0ea5e9; color: white; }
        .btn-chat-toggle { background: #6366f1; color: white; }

        .btn-disabled {
            background: #475569 !important;
            color: #94a3b8 !important;
            cursor: not-allowed !important;
            opacity: 0.7;
        }

        .quality-select {
            padding: 8px 10px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #ffffff;
            font-size: 0.8rem;
            outline: none;
            cursor: pointer;
        }

        .quality-select:focus { border-color: #38bdf8; }

        /* Toolbar diffuseur */
        .broadcast-toolbar {
            padding: 8px 12px;
            background: #1e293b;
            display: none;
            gap: 6px;
            align-items: center;
            border-bottom: 1px solid #334155;
            flex-wrap: wrap;
            justify-content: center;
            flex-shrink: 0;
        }

        .broadcast-toolbar.active { display: flex; }

        /* Layout principal */
        .main-layout {
            display: flex;
            flex: 1;
            min-height: 0;
            position: relative;
        }

        .video-container {
            flex: 1;
            background: #000;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            min-width: 0;
        }

        video {
            width: 100%;
            height: 100%;
            object-fit: contain;
            background: #000;
        }

        .status-overlay {
            position: absolute;
            top: 8px;
            left: 8px;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            padding: 6px 10px;
            border-radius: 16px;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 6px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 10;
        }

        .viewers-count {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            padding: 6px 10px;
            border-radius: 16px;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 6px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 10;
        }

        .dot { width: 8px; height: 8px; border-radius: 50%; background: #64748b; }
        .dot.live {
            background: #22c55e;
            box-shadow: 0 0 8px #22c55e;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 8px #22c55e; }
            50% { box-shadow: 0 0 16px #22c55e; }
        }

        .source-label {
            position: absolute;
            bottom: 8px;
            left: 8px;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 0.7rem;
            z-index: 10;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Chat Panel - Desktop */
        .chat-panel {
            width: 320px;
            background: #1e293b;
            border-left: 1px solid #334155;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }

        .chat-header {
            padding: 12px;
            background: #0f172a;
            font-weight: 600;
            border-bottom: 1px solid #334155;
            font-size: 0.9rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        .chat-close {
            display: none;
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 1.2rem;
            cursor: pointer;
            padding: 4px 8px;
        }

        .chat-messages {
            flex: 1;
            padding: 12px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-height: 0;
            -webkit-overflow-scrolling: touch;
        }

        .chat-msg {
            background: #334155;
            padding: 8px 12px;
            border-radius: 10px;
            word-break: break-word;
            font-size: 0.85rem;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .chat-msg .author {
            font-weight: bold;
            color: #38bdf8;
            margin-bottom: 2px;
            font-size: 0.75rem;
        }

        .chat-input-box {
            padding: 10px;
            background: #0f172a;
            border-top: 1px solid #334155;
            display: flex;
            gap: 6px;
            flex-shrink: 0;
        }

        .chat-input-box input {
            flex: 1;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #ffffff;
            outline: none;
            font-size: 0.85rem;
            -webkit-appearance: none;
        }

        .chat-input-box input:focus { border-color: #38bdf8; }

        .chat-input-box .btn { padding: 10px 14px; }

        /* Notification toast */
        .notification-toast {
            position: fixed;
            top: 60px;
            right: 12px;
            background: #1e293b;
            border: 1px solid #38bdf8;
            border-radius: 12px;
            padding: 10px 16px;
            z-index: 1000;
            animation: slideIn 0.4s ease, fadeOut 0.4s ease 3s forwards;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            max-width: 280px;
            font-size: 0.85rem;
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        @keyframes fadeOut {
            to { opacity: 0; transform: translateY(-20px); }
        }

        /* Share box */
        .share-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 999;
            display: none;
        }

        .share-box {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px;
            z-index: 1000;
            box-shadow: 0 16px 64px rgba(0,0,0,0.6);
            display: none;
            width: 90%;
            max-width: 400px;
        }

        .share-box h3 { margin-bottom: 12px; color: #38bdf8; font-size: 1rem; }

        .share-box .link-box {
            background: #0f172a;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #334155;
            word-break: break-all;
            margin-bottom: 12px;
            font-family: monospace;
            font-size: 0.8rem;
        }

        /* Badge notification chat mobile */
        .chat-badge {
            position: absolute;
            top: -4px;
            right: -4px;
            background: #ef4444;
            color: white;
            border-radius: 50%;
            width: 18px;
            height: 18px;
            font-size: 0.65rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            display: none;
        }

        .btn-chat-wrapper {
            position: relative;
            display: none;
        }

        /* ========== MOBILE ========== */
        @media (max-width: 768px) {
            header {
                padding: 6px 10px;
                min-height: 44px;
            }

            .logo { font-size: 0.9rem; }

            .main-layout {
                flex-direction: column;
            }

            .video-container {
                flex: none;
                height: 56vw;
                min-height: 200px;
                max-height: 50vh;
            }

            /* Chat prend le reste en mobile */
            .chat-panel {
                width: 100%;
                flex: 1;
                border-left: none;
                border-top: 1px solid #334155;
                display: flex;
            }

            .chat-panel.hidden-mobile {
                display: none;
            }

            .chat-close { display: block; }

            .btn-chat-wrapper { display: block; }

            .broadcast-toolbar .btn span.btn-label {
                display: none;
            }

            .broadcast-toolbar {
                padding: 6px 8px;
                gap: 4px;
            }

            .broadcast-toolbar .btn {
                padding: 8px 10px;
                font-size: 0.75rem;
            }

            .quality-select {
                padding: 6px 8px;
                font-size: 0.75rem;
            }

            .share-box {
                width: 92%;
                padding: 20px;
            }

            .notification-toast {
                top: auto;
                bottom: 12px;
                right: 8px;
                left: 8px;
                max-width: none;
            }
        }

        /* ========== TRES PETIT ECRAN ========== */
        @media (max-width: 380px) {
            .logo { font-size: 0.8rem; }
            .btn { padding: 6px 8px; font-size: 0.7rem; }
            .quality-select { font-size: 0.7rem; padding: 6px; }

            .video-container {
                height: 50vw;
                min-height: 160px;
            }
        }

        /* ========== PAYSAGE MOBILE ========== */
        @media (max-height: 500px) and (orientation: landscape) {
            header { padding: 4px 10px; min-height: 36px; }
            .logo { font-size: 0.8rem; }
            .btn { padding: 5px 8px; font-size: 0.7rem; }

            .main-layout { flex-direction: row; }

            .video-container {
                flex: 1;
                height: auto;
                max-height: none;
            }

            .chat-panel {
                width: 260px;
                border-left: 1px solid #334155;
                border-top: none;
            }

            .chat-panel.hidden-mobile { display: none; }
            .btn-chat-wrapper { display: block; }

            .broadcast-toolbar {
                padding: 4px 8px;
            }

            .broadcast-toolbar .btn {
                padding: 4px 8px;
                font-size: 0.7rem;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">&#127909; Stream Ninja</div>
        <div class="header-btns">
            <div class="btn-chat-wrapper">
                <button class="btn btn-chat-toggle" onclick="toggleChat()">&#128172;</button>
                <span class="chat-badge" id="chatBadge">0</span>
            </div>
            <button class="btn btn-fullscreen" onclick="toggleFullscreen()">&#9974;</button>
            <button class="btn btn-share" onclick="showShareBox()">&#128279;</button>
        </div>
    </header>

    <div class="broadcast-toolbar" id="broadcastToolbar">
        <select id="qualitySelect" class="quality-select" onchange="updateQuality()">
            <option value="auto">Auto</option>
            <option value="1080">1080p</option>
            <option value="720" selected>720p</option>
            <option value="480">480p</option>
            <option value="360">360p</option>
        </select>
        <button id="cameraBtn" class="btn btn-broadcast" onclick="startCamera()">
            &#128247; <span class="btn-label">Camera</span>
        </button>
        <button id="screenBtn" class="btn btn-screen" onclick="startScreen()">
            &#128187; <span class="btn-label">Ecran</span>
        </button>
        <button id="captureBtn" class="btn btn-capture" onclick="startCapture()">
            &#127910; <span class="btn-label">Capture</span>
        </button>
        <button id="stopBtn" class="btn btn-stop" onclick="stopBroadcast()" style="display:none;">
            &#9632; Stop
        </button>
    </div>

    <div class="main-layout" id="streamContainer">
        <div class="video-container">
            <div class="status-overlay">
                <span class="dot" id="statusDot"></span>
                <span id="statusText">Hors ligne</span>
            </div>
            <div class="viewers-count">
                &#128065; <span id="viewersCount">0</span>
            </div>
            <div class="source-label" id="sourceLabel" style="display:none;"></div>
            <video id="remoteVideo" autoplay playsinline></video>
            <video id="localVideo" autoplay playsinline muted style="display:none;"></video>
        </div>

        <div class="chat-panel" id="chatPanel">
            <div class="chat-header">
                <span>&#128172; Chat en direct</span>
                <button class="chat-close" onclick="toggleChat()">&#10005;</button>
            </div>
            <div class="chat-messages" id="chatMessages"></div>
            <div class="chat-input-box">
                <input type="text" id="chatInput" placeholder="Message..."
                       onkeypress="if(event.key==='Enter') sendChatMessage()">
                <button class="btn btn-broadcast" onclick="sendChatMessage()">&#10148;</button>
            </div>
        </div>
    </div>

    <div class="share-overlay" id="shareOverlay" onclick="hideShareBox()"></div>
    <div class="share-box" id="shareBox">
        <h3>&#128279; Partager le live</h3>
        <p style="margin-bottom:10px;color:#94a3b8;font-size:0.85rem;">Envoyez ce lien aux spectateurs :</p>
        <div class="link-box" id="shareLink"></div>
        <button class="btn btn-broadcast" onclick="copyLink()" style="width:100%;justify-content:center;">
            Copier le lien
        </button>
        <br><br>
        <button class="btn btn-stop" onclick="hideShareBox()" style="width:100%;justify-content:center;">
            Fermer
        </button>
    </div>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        const socket = io();
        let localStream = null;
        let isBroadcaster = false;
        let currentBroadcasterId = null;
        let peerConnections = {};
        let viewerPeerConnection = null;
        let currentSource = '';
        let originalTitle = document.title;
        let unreadCount = 0;
        let windowFocused = true;
        let chatVisible = true;
        let mobileChatUnread = 0;

        const cameraBtn = document.getElementById('cameraBtn');
        const screenBtn = document.getElementById('screenBtn');
        const captureBtn = document.getElementById('captureBtn');
        const stopBtn = document.getElementById('stopBtn');
        const localVideo = document.getElementById('localVideo');
        const remoteVideo = document.getElementById('remoteVideo');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const chatMessages = document.getElementById('chatMessages');
        const sourceLabel = document.getElementById('sourceLabel');
        const viewersCount = document.getElementById('viewersCount');
        const chatPanel = document.getElementById('chatPanel');
        const chatBadge = document.getElementById('chatBadge');
        const broadcastToolbar = document.getElementById('broadcastToolbar');

        const userId = 'User_' + Math.floor(Math.random() * 9000 + 1000);

        const rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' }
            ]
        };

        const qualityPresets = {
            '1080': { width: 1920, height: 1080, frameRate: 30 },
            '720':  { width: 1280, height: 720,  frameRate: 30 },
            '480':  { width: 854,  height: 480,  frameRate: 24 },
            '360':  { width: 640,  height: 360,  frameRate: 20 },
            'auto': { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } }
        };

        // Detecter mobile
        function isMobile() {
            return window.innerWidth <= 768;
        }

        // Chat toggle mobile
        function toggleChat() {
            if (chatVisible) {
                chatPanel.classList.add('hidden-mobile');
                chatVisible = false;
            } else {
                chatPanel.classList.remove('hidden-mobile');
                chatVisible = true;
                mobileChatUnread = 0;
                chatBadge.style.display = 'none';
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }

        // Init mobile
        function initMobileLayout() {
            if (isMobile()) {
                chatPanel.classList.remove('hidden-mobile');
                chatVisible = true;
            }
        }

        window.addEventListener('resize', function() {
            if (!isMobile()) {
                chatPanel.classList.remove('hidden-mobile');
                chatVisible = true;
                chatBadge.style.display = 'none';
            }
        });

        // Son notification
        function playNotificationSound() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                oscillator.frequency.setValueAtTime(800, audioCtx.currentTime);
                oscillator.frequency.setValueAtTime(1200, audioCtx.currentTime + 0.1);
                gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
                oscillator.start(audioCtx.currentTime);
                oscillator.stop(audioCtx.currentTime + 0.3);
            } catch(e) {}
        }

        // Notification onglet
        window.addEventListener('focus', function() {
            windowFocused = true;
            unreadCount = 0;
            document.title = originalTitle;
        });

        window.addEventListener('blur', function() {
            windowFocused = false;
        });

        function updateTabNotification() {
            if (!windowFocused) {
                unreadCount++;
                document.title = '(' + unreadCount + ') Nouveau message - Stream Ninja';
            }
        }

        // Toast
        function showToast(message) {
            var existing = document.querySelectorAll('.notification-toast');
            if (existing.length > 3) {
                existing[0].parentNode.removeChild(existing[0]);
            }
            var toast = document.createElement('div');
            toast.className = 'notification-toast';
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(function() {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 3500);
        }

        // Qualite
        function getQualityConstraints() {
            var quality = document.getElementById('qualitySelect').value;
            return qualityPresets[quality] || qualityPresets['720'];
        }

        function updateQuality() {
            if (!isBroadcaster || !localStream) return;
            var quality = getQualityConstraints();
            var videoTrack = localStream.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.applyConstraints({
                    width: quality.width,
                    height: quality.height,
                    frameRate: quality.frameRate
                }).catch(function(e) { console.log('Qualite non supportee:', e); });
            }
        }

        // Sources
        async function startCamera() {
            var quality = getQualityConstraints();
            try {
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: quality.width, height: quality.height, frameRate: quality.frameRate },
                    audio: true
                });
                currentSource = 'Camera';
                startBroadcastWithStream();
            } catch (err) {
                alert('Erreur camera : ' + err.message);
            }
        }

        async function startScreen() {
            var quality = getQualityConstraints();
            try {
                var screenStream = await navigator.mediaDevices.getDisplayMedia({
                    video: { width: quality.width, height: quality.height, frameRate: quality.frameRate },
                    audio: true
                });

                try {
                    var micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    var audioCtx = new AudioContext();
                    var dest = audioCtx.createMediaStreamDestination();

                    if (screenStream.getAudioTracks().length > 0) {
                        audioCtx.createMediaStreamSource(screenStream).connect(dest);
                    }
                    audioCtx.createMediaStreamSource(micStream).connect(dest);

                    localStream = new MediaStream([
                        ...screenStream.getVideoTracks(),
                        ...dest.stream.getAudioTracks()
                    ]);
                } catch(e) {
                    localStream = screenStream;
                }

                currentSource = 'Ecran';

                screenStream.getVideoTracks()[0].onended = function() {
                    stopBroadcast();
                };

                startBroadcastWithStream();
            } catch (err) {
                alert('Partage ecran refuse : ' + err.message);
            }
        }

        async function startCapture() {
            var quality = getQualityConstraints();
            try {
                var devices = await navigator.mediaDevices.enumerateDevices();
                var videoDevices = devices.filter(function(d) { return d.kind === 'videoinput'; });

                if (videoDevices.length === 0) {
                    alert('Aucun peripherique video detecte');
                    return;
                }

                var captureDevice = videoDevices[videoDevices.length - 1];

                for (var i = 0; i < videoDevices.length; i++) {
                    var label = videoDevices[i].label.toLowerCase();
                    if (label.indexOf('capture') !== -1 ||
                        label.indexOf('cam link') !== -1 ||
                        label.indexOf('elgato') !== -1 ||
                        label.indexOf('avermedia') !== -1 ||
                        label.indexOf('hdmi') !== -1 ||
                        label.indexOf('usb video') !== -1) {
                        captureDevice = videoDevices[i];
                        break;
                    }
                }

                localStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        deviceId: { exact: captureDevice.deviceId },
                        width: quality.width,
                        height: quality.height,
                        frameRate: quality.frameRate
                    },
                    audio: true
                });

                currentSource = 'Capture (' + (captureDevice.label || 'Inconnu') + ')';
                startBroadcastWithStream();
            } catch (err) {
                alert('Erreur carte de capture : ' + err.message);
            }
        }

        function startBroadcastWithStream() {
            localVideo.srcObject = localStream;
            localVideo.style.display = 'block';
            remoteVideo.style.display = 'none';
            sourceLabel.textContent = currentSource;
            sourceLabel.style.display = 'block';
            isBroadcaster = true;

            cameraBtn.style.display = 'none';
            screenBtn.style.display = 'none';
            captureBtn.style.display = 'none';
            stopBtn.style.display = 'flex';

            socket.emit('start_broadcast', { source: currentSource });
        }

        function stopBroadcast() {
            socket.emit('stop_broadcast');
            stopLocalStream();
        }

        function stopLocalStream() {
            if (localStream) {
                localStream.getTracks().forEach(function(track) { track.stop(); });
                localStream = null;
            }
            Object.values(peerConnections).forEach(function(pc) { pc.close(); });
            peerConnections = {};
            localVideo.style.display = 'none';
            localVideo.srcObject = null;
            remoteVideo.style.display = 'block';
            sourceLabel.style.display = 'none';
            isBroadcaster = false;
            currentSource = '';

            cameraBtn.style.display = 'flex';
            screenBtn.style.display = 'flex';
            captureBtn.style.display = 'flex';
            stopBtn.style.display = 'none';
        }

        // Socket
        socket.on('broadcaster_status', function(data) {
            currentBroadcasterId = data.broadcaster_id;
            viewersCount.textContent = data.viewers || 0;

            if (currentBroadcasterId) {
                if (currentBroadcasterId === socket.id) {
                    statusDot.className = 'dot live';
                    statusText.textContent = 'En direct';
                    broadcastToolbar.classList.add('active');
                } else {
                    cameraBtn.className = 'btn btn-disabled';
                    cameraBtn.disabled = true;
                    screenBtn.className = 'btn btn-disabled';
                    screenBtn.disabled = true;
                    captureBtn.className = 'btn btn-disabled';
                    captureBtn.disabled = true;
                    statusDot.className = 'dot live';
                    statusText.textContent = 'En direct';
                    broadcastToolbar.classList.remove('active');
                    if (data.source) {
                        sourceLabel.textContent = data.source;
                        sourceLabel.style.display = 'block';
                    }
                    socket.emit('request_stream');
                }
            } else {
                cameraBtn.className = 'btn btn-broadcast';
                cameraBtn.disabled = false;
                screenBtn.className = 'btn btn-screen';
                screenBtn.disabled = false;
                captureBtn.className = 'btn btn-capture';
                captureBtn.disabled = false;
                statusDot.className = 'dot';
                statusText.textContent = 'Hors ligne';
                sourceLabel.style.display = 'none';
                broadcastToolbar.classList.add('active');

                if (isBroadcaster) {
                    stopLocalStream();
                } else if (viewerPeerConnection) {
                    viewerPeerConnection.close();
                    viewerPeerConnection = null;
                    remoteVideo.srcObject = null;
                }
            }
        });

        socket.on('viewers_count', function(data) {
            viewersCount.textContent = data.count;
        });

        // WebRTC
        socket.on('new_viewer', async function(data) {
            if (!isBroadcaster || !localStream) return;
            var viewerId = data.viewer_id;
            var pc = new RTCPeerConnection(rtcConfig);
            peerConnections[viewerId] = pc;

            localStream.getTracks().forEach(function(track) { pc.addTrack(track, localStream); });

            pc.onicecandidate = function(e) {
                if (e.candidate) socket.emit('candidate', { target: viewerId, candidate: e.candidate });
            };

            var offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            socket.emit('offer', { target: viewerId, offer: offer });
        });

        socket.on('offer', async function(data) {
            viewerPeerConnection = new RTCPeerConnection(rtcConfig);
            viewerPeerConnection.ontrack = function(e) { remoteVideo.srcObject = e.streams[0]; };
            viewerPeerConnection.onicecandidate = function(e) {
                if (e.candidate) socket.emit('candidate', { target: data.broadcaster_id, candidate: e.candidate });
            };

            await viewerPeerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            var answer = await viewerPeerConnection.createAnswer();
            await viewerPeerConnection.setLocalDescription(answer);
            socket.emit('answer', { target: data.broadcaster_id, answer: answer });
        });

        socket.on('answer', async function(data) {
            var pc = peerConnections[data.viewer_id];
            if (pc) await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
        });

        socket.on('candidate', async function(data) {
            var pc = isBroadcaster ? peerConnections[data.from] : viewerPeerConnection;
            if (pc && data.candidate) {
                try { await pc.addIceCandidate(new RTCIceCandidate(data.candidate)); }
                catch (e) { console.error('Erreur ICE:', e); }
            }
        });

        socket.on('viewer_disconnected', function(data) {
            if (peerConnections[data.viewer_id]) {
                peerConnections[data.viewer_id].close();
                delete peerConnections[data.viewer_id];
            }
        });

        // Chat
        function sendChatMessage() {
            var input = document.getElementById('chatInput');
            var message = input.value.trim();
            if (message) {
                socket.emit('chat_message', { user: userId, text: message });
                input.value = '';
            }
        }

        socket.on('chat_message', function(data) {
            var msgEl = document.createElement('div');
            msgEl.className = 'chat-msg';
            msgEl.innerHTML = '<div class="author">' + escapeHtml(data.user) + '</div><div>' + escapeHtml(data.text) + '</div>';
            chatMessages.appendChild(msgEl);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            if (data.user !== userId) {
                playNotificationSound();
                updateTabNotification();

                if (isMobile() && !chatVisible) {
                    mobileChatUnread++;
                    chatBadge.textContent = mobileChatUnread;
                    chatBadge.style.display = 'flex';
                } else {
                    showToast(data.user + ': ' + data.text.substring(0, 40));
                }
            }
        });

        function escapeHtml(str) {
            var div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Partage
        function showShareBox() {
            document.getElementById('shareLink').textContent = window.location.href;
            document.getElementById('shareBox').style.display = 'block';
            document.getElementById('shareOverlay').style.display = 'block';
        }

        function hideShareBox() {
            document.getElementById('shareBox').style.display = 'none';
            document.getElementById('shareOverlay').style.display = 'none';
        }

        function copyLink() {
            navigator.clipboard.writeText(window.location.href).then(function() {
                showToast('Lien copie !');
            });
        }

        // Plein ecran
        function toggleFullscreen() {
            var elem = document.getElementById('streamContainer');
            if (!document.fullscreenElement) {
                if (elem.requestFullscreen) elem.requestFullscreen();
                else if (elem.webkitRequestFullscreen) elem.webkitRequestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        }

        // Init
        initMobileLayout();
        broadcastToolbar.classList.add('active');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

viewers = set()
broadcast_source = ''

@socketio.on('connect')
def handle_connect():
    global broadcaster_id, broadcast_source
    viewers.add(request.sid)
    emit('broadcaster_status', {
        'broadcaster_id': broadcaster_id,
        'viewers': len(viewers),
        'source': broadcast_source
    })
    emit('viewers_count', {'count': len(viewers)}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    global broadcaster_id, broadcast_source
    viewers.discard(request.sid)

    if request.sid == broadcaster_id:
        broadcaster_id = None
        broadcast_source = ''
        emit('broadcaster_status', {
            'broadcaster_id': None,
            'viewers': len(viewers),
            'source': ''
        }, broadcast=True)
    else:
        if broadcaster_id:
            emit('viewer_disconnected', {'viewer_id': request.sid}, room=broadcaster_id)

    emit('viewers_count', {'count': len(viewers)}, broadcast=True)

@socketio.on('start_broadcast')
def handle_start_broadcast(data=None):
    global broadcaster_id, broadcast_source
    if broadcaster_id is None:
        broadcaster_id = request.sid
        broadcast_source = data.get('source', 'Camera') if data else 'Camera'
        emit('broadcaster_status', {
            'broadcaster_id': broadcaster_id,
            'viewers': len(viewers),
            'source': broadcast_source
        }, broadcast=True)

@socketio.on('stop_broadcast')
def handle_stop_broadcast():
    global broadcaster_id, broadcast_source
    if request.sid == broadcaster_id:
        broadcaster_id = None
        broadcast_source = ''
        emit('broadcaster_status', {
            'broadcaster_id': None,
            'viewers': len(viewers),
            'source': ''
        }, broadcast=True)

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
