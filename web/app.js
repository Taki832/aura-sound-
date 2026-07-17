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

let currentUser = null;

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
    // Load YouTube API
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    setupNavigation();
    setupSearch();
    setupRoomUI();
    setupPlayerControls();
    setupSettings();
    setupEditProfile();
    
    // Setup Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.setHeaderColor('#121212');
        const user = window.Telegram.WebApp.initDataUnsafe?.user;
        if (user) {
            document.getElementById('greetingText').textContent = `Good afternoon, ${user.first_name}`;
            
            // Authenticate with backend Phase 2 Database
            try {
                const res = await fetch('/api/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user: user })
                });
                const authData = await res.json();
                if (authData.user) {
                    currentUser = authData.user;
                    console.log("Authenticated as:", currentUser.username || currentUser.display_name);
                    
                    // Populate Profile View
                    document.getElementById('profileDisplayName').textContent = currentUser.display_name || "User";
                    document.getElementById('profileUsername').textContent = currentUser.username ? `@${currentUser.username}` : "Listener";
                    document.getElementById('profileBio').textContent = currentUser.bio || "No bio added.";
                    if (currentUser.avatar_url) {
                        document.getElementById('profileAvatar').src = currentUser.avatar_url;
                    }
                    if (currentUser.banner_url) {
                        document.getElementById('profileBannerImg').src = currentUser.banner_url;
                    }
                    if (currentUser.theme === 'light') {
                        document.body.classList.add('light-theme');
                    }
                    
                    // Apply Settings
                    try {
                        const settings = JSON.parse(currentUser.settings_json || '{}');
                        document.getElementById('settingAmoled').checked = settings.amoled || false;
                        document.getElementById('settingGapless').checked = settings.gapless !== false;
                        document.getElementById('settingHqAudio').checked = settings.hqAudio !== false;
                        document.getElementById('settingGlassEffects').checked = settings.glassEffects !== false;
                        
                        if(settings.amoled) document.body.style.backgroundColor = '#000000';
                        if(settings.glassEffects === false) {
                            document.documentElement.style.setProperty('--glass-bg', 'rgba(18,18,18,1)');
                        }
                    } catch(e) {}

                    // Load User Data
                    loadFriendsList();
                    loadNotificationsList();
                    loadPlaylistsList();
                    loadLikedSongsList();
                }
            } catch (e) {
                console.error("Auth failed", e);
            }
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

    // Top Header Navigation (Phase 3)
    const openView = (viewId) => {
        navItems.forEach(n => n.classList.remove('active'));
        views.forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
    };
    
    document.getElementById('btnNavNotifications')?.addEventListener('click', () => openView('view-notifications'));
    document.getElementById('btnNavProfile')?.addEventListener('click', () => openView('view-profile'));
    document.getElementById('btnNavSettings')?.addEventListener('click', () => openView('view-settings'));

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
                <img src="${track.thumbnail || 'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'}" alt="Art" onerror="this.src='https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'">
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
    
    const fallbackArt = 'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400';
    const miniArt = document.getElementById('miniArt');
    const fullArtEl = document.getElementById('fullArt');
    
    miniArt.src = track.thumbnail || fallbackArt;
    miniArt.onerror = () => { miniArt.src = fallbackArt; };
    
    fullArtEl.src = track.thumbnail || fallbackArt;
    fullArtEl.onerror = () => { fullArtEl.src = fallbackArt; };
    
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
        document.getElementById('chatMessages').innerHTML = ''; // Clear chat
        pauseLocal();
        showToast("Left Sync Room");
    });

    // Chat UI logic
    const chatInput = document.getElementById('chatInput');
    const sendChat = () => {
        const text = chatInput.value.trim();
        if (text && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'ACTION_CHAT_MESSAGE',
                text: text,
                user_id: window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 0
            }));
            chatInput.value = '';
        }
    };
    document.getElementById('btnSendChat').addEventListener('click', sendChat);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChat();
    });
}

function appendChatMessage(msg) {
    const chatDiv = document.getElementById('chatMessages');
    const msgEl = document.createElement('div');
    const isSelf = window.Telegram?.WebApp?.initDataUnsafe?.user?.id === msg.user_id;
    msgEl.className = 'chat-msg' + (isSelf ? ' self' : '');
    msgEl.innerHTML = `<span class="chat-msg-user">${msg.username || 'User'}</span>${msg.text}`;
    chatDiv.appendChild(msgEl);
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

async function initRoom(asHost, asVideoRoom, code = "") {
    const user = window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name || "Listener";
    
    if (asHost) {
        try {
            const res = await fetch('/api/room/create', {
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
            if (data.type === 'INIT_ROOM_STATE' && data.recent_messages) {
                document.getElementById('chatMessages').innerHTML = '';
                data.recent_messages.forEach(appendChatMessage);
            }
        } else if (data.type === 'CHAT_MESSAGE') {
            appendChatMessage(data.message);
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

function setupSettings() {
    const updateSettings = async () => {
        if (!currentUser) return;
        const settings = {
            amoled: document.getElementById('settingAmoled').checked,
            gapless: document.getElementById('settingGapless').checked,
            hqAudio: document.getElementById('settingHqAudio').checked,
            glassEffects: document.getElementById('settingGlassEffects').checked
        };
        
        // Immediate UI updates
        document.body.style.backgroundColor = settings.amoled ? '#000000' : '#121212';
        document.documentElement.style.setProperty('--glass-bg', settings.glassEffects ? 'rgba(24, 24, 24, 0.7)' : 'rgba(18,18,18,1)');

        try {
            await fetch('/api/profile/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: currentUser.id,
                    settings_json: JSON.stringify(settings)
                })
            });
            showToast("Settings saved");
        } catch(e) {
            console.error("Failed to save settings", e);
        }
    };

    document.getElementById('settingAmoled')?.addEventListener('change', updateSettings);
    document.getElementById('settingGapless')?.addEventListener('change', updateSettings);
    document.getElementById('settingHqAudio')?.addEventListener('change', updateSettings);
    document.getElementById('settingGlassEffects')?.addEventListener('change', updateSettings);
}

// --- Edit Profile & Image Cropper ---
function setupEditProfile() {
    const modal = document.getElementById('editProfileModal');
    const closeBtn = document.getElementById('closeEditProfileBtn');
    const saveBtn = document.getElementById('saveProfileBtn');
    
    // Inputs
    const inputDisplay = document.getElementById('editDisplayName');
    const inputUsername = document.getElementById('editUsername');
    const inputBio = document.getElementById('editBio');
    
    // Images
    let avatarBlob = null;
    let bannerBlob = null;

    const openModal = () => {
        if (!currentUser) return;
        inputDisplay.value = currentUser.display_name || '';
        inputUsername.value = currentUser.username || '';
        inputBio.value = currentUser.bio || '';
        if (currentUser.avatar_url) document.getElementById('editAvatarPreview').src = currentUser.avatar_url;
        if (currentUser.banner_url) document.getElementById('editBannerPreview').src = currentUser.banner_url;
        modal.classList.remove('hidden');
    };

    document.getElementById('openEditProfileBtnMain')?.addEventListener('click', openModal);
    document.getElementById('openEditProfileBtnSettings')?.addEventListener('click', openModal);
    closeBtn?.addEventListener('click', () => modal.classList.add('hidden'));

    // Cropper State
    let cropper = null;
    let currentCropTarget = null; // 'avatar' or 'banner'
    const cropperModal = document.getElementById('cropperModal');
    const cropperImage = document.getElementById('cropperImage');
    
    const handleFileSelect = (e, target) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) {
            showToast("File too large. Max 10MB");
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (evt) => {
            cropperImage.src = evt.target.result;
            cropperModal.classList.remove('hidden');
            currentCropTarget = target;
            
            if (cropper) cropper.destroy();
            cropper = new Cropper(cropperImage, {
                aspectRatio: target === 'avatar' ? 1 : 16/9,
                viewMode: 1,
                background: false
            });
        };
        reader.readAsDataURL(file);
        e.target.value = ''; // reset
    };

    document.getElementById('avatarInput')?.addEventListener('change', (e) => handleFileSelect(e, 'avatar'));
    document.getElementById('bannerInput')?.addEventListener('change', (e) => handleFileSelect(e, 'banner'));

    document.getElementById('closeCropperBtn')?.addEventListener('click', () => {
        cropperModal.classList.add('hidden');
        if (cropper) cropper.destroy();
    });

    document.getElementById('confirmCropBtn')?.addEventListener('click', () => {
        if (!cropper) return;
        const canvas = cropper.getCroppedCanvas({
            width: currentCropTarget === 'avatar' ? 256 : 1024,
            height: currentCropTarget === 'avatar' ? 256 : 576
        });
        
        // Compress to JPEG 0.8
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            if (currentCropTarget === 'avatar') {
                document.getElementById('editAvatarPreview').src = url;
                avatarBlob = blob;
            } else {
                document.getElementById('editBannerPreview').src = url;
                bannerBlob = blob;
            }
            cropperModal.classList.add('hidden');
            cropper.destroy();
        }, 'image/jpeg', 0.8);
    });

    saveBtn?.addEventListener('click', async () => {
        if (!currentUser) return;
        saveBtn.textContent = 'Saving...';
        
        const formData = new FormData();
        formData.append('id', currentUser.id);
        formData.append('display_name', inputDisplay.value);
        formData.append('username', inputUsername.value);
        formData.append('bio', inputBio.value);
        
        if (avatarBlob) formData.append('avatar_file', avatarBlob, 'avatar.jpg');
        if (bannerBlob) formData.append('banner_file', bannerBlob, 'banner.jpg');

        try {
            const res = await fetch('/api/profile/update', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.user) {
                currentUser = data.user;
                // Update UI immediately
                document.getElementById('profileDisplayName').textContent = currentUser.display_name;
                document.getElementById('profileUsername').textContent = `@${currentUser.username}`;
                document.getElementById('profileBio').textContent = currentUser.bio;
                if(currentUser.avatar_url) document.getElementById('profileAvatar').src = currentUser.avatar_url;
                if(currentUser.banner_url) document.getElementById('profileBannerImg').src = currentUser.banner_url;
                
                showToast("Profile Updated Successfully");
                modal.classList.add('hidden');
            } else {
                showToast("Failed to update profile");
            }
        } catch(e) {
            console.error(e);
            showToast("Network Error");
        }
        saveBtn.textContent = 'Save Changes';
    });
}

// --- FRIENDS, NOTIFICATIONS & PLAYLISTS LOADERS ---
async function loadFriendsList() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/friends/list?user_id=${currentUser.id}`);
        const data = await res.json();
        if (data.friends) {
            document.getElementById('profileFriendsCount').textContent = data.friends.length;
        }
    } catch(e) {}
}

async function loadNotificationsList() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/notifications/list?user_id=${currentUser.id}`);
        const data = await res.json();
        const listEl = document.getElementById('notificationsList');
        if (listEl && data.notifications && data.notifications.length > 0) {
            listEl.innerHTML = data.notifications.map(n => `
                <div class="notification-item ${n.is_read ? 'read' : 'unread'}" style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 14px;">${n.title}</div>
                        <div class="text-muted" style="font-size: 13px;">${n.message}</div>
                    </div>
                    ${!n.is_read ? `<button onclick="markRead(${n.id})" class="secondary-btn" style="padding: 4px 10px; font-size: 12px;">Mark Read</button>` : ''}
                </div>
            `).join('');
        }
    } catch(e) {}
}

async function markRead(notifId) {
    if (!currentUser) return;
    await fetch('/api/notifications/read', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ notif_id: notifId, user_id: currentUser.id })
    });
    loadNotificationsList();
}

async function loadPlaylistsList() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/playlists/list?user_id=${currentUser.id}`);
        const data = await res.json();
        console.log("Playlists loaded:", data.playlists);
    } catch(e) {}
}

async function loadLikedSongsList() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/liked/list?user_id=${currentUser.id}`);
        const data = await res.json();
        if (data.tracks) {
            const countEl = document.getElementById('likedCount');
            if (countEl) countEl.textContent = data.tracks.length;
        }
    } catch(e) {}
}
