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
            background: #000;
            color: #f8fafc;
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            -webkit-tap-highlight-color: transparent;
        }

        /* HEADER */
        header {
            padding: 6px 12px;
            background: rgba(15, 23, 42, 0.95);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            min-height: 44px;
            flex-shrink: 0;
            z-index: 50;
        }

        .logo {
            font-size: 0.95rem;
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
            padding: 7px 12px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
            -webkit-user-select: none;
            user-select: none;
            touch-action: manipulation;
        }

        .btn:active { transform: scale(0.95); }

        .btn-broadcast { background: #0284c7; color: white; }
        .btn-screen { background: #7c3aed; color: white; }
        .btn-capture { background: #059669; color: white; }
        .btn-stop { background: #ef4444; color: white; }
        .btn-fullscreen { background: #334155; color: white; }
        .btn-share { background: #0ea5e9; color: white; }
        .btn-chat-toggle { background: #6366f1; color: white; }
        .btn-sm { padding: 6px 10px; font-size: 0.75rem; }

        .btn-disabled {
            background: #475569 !important;
            color: #94a3b8 !important;
            cursor: not-allowed !important;
            opacity: 0.7;
        }

        .quality-select {
            padding: 7px 10px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #fff;
            font-size: 0.8rem;
            outline: none;
        }

        /* TOOLBAR */
        .broadcast-toolbar {
            padding: 6px 10px;
            background: rgba(30, 41, 59, 0.95);
            display: none;
            gap: 6px;
            align-items: center;
            border-bottom: 1px solid #334155;
            flex-wrap: wrap;
            justify-content: center;
            flex-shrink: 0;
            z-index: 50;
        }

        .broadcast-toolbar.active { display: flex; }

        /* MAIN LAYOUT */
        .main-layout {
            display: flex;
            flex: 1;
            min-height: 0;
            position: relative;
            background: #000;
        }

        /* VIDEO */
        .video-container {
            flex: 1;
            background: #000;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            min-width: 0;
            min-height: 0;
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
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            padding: 5px 10px;
            border-radius: 14px;
            font-size: 0.7rem;
            display: flex;
            align-items: center;
            gap: 5px;
            z-index: 10;
        }

        .viewers-count {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            padding: 5px 10px;
            border-radius: 14px;
            font-size: 0.7rem;
            display: flex;
            align-items: center;
            gap: 5px;
            z-index: 10;
        }

        .dot { width: 8px; height: 8px; border-radius: 50%; background: #64748b; flex-shrink: 0; }
        .dot.live {
            background: #22c55e;
            box-shadow: 0 0 8px #22c55e;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 6px #22c55e; }
            50% { box-shadow: 0 0 14px #22c55e; }
        }

        .source-label {
            position: absolute;
            bottom: 8px;
            left: 8px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 0.65rem;
            z-index: 10;
        }

        /* Waiting screen */
        .waiting-screen {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background: #0f172a;
            z-index: 5;
            gap: 16px;
        }

        .waiting-screen.hidden { display: none; }

        .waiting-icon {
            font-size: 3rem;
            animation: float 3s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        .waiting-text {
            color: #94a3b8;
            font-size: 1rem;
        }

        /* CHAT */
        .chat-panel {
            width: 320px;
            background: #1e293b;
            border-left: 1px solid #334155;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            z-index: 40;
        }

        .chat-header {
            padding: 10px 12px;
            background: #0f172a;
            font-weight: 600;
            border-bottom: 1px solid #334155;
            font-size: 0.85rem;
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
            font-size: 1.4rem;
            cursor: pointer;
            padding: 2px 6px;
            line-height: 1;
        }

        .chat-messages {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-height: 0;
            -webkit-overflow-scrolling: touch;
        }

        .chat-msg {
            background: #334155;
            padding: 8px 10px;
            border-radius: 8px;
            word-break: break-word;
            font-size: 0.8rem;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .chat-msg .author {
            font-weight: bold;
            color: #38bdf8;
            margin-bottom: 2px;
            font-size: 0.7rem;
        }

        .chat-input-box {
            padding: 8px;
            background: #0f172a;
            border-top: 1px solid #334155;
            display: flex;
            gap: 6px;
            flex-shrink: 0;
        }

        .chat-input-box input {
            flex: 1;
            padding: 9px 12px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #fff;
            outline: none;
            font-size: 0.85rem;
            -webkit-appearance: none;
        }

        .chat-input-box input:focus { border-color: #38bdf8; }

        /* TOAST */
        .notification-toast {
            position: fixed;
            top: 52px;
            right: 10px;
            background: rgba(30, 41, 59, 0.95);
            border: 1px solid #38bdf8;
            border-radius: 10px;
            padding: 8px 14px;
            z-index: 2000;
            animation: slideIn 0.3s ease, fadeOut 0.4s ease 2.5s forwards;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: 260px;
            font-size: 0.8rem;
        }

        @keyframes slideIn {
            from { transform: translateX(110%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        @keyframes fadeOut {
            to { opacity: 0; transform: translateY(-10px); }
        }

        /* SHARE */
        .share-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
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
            border-radius: 14px;
            padding: 20px;
            z-index: 1000;
            display: none;
            width: 90%;
            max-width: 380px;
        }

        .share-box h3 { margin-bottom: 10px; color: #38bdf8; font-size: 0.95rem; }

        .share-box .link-box {
            background: #0f172a;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #334155;
            word-break: break-all;
            margin-bottom: 10px;
            font-family: monospace;
            font-size: 0.75rem;
        }

        /* BADGE */
        .btn-chat-wrapper {
            position: relative;
            display: none;
        }

        .chat-badge {
            position: absolute;
            top: -5px;
            right: -5px;
            background: #ef4444;
            color: white;
            border-radius: 50%;
            width: 18px;
            height: 18px;
            font-size: 0.6rem;
            display: none;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }

        /* FULLSCREEN */
        .fullscreen-active header,
        .fullscreen-active .broadcast-toolbar {
            display: none !important;
        }

        .fullscreen-active .main-layout {
            height: 100vh;
            height: 100dvh;
        }

        .fullscreen-controls {
            position: fixed;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(12px);
            padding: 8px 16px;
            border-radius: 30px;
            display: none;
            gap: 10px;
            align-items: center;
            z-index: 100;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .fullscreen-controls.visible {
            display: flex;
            opacity: 1;
        }

        .fullscreen-controls .btn {
            padding: 8px 14px;
            font-size: 0.8rem;
            border-radius: 20px;
        }

        /* ===== MOBILE ===== */
        @media (max-width: 768px) {
            .main-layout {
                flex-direction: column;
            }

            .video-container {
                flex: 1;
                min-height: 0;
                width: 100%;
            }

            .chat-panel {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                top: auto;
                height: 45%;
                width: 100%;
                border-left: none;
                border-top: 1px solid #334155;
                transform: translateY(0);
                transition: transform 0.3s ease;
                border-radius: 16px 16px 0 0;
                z-index: 60;
            }

            .chat-panel.hidden-mobile {
                transform: translateY(100%);
            }

            .chat-close { display: block; }
            .btn-chat-wrapper { display: block; }

            .broadcast-toolbar .btn-label { display: none; }

            .fullscreen-controls {
                bottom: 10px;
                padding: 6px 12px;
                gap: 8px;
            }

            .fullscreen-controls .btn {
                padding: 6px 10px;
                font-size: 0.7rem;
            }

            .notification-toast {
                top: auto;
                bottom: 10px;
                right: 8px;
                left: 8px;
                max-width: none;
                font-size: 0.75rem;
            }
        }

        @media (max-width: 380px) {
            .logo { font-size: 0.8rem; }
            .btn { padding: 5px 8px; font-size: 0.7rem; }
        }

        @media (max-height: 500px) and (orientation: landscape) {
            header { padding: 3px 8px; min-height: 34px; }
            .logo { font-size: 0.75rem; }
            .btn { padding: 4px 8px; font-size: 0.7rem; }

            .main-layout { flex-direction: row; }

            .video-container {
                flex: 1;
                height: 100%;
            }

            .chat-panel {
                position: relative;
                width: 240px;
                height: 100%;
                border-radius: 0;
                transform: none;
            }

            .chat-panel.hidden-mobile {
                display: none;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">&#127909; Stream Ninja</div>
        <div class="header-btns">
            <div class="btn-chat-wrapper">
                <button class="btn btn-chat-toggle btn-sm" onclick="toggleChat()">&#128172;</button>
                <span class="chat-badge" id="chatBadge">0</span>
            </div>
            <button class="btn btn-fullscreen btn-sm" onclick="toggleFullscreen()">&#9974;</button>
            <button class="btn btn-share btn-sm" onclick="showShareBox()">&#128279;</button>
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
        <button id="cameraBtn" class="btn btn-broadcast btn-sm" onclick="startCamera()">
            &#128247; <span class="btn-label">Camera</span>
        </button>
        <button id="screenBtn" class="btn btn-screen btn-sm" onclick="startScreen()">
            &#128187; <span class="btn-label">Ecran</span>
        </button>
        <button id="captureBtn" class="btn btn-capture btn-sm" onclick="startCapture()">
            &#127910; <span class="btn-label">Capture</span>
        </button>
        <button id="stopBtn" class="btn btn-stop btn-sm" onclick="stopBroadcast()" style="display:none;">
            &#9632; Stop
        </button>
    </div>

    <div class="main-layout" id="streamContainer">
        <div class="video-container" id="videoContainer">
            <div class="status-overlay">
                <span class="dot" id="statusDot"></span>
                <span id="statusText">Hors ligne</span>
            </div>
            <div class="viewers-count">
                &#128065; <span id="viewersCount">0</span>
            </div>
            <div class="source-label" id="sourceLabel" style="display:none;"></div>

            <div class="waiting-screen" id="waitingScreen">
                <div class="waiting-icon">&#127909;</div>
                <div class="waiting-text">En attente du direct...</div>
            </div>

            <video id="remoteVideo" autoplay playsinline style="display:none;"></video>
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
                <button class="btn btn-broadcast btn-sm" onclick="sendChatMessage()">&#10148;</button>
            </div>
        </div>
    </div>

    <div class="fullscreen-controls" id="fullscreenControls">
        <button class="btn btn-chat-toggle" onclick="toggleChat()">&#128172; Chat</button>
        <button class="btn btn-stop" onclick="exitFullscreen()">&#10005; Quitter</button>
    </div>

    <div class="share-overlay" id="shareOverlay" onclick="hideShareBox()"></div>
    <div class="share-box" id="shareBox">
        <h3>&#128279; Partager le live</h3>
        <p style="margin-bottom:10px;color:#94a3b8;font-size:0.8rem;">Envoyez ce lien aux spectateurs :</p>
        <div class="link-box" id="shareLink"></div>
        <button class="btn btn-broadcast" onclick="copyLink()" style="width:100%;justify-content:center;margin-bottom:8px;">
            Copier le lien
        </button>
        <button class="btn btn-stop" onclick="hideShareBox()" style="width:100%;justify-content:center;">
            Fermer
        </button>
    </div>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        var socket = io();
        var localStream = null;
        var isBroadcaster = false;
        var currentBroadcasterId = null;
        var peerConnections = {};
        var viewerPeerConnection = null;
        var currentSource = '';
        var originalTitle = document.title;
        var unreadCount = 0;
        var windowFocused = true;
        var chatVisible = true;
        var mobileChatUnread = 0;
        var isFullscreen = false;
        var fullscreenTimeout = null;

        var cameraBtn = document.getElementById('cameraBtn');
        var screenBtn = document.getElementById('screenBtn');
        var captureBtn = document.getElementById('captureBtn');
        var stopBtn = document.getElementById('stopBtn');
        var localVideo = document.getElementById('localVideo');
        var remoteVideo = document.getElementById('remoteVideo');
        var statusDot = document.getElementById('statusDot');
        var statusText = document.getElementById('statusText');
        var chatMessages = document.getElementById('chatMessages');
        var sourceLabel = document.getElementById('sourceLabel');
        var viewersCount = document.getElementById('viewersCount');
        var chatPanel = document.getElementById('chatPanel');
        var chatBadge = document.getElementById('chatBadge');
        var broadcastToolbar = document.getElementById('broadcastToolbar');
        var waitingScreen = document.getElementById('waitingScreen');
        var fullscreenControls = document.getElementById('fullscreenControls');
        var videoContainer = document.getElementById('videoContainer');

        var userId = 'User_' + Math.floor(Math.random() * 9000 + 1000);

        var rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' }
            ]
        };

        var qualityPresets = {
            '1080': { width: 1920, height: 1080, frameRate: 30 },
            '720':  { width: 1280, height: 720,  frameRate: 30 },
            '480':  { width: 854,  height: 480,  frameRate: 24 },
            '360':  { width: 640,  height: 360,  frameRate: 20 },
            'auto': { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } }
        };

        function isMobile() { return window.innerWidth <= 768; }

        // === FULLSCREEN ===
        function toggleFullscreen() {
            if (!isFullscreen) {
                enterFullscreen();
            } else {
                exitFullscreen();
            }
        }

        function enterFullscreen() {
            var elem = document.documentElement;
            if (elem.requestFullscreen) {
                elem.requestFullscreen();
            } else if (elem.webkitRequestFullscreen) {
                elem.webkitRequestFullscreen();
            } else if (elem.msRequestFullscreen) {
                elem.msRequestFullscreen();
            }
            document.body.classList.add('fullscreen-active');
            isFullscreen = true;
            showFullscreenControls();

            if (isMobile()) {
                chatPanel.classList.add('hidden-mobile');
                chatVisible = false;
            }
        }

        function exitFullscreen() {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
            document.body.classList.remove('fullscreen-active');
            isFullscreen = false;
            fullscreenControls.classList.remove('visible');
        }

        document.addEventListener('fullscreenchange', function() {
            if (!document.fullscreenElement) {
                document.body.classList.remove('fullscreen-active');
                isFullscreen = false;
                fullscreenControls.classList.remove('visible');
            }
        });

        function showFullscreenControls() {
            fullscreenControls.classList.add('visible');
            clearTimeout(fullscreenTimeout);
            fullscreenTimeout = setTimeout(function() {
                fullscreenControls.classList.remove('visible');
            }, 4000);
        }

        document.addEventListener('mousemove', function() {
            if (isFullscreen) showFullscreenControls();
        });

        document.addEventListener('touchstart', function() {
            if (isFullscreen) showFullscreenControls();
        });

        // === CHAT ===
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

        window.addEventListener('resize', function() {
            if (!isMobile()) {
                chatPanel.classList.remove('hidden-mobile');
                chatVisible = true;
                chatBadge.style.display = 'none';
            }
        });

        // === SON ===
        function playNotificationSound() {
            try {
                var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                var osc = audioCtx.createOscillator();
                var gain = audioCtx.createGain();
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.frequency.setValueAtTime(800, audioCtx.currentTime);
                osc.frequency.setValueAtTime(1200, audioCtx.currentTime + 0.1);
                gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
                osc.start(audioCtx.currentTime);
                osc.stop(audioCtx.currentTime + 0.3);
            } catch(e) {}
        }

        // === ONGLET ===
        window.addEventListener('focus', function() {
            windowFocused = true;
            unreadCount = 0;
            document.title = originalTitle;
        });
        window.addEventListener('blur', function() { windowFocused = false; });

        function updateTabNotification() {
            if (!windowFocused) {
                unreadCount++;
                document.title = '(' + unreadCount + ') Nouveau msg - Stream Ninja';
            }
        }

        // === TOAST ===
        function showToast(message) {
            var old = document.querySelectorAll('.notification-toast');
            if (old.length > 2) old[0].parentNode.removeChild(old[0]);
            var t = document.createElement('div');
            t.className = 'notification-toast';
            t.textContent = message;
            document.body.appendChild(t);
            setTimeout(function() { if (t.parentNode) t.parentNode.removeChild(t); }, 3000);
        }

        // === QUALITE ===
        function getQualityConstraints() {
            var q = document.getElementById('qualitySelect').value;
            return qualityPresets[q] || qualityPresets['720'];
        }

        function updateQuality() {
            if (!isBroadcaster || !localStream) return;
            var q = getQualityConstraints();
            var vt = localStream.getVideoTracks()[0];
            if (vt) {
                vt.applyConstraints({
                    width: q.width, height: q.height, frameRate: q.frameRate
                }).catch(function(e) { console.log('Qualite:', e); });
            }
        }

        // === SOURCES ===
        async function startCamera() {
            var q = getQualityConstraints();
            try {
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: q.width, height: q.height, frameRate: q.frameRate },
                    audio: true
                });
                currentSource = 'Camera';
                startBroadcastWithStream();
            } catch (err) { alert('Erreur camera : ' + err.message); }
        }

        async function startScreen() {
            var q = getQualityConstraints();
            try {
                var ss = await navigator.mediaDevices.getDisplayMedia({
                    video: { width: q.width, height: q.height, frameRate: q.frameRate },
                    audio: true
                });
                try {
                    var mic = await navigator.mediaDevices.getUserMedia({ audio: true });
                    var ctx = new AudioContext();
                    var dest = ctx.createMediaStreamDestination();
                    if (ss.getAudioTracks().length > 0) ctx.createMediaStreamSource(ss).connect(dest);
                    ctx.createMediaStreamSource(mic).connect(dest);
                    localStream = new MediaStream([
                        ...ss.getVideoTracks(), ...dest.stream.getAudioTracks()
                    ]);
                } catch(e) { localStream = ss; }
                currentSource = 'Ecran';
                ss.getVideoTracks()[0].onended = function() { stopBroadcast(); };
                startBroadcastWithStream();
            } catch (err) { alert('Partage ecran refuse : ' + err.message); }
        }

        async function startCapture() {
            var q = getQualityConstraints();
            try {
                var devs = await navigator.mediaDevices.enumerateDevices();
                var vids = devs.filter(function(d) { return d.kind === 'videoinput'; });
                if (vids.length === 0) { alert('Aucun peripherique video'); return; }
                var cap = vids[vids.length - 1];
                for (var i = 0; i < vids.length; i++) {
                    var lb = vids[i].label.toLowerCase();
                    if (lb.indexOf('capture') !== -1 || lb.indexOf('cam link') !== -1 ||
                        lb.indexOf('elgato') !== -1 || lb.indexOf('avermedia') !== -1 ||
                        lb.indexOf('hdmi') !== -1 || lb.indexOf('usb video') !== -1) {
                        cap = vids[i]; break;
                    }
                }
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: { deviceId: { exact: cap.deviceId }, width: q.width, height: q.height, frameRate: q.frameRate },
                    audio: true
                });
                currentSource = 'Capture';
                startBroadcastWithStream();
            } catch (err) { alert('Erreur capture : ' + err.message); }
        }

        function startBroadcastWithStream() {
            waitingScreen.classList.add('hidden');
            localVideo.style.display = 'block';
            localVideo.srcObject = localStream;
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
                localStream.getTracks().forEach(function(t) { t.stop(); });
                localStream = null;
            }
            Object.values(peerConnections).forEach(function(pc) { pc.close(); });
            peerConnections = {};
            localVideo.style.display = 'none';
            localVideo.srcObject = null;
            remoteVideo.style.display = 'none';
            remoteVideo.srcObject = null;
            sourceLabel.style.display = 'none';
            waitingScreen.classList.remove('hidden');
            isBroadcaster = false;
            currentSource = '';
            cameraBtn.style.display = 'flex';
            screenBtn.style.display = 'flex';
            captureBtn.style.display = 'flex';
            stopBtn.style.display = 'none';
        }

        // === SOCKET ===
        socket.on('broadcaster_status', function(data) {
            currentBroadcasterId = data.broadcaster_id;
            viewersCount.textContent = data.viewers || 0;

            if (currentBroadcasterId) {
                if (currentBroadcasterId === socket.id) {
                    statusDot.className = 'dot live';
                    statusText.textContent = 'En direct';
                    broadcastToolbar.classList.add('active');
                } else {
                    cameraBtn.className = 'btn btn-disabled btn-sm';
                    cameraBtn.disabled = true;
                    screenBtn.className = 'btn btn-disabled btn-sm';
                    screenBtn.disabled = true;
                    captureBtn.className = 'btn btn-disabled btn-sm';
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
                cameraBtn.className = 'btn btn-broadcast btn-sm';
                cameraBtn.disabled = false;
                screenBtn.className = 'btn btn-screen btn-sm';
                screenBtn.disabled = false;
                captureBtn.className = 'btn btn-capture btn-sm';
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
                    remoteVideo.style.display = 'none';
                    remoteVideo.srcObject = null;
                    waitingScreen.classList.remove('hidden');
                }
            }
        });

        socket.on('viewers_count', function(data) {
            viewersCount.textContent = data.count;
        });

        // === WEBRTC ===
        socket.on('new_viewer', async function(data) {
            if (!isBroadcaster || !localStream) return;
            var vid = data.viewer_id;
            var pc = new RTCPeerConnection(rtcConfig);
            peerConnections[vid] = pc;
            localStream.getTracks().forEach(function(t) { pc.addTrack(t, localStream); });
            pc.onicecandidate = function(e) {
                if (e.candidate) socket.emit('candidate', { target: vid, candidate: e.candidate });
            };
            var offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            socket.emit('offer', { target: vid, offer: offer });
        });

        socket.on('offer', async function(data) {
            viewerPeerConnection = new RTCPeerConnection(rtcConfig);
            viewerPeerConnection.ontrack = function(e) {
                waitingScreen.classList.add('hidden');
                remoteVideo.style.display = 'block';
                remoteVideo.srcObject = e.streams[0];
            };
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
                catch (e) {}
            }
        });

        socket.on('viewer_disconnected', function(data) {
            if (peerConnections[data.viewer_id]) {
                peerConnections[data.viewer_id].close();
                delete peerConnections[data.viewer_id];
            }
        });

        // === CHAT ===
        function sendChatMessage() {
            var input = document.getElementById('chatInput');
            var msg = input.value.trim();
            if (msg) {
                socket.emit('chat_message', { user: userId, text: msg });
                input.value = '';
            }
        }

        socket.on('chat_message', function(data) {
            var el = document.createElement('div');
            el.className = 'chat-msg';
            el.innerHTML = '<div class="author">' + escapeHtml(data.user) + '</div><div>' + escapeHtml(data.text) + '</div>';
            chatMessages.appendChild(el);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            if (data.user !== userId) {
                playNotificationSound();
                updateTabNotification();
                if (isMobile() && !chatVisible) {
                    mobileChatUnread++;
                    chatBadge.textContent = mobileChatUnread;
                    chatBadge.style.display = 'flex';
                }
                showToast(data.user + ': ' + data.text.substring(0, 40));
            }
        });

        function escapeHtml(s) {
            var d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        // === SHARE ===
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

        // INIT
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
