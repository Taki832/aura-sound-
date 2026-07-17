// AuraSound AI - Spotify Mobile Clone & Sync Engine

// --- State Variables ---
let currentTrack = null;
let isPlaying = false;
let isVideoMode = false;
let favorites = JSON.parse(localStorage.getItem('aurasound_favs')) || [];
let activeSource = 'all';

// --- Sync Room State ---
let roomCode = null;
let isRoomHost = false;
let ws = null;
let serverOffset = 0; // LocalTime - ServerTime
let roomIsPlaying = false;
let roomPauseOffset = 0;
let roomStartTime = 0;
let lastHeartbeatPos = 0;

// --- YouTube IFrame API ---
let ytPlayer = null;
let isYtReady = false;
let hiddenYtPlayer = null;
let isHiddenYtReady = false;

// --- DOM Elements ---
const views = document.querySelectorAll('.view-section');
const navItems = document.querySelectorAll('.nav-item');
const searchInput = document.getElementById('searchInput');
const resultsList = document.getElementById('resultsList');
const searchSpinner = document.getElementById('searchSpinner');

// Mini Player
const miniPlayer = document.getElementById('miniPlayer');
const miniPlayBtn = document.getElementById('miniPlayBtn');
const miniProgressFill = document.getElementById('miniProgressFill');

// Full Player
const fullPlayerOverlay = document.getElementById('fullPlayerOverlay');
const closeFullPlayerBtn = document.getElementById('closeFullPlayerBtn');
const fullPlayBtn = document.getElementById('fullPlayBtn');
const seekSlider = document.getElementById('seekSlider');
const timeCurrent = document.getElementById('timeCurrent');
const timeTotal = document.getElementById('timeTotal');
const youtubePlayerHost = document.getElementById('youtubePlayerHost');
const fullArt = document.getElementById('fullArt');
const fullPlayerModeText = document.getElementById('fullPlayerModeText');

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    // Load YouTube API
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    setupNavigation();
    setupSearch();
    setupRoomUI();
    setupPlayerControls();
    
    // Setup Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.setHeaderColor('#121212');
        const user = window.Telegram.WebApp.initDataUnsafe?.user;
        if (user) {
            document.getElementById('greetingText').textContent = `Good afternoon, ${user.first_name}`;
        }
    }
});

// --- YouTube API Callbacks ---
window.onYouTubeIframeAPIReady = function() {
    // Visible Player (For Video Mode)
    ytPlayer = new YT.Player('youtubePlayerHost', {
        height: '100%',
        width: '100%',
        playerVars: { 'autoplay': 0, 'controls': 0, 'disablekb': 1, 'fs': 0, 'rel': 0, 'playsinline': 1 },
        events: {
            'onReady': () => { isYtReady = true; },
            'onStateChange': onYtStateChange
        }
    });

    // Hidden Player (For Audio Mode - Bypasses Render IP Blocks)
    hiddenYtPlayer = new YT.Player('hiddenAudioPlayerHost', {
        height: '1',
        width: '1',
        playerVars: { 'autoplay': 0, 'controls': 0, 'playsinline': 1 },
        events: {
            'onReady': () => { isHiddenYtReady = true; },
            'onStateChange': onHiddenYtStateChange
        }
    });
};

function onYtStateChange(event) {
    if (!isVideoMode) return;
    if (event.data === YT.PlayerState.PLAYING) {
        isPlaying = true;
        updatePlayButtons();
    } else if (event.data === YT.PlayerState.PAUSED) {
        isPlaying = false;
        updatePlayButtons();
    }
}
function onHiddenYtStateChange(event) {
    if (isVideoMode) return;
    if (event.data === YT.PlayerState.PLAYING) {
        isPlaying = true;
        updatePlayButtons();
    } else if (event.data === YT.PlayerState.PAUSED) {
        isPlaying = false;
        updatePlayButtons();
    }
}

// --- Navigation ---
function setupNavigation() {
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(item.dataset.target).classList.add('active');
        });
    });

    // Quick Picks
    document.querySelectorAll('.recent-card').forEach(card => {
        card.addEventListener('click', () => {
            document.querySelector('[data-target="view-search"]').click();
            searchInput.value = card.dataset.query;
            performSearch(card.dataset.query);
        });
    });

    document.querySelectorAll('.pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            activeSource = pill.dataset.source;
            if(searchInput.value.trim()) performSearch(searchInput.value.trim());
        });
    });
}

// --- Search ---
function setupSearch() {
    let timeout = null;
    searchInput.addEventListener('input', () => {
        clearTimeout(timeout);
        const q = searchInput.value.trim();
        document.getElementById('clearSearchBtn').classList.toggle('hidden', !q);
        if (q) {
            timeout = setTimeout(() => performSearch(q), 500);
        } else {
            resultsList.innerHTML = `<div class="empty-search"><h4>Play what you love</h4><p>Search for artists, songs, podcasts, and more.</p></div>`;
        }
    });

    document.getElementById('clearSearchBtn').addEventListener('click', () => {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
    });
}

async function performSearch(query) {
    resultsList.innerHTML = '';
    searchSpinner.classList.remove('hidden');
    
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(activeSource)}`);
        const data = await response.json();
        searchSpinner.classList.add('hidden');

        if (!data.results || data.results.length === 0) {
            resultsList.innerHTML = `<div class="empty-search"><h4>No results found</h4><p>Try a different keyword.</p></div>`;
            return;
        }

        data.results.forEach(track => {
            const el = document.createElement('div');
            el.className = 'track-item';
            el.innerHTML = `
                <img src="${track.thumbnail}" alt="Art">
                <div class="track-info">
                    <div class="track-title">${track.title}</div>
                    <div class="track-meta">
                        <span class="source-tag ${track.source.toLowerCase()}">${track.source}</span>
                        ${formatTime(track.duration)}
                    </div>
                </div>
                <div class="track-actions">
                    <i class="fa-solid fa-play play-audio-btn"></i>
                    <i class="fa-solid fa-film play-video-btn"></i>
                </div>
            `;
            
            el.querySelector('.play-audio-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                playTrack(track, false);
            });
            el.querySelector('.play-video-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                playTrack(track, true);
            });
            el.addEventListener('click', () => playTrack(track, false));
            resultsList.appendChild(el);
        });
    } catch (e) {
        searchSpinner.classList.add('hidden');
        showToast("Search failed");
    }
}

// --- Player Logic ---
function setupPlayerControls() {
    miniPlayer.addEventListener('click', (e) => {
        if(e.target.id === 'miniPlayBtn' || e.target.id === 'miniFavBtn') return;
        fullPlayerOverlay.classList.add('open');
    });
    
    closeFullPlayerBtn.addEventListener('click', () => {
        fullPlayerOverlay.classList.remove('open');
    });

    const togglePlay = () => {
        if (!currentTrack) return;
        const targetPos = getLocalPosition();
        if (roomCode && isRoomHost) {
            sendRoomAction(isPlaying ? 'ACTION_PAUSE' : 'ACTION_PLAY', targetPos);
        } else if (!roomCode) {
            isPlaying ? pauseLocal() : playLocal();
        } else {
            showToast("Only the host can control playback");
        }
    };

    miniPlayBtn.addEventListener('click', togglePlay);
    fullPlayBtn.addEventListener('click', togglePlay);

    seekSlider.addEventListener('input', () => {
        timeCurrent.textContent = formatTime(seekSlider.value);
    });
    seekSlider.addEventListener('change', () => {
        if (roomCode && isRoomHost) {
            sendRoomAction('ACTION_SEEK', seekSlider.value);
        } else if (!roomCode) {
            seekLocal(seekSlider.value);
        } else {
            showToast("Only host can seek!");
        }
    });

    // Update Progress Loop
    setInterval(() => {
        if (!currentTrack) return;
        const pos = getLocalPosition();
        if (!seekSlider.matches(':active')) {
            seekSlider.value = pos;
            timeCurrent.textContent = formatTime(pos);
            const percent = (pos / currentTrack.duration) * 100;
            miniProgressFill.style.width = `${percent}%`;
        }
        
        // Sync Drift Correction (If in room)
        if (roomCode && isPlaying) {
            const expected = getRoomExpectedPosition();
            if (Math.abs(pos - expected) > 1.5) {
                console.log(`[Sync] Drift corrected: Local ${pos.toFixed(1)}s, Expected ${expected.toFixed(1)}s`);
                seekLocal(expected);
            }
        }
    }, 500);
}

async function playTrack(track, asVideo) {
    if (roomCode && !isRoomHost) {
        showToast("Only the host can change tracks!");
        return;
    }

    currentTrack = track;
    isVideoMode = asVideo;
    
    // Resolve YouTube ID
    showToast("Resolving stream...");
    try {
        const res = await fetch(`/api/video?q=${encodeURIComponent(track.id || track.title)}`);
        const data = await res.json();
        if (!data.video_id) throw new Error("No ID");
        track.yt_id = data.video_id;
    } catch (e) {
        showToast("Failed to resolve stream");
        return;
    }

    if (roomCode && isRoomHost) {
        ws.send(JSON.stringify({ type: 'ACTION_PLAY', track: track, position: 0, is_video: asVideo }));
    } else {
        applyTrackUI(track, asVideo);
        seekLocal(0);
        playLocal();
    }
}

function applyTrackUI(track, asVideo) {
    miniPlayer.classList.remove('hidden');
    document.getElementById('miniTitle').textContent = track.title;
    document.getElementById('fullTitle').textContent = track.title;
    document.getElementById('miniArt').src = track.thumbnail;
    fullArt.src = track.thumbnail;
    timeTotal.textContent = formatTime(track.duration);
    seekSlider.max = track.duration;

    fullPlayerModeText.textContent = asVideo ? "WATCHING VIDEO" : "PLAYING AUDIO";

    if (asVideo) {
        fullArt.classList.add('hidden');
        youtubePlayerHost.classList.remove('hidden');
        if (isYtReady) ytPlayer.loadVideoById(track.yt_id);
        if (isHiddenYtReady) hiddenYtPlayer.stopVideo();
    } else {
        youtubePlayerHost.classList.add('hidden');
        fullArt.classList.remove('hidden');
        if (isYtReady) ytPlayer.stopVideo();
        if (isHiddenYtReady) hiddenYtPlayer.loadVideoById(track.yt_id);
    }
}

function getLocalPosition() {
    if (isVideoMode && isYtReady) return ytPlayer.getCurrentTime() || 0;
    if (!isVideoMode && isHiddenYtReady) return hiddenYtPlayer.getCurrentTime() || 0;
    return 0;
}

function playLocal() {
    isPlaying = true;
    updatePlayButtons();
    if (isVideoMode && isYtReady) ytPlayer.playVideo();
    else if (!isVideoMode && isHiddenYtReady) hiddenYtPlayer.playVideo();
}

function pauseLocal() {
    isPlaying = false;
    updatePlayButtons();
    if (isVideoMode && isYtReady) ytPlayer.pauseVideo();
    else if (!isVideoMode && isHiddenYtReady) hiddenYtPlayer.pauseVideo();
}

function seekLocal(seconds) {
    if (isVideoMode && isYtReady) ytPlayer.seekTo(seconds, true);
    else if (!isHiddenYtReady) hiddenYtPlayer.seekTo(seconds, true);
}

function updatePlayButtons() {
    miniPlayBtn.className = isPlaying ? "fa-solid fa-pause" : "fa-solid fa-play";
    fullPlayBtn.innerHTML = isPlaying ? '<i class="fa-solid fa-pause fa-xl"></i>' : '<i class="fa-solid fa-play fa-xl" style="margin-left: 4px;"></i>';
}

// --- Sync Room Logic ---
function setupRoomUI() {
    document.getElementById('btnCreateAudioRoom').addEventListener('click', () => initRoom(true, false));
    document.getElementById('btnCreateVideoRoom').addEventListener('click', () => initRoom(true, true));
    document.getElementById('btnJoinRoom').addEventListener('click', () => {
        const code = document.getElementById('joinCodeInput').value.trim().toUpperCase();
        if(code) initRoom(false, false, code);
    });

    document.getElementById('btnLeaveRoom').addEventListener('click', () => {
        if(ws) ws.close();
        roomCode = null;
        isRoomHost = false;
        document.getElementById('roomSetupState').classList.remove('hidden');
        document.getElementById('roomActiveState').classList.add('hidden');
        document.getElementById('fullRoomSyncIcon').style.color = '#fff';
        pauseLocal();
        showToast("Left Sync Room");
    });
}

async function initRoom(asHost, asVideoRoom, code = "") {
    const user = window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name || "Listener";
    
    if (asHost) {
        try {
            const res = await fetch('/api/room', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: user })
            });
            const data = await res.json();
            code = data.room_code;
        } catch(e) {
            showToast("Failed to create room");
            return;
        }
    }

    roomCode = code;
    isRoomHost = asHost;
    
    // Connect WS
    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProto}//${location.host}/ws/room/${code}?user=${encodeURIComponent(user)}`);
    
    ws.onopen = () => {
        document.getElementById('roomSetupState').classList.add('hidden');
        document.getElementById('roomActiveState').classList.remove('hidden');
        document.getElementById('activeRoomCode').textContent = code;
        document.getElementById('fullRoomSyncIcon').style.color = '#1DB954';
        showToast(asHost ? "Room Created!" : "Joined Room!");
    };
    
    ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.type === 'INIT_ROOM_STATE' || data.type === 'SERVER_STATE' || data.type === 'SERVER_HEARTBEAT') {
            handleServerState(data);
        }
    };
    
    ws.onclose = () => { showToast("Disconnected from room"); };
}

function handleServerState(state) {
    serverOffset = (Date.now() / 1000) - state.server_time;
    roomIsPlaying = state.is_playing;
    roomStartTime = state.start_time || 0;
    roomPauseOffset = state.pause_offset || state.current_position;
    lastHeartbeatPos = state.current_position;

    // Member List
    if (state.members) {
        document.getElementById('memberCount').textContent = state.members.length;
        document.getElementById('membersUl').innerHTML = state.members.map((m, i) => `<li>${m} ${i===0?'(Host)':''}</li>`).join('');
    }

    // Apply Track changes
    if (state.track && (!currentTrack || currentTrack.yt_id !== state.track.yt_id)) {
        currentTrack = state.track;
        isVideoMode = state.is_video;
        applyTrackUI(currentTrack, isVideoMode);
    }

    // Apply Play/Pause state
    if (roomIsPlaying && !isPlaying) {
        seekLocal(state.current_position);
        playLocal();
    } else if (!roomIsPlaying && isPlaying) {
        seekLocal(state.current_position);
        pauseLocal();
    }
}

function getRoomExpectedPosition() {
    if (!roomIsPlaying) return roomPauseOffset;
    const now = (Date.now() / 1000) - serverOffset;
    return now - roomStartTime;
}

function sendRoomAction(type, position) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type, position }));
    }
}

// --- Utils ---
function formatTime(seconds) {
    if (!seconds) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), 3000);
}
