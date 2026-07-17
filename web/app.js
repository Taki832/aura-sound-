// AuraSound AI - Full Production Client

// --- State Variables ---
let currentTrack = null;
let isPlaying = false;
let isVideoMode = false;
let favorites = JSON.parse(localStorage.getItem('aurasound_favs')) || [];
let activeSource = 'all';
let currentUser = null;
let playQueue = [];
let queueIndex = -1;

// --- Sync Room State ---
let roomCode = null;
let isRoomHost = false;
let ws = null;
let serverOffset = 0;
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
    setupLibrary();
    
    // Setup Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.setHeaderColor('#121212');
        const user = window.Telegram.WebApp.initDataUnsafe?.user;
        if (user) {
            // Time-aware greeting
            const hour = new Date().getHours();
            let greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
            document.getElementById('greetingText').textContent = `${greeting}, ${user.first_name}`;
            
            // Authenticate with backend
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
                    loadListeningHistory();
                    loadUserStats();
                    loadSearchHistory();
                }
            } catch (e) {
                console.error("Auth failed", e);
            }
        }
    }
});

// --- YouTube API Callbacks ---
window.onYouTubeIframeAPIReady = function() {
    ytPlayer = new YT.Player('youtubePlayerHost', {
        height: '100%',
        width: '100%',
        playerVars: { 'autoplay': 0, 'controls': 0, 'disablekb': 1, 'fs': 0, 'rel': 0, 'playsinline': 1 },
        events: {
            'onReady': () => { isYtReady = true; },
            'onStateChange': onYtStateChange
        }
    });

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
    } else if (event.data === YT.PlayerState.ENDED) {
        playNextInQueue();
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
    } else if (event.data === YT.PlayerState.ENDED) {
        playNextInQueue();
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

    const openView = (viewId) => {
        navItems.forEach(n => n.classList.remove('active'));
        views.forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
    };
    
    document.getElementById('btnNavNotifications')?.addEventListener('click', () => {
        openView('view-notifications');
        loadNotificationsList();
    });
    document.getElementById('btnNavProfile')?.addEventListener('click', () => openView('view-profile'));
    document.getElementById('btnNavSettings')?.addEventListener('click', () => openView('view-settings'));

    // Quick Picks (genre cards)
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
            showSearchHistory();
        }
    });

    document.getElementById('clearSearchBtn').addEventListener('click', () => {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
    });
    
    // Show search history on focus
    searchInput.addEventListener('focus', () => {
        if (!searchInput.value.trim()) showSearchHistory();
    });
}

async function showSearchHistory() {
    if (!currentUser) {
        resultsList.innerHTML = `<div class="empty-search"><h4>Play what you love</h4><p>Search for artists, songs, podcasts, and more.</p></div>`;
        return;
    }
    try {
        const res = await fetch(`/api/history/search?user_id=${currentUser.id}`);
        const data = await res.json();
        if (data.history && data.history.length > 0) {
            let html = `<div class="search-history-header" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;margin-bottom:8px;">
                <h4 style="font-size:16px;font-weight:600;">Recent Searches</h4>
                <button id="clearHistoryBtn" class="text-btn" style="color:var(--spotify-green);font-size:13px;background:none;border:none;cursor:pointer;">Clear All</button>
            </div>`;
            data.history.forEach(h => {
                html += `<div class="track-item search-history-item" data-query="${h.query}" style="cursor:pointer;">
                    <div style="width:48px;height:48px;background:var(--bg-elevated);border-radius:8px;display:flex;align-items:center;justify-content:center;">
                        <i class="fa-solid fa-clock-rotate-left" style="color:var(--text-subdued);"></i>
                    </div>
                    <div class="track-info">
                        <div class="track-title">${h.query}</div>
                    </div>
                </div>`;
            });
            resultsList.innerHTML = html;
            
            document.getElementById('clearHistoryBtn')?.addEventListener('click', async () => {
                await fetch('/api/history/clear_search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: currentUser.id })
                });
                resultsList.innerHTML = `<div class="empty-search"><h4>Play what you love</h4><p>Search for artists, songs, podcasts, and more.</p></div>`;
                showToast("Search history cleared");
            });
            
            document.querySelectorAll('.search-history-item').forEach(item => {
                item.addEventListener('click', () => {
                    searchInput.value = item.dataset.query;
                    performSearch(item.dataset.query);
                });
            });
        } else {
            resultsList.innerHTML = `<div class="empty-search"><h4>Play what you love</h4><p>Search for artists, songs, podcasts, and more.</p></div>`;
        }
    } catch(e) {
        resultsList.innerHTML = `<div class="empty-search"><h4>Play what you love</h4><p>Search for artists, songs, podcasts, and more.</p></div>`;
    }
}

async function performSearch(query) {
    resultsList.innerHTML = '';
    searchSpinner.classList.remove('hidden');
    
    // Save search history
    if (currentUser) {
        fetch('/api/history/save_search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: currentUser.id, query: query })
        }).catch(() => {});
    }
    
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(activeSource)}`);
        const data = await response.json();
        searchSpinner.classList.add('hidden');

        if (!data.results || data.results.length === 0) {
            resultsList.innerHTML = `<div class="empty-search"><h4>No results found</h4><p>Try a different keyword.</p></div>`;
            return;
        }

        data.results.forEach((track, idx) => {
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
                    <i class="fa-solid fa-plus add-queue-btn" title="Add to Queue"></i>
                    <i class="fa-solid fa-play play-audio-btn" title="Play Audio"></i>
                    <i class="fa-solid fa-film play-video-btn" title="Play Video"></i>
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
            el.querySelector('.add-queue-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                addToQueue(track);
            });
            el.addEventListener('click', () => playTrack(track, false));
            resultsList.appendChild(el);
        });
    } catch (e) {
        searchSpinner.classList.add('hidden');
        showToast("Search failed. Please try again.");
    }
}

// --- Queue System ---
function addToQueue(track) {
    playQueue.push(track);
    showToast(`Added "${track.title.substring(0, 30)}..." to queue`);
    updateQueueUI();
}

function playNextInQueue() {
    queueIndex++;
    if (queueIndex < playQueue.length) {
        playTrack(playQueue[queueIndex], false);
    } else {
        showToast("Queue finished");
    }
}

function updateQueueUI() {
    const queueList = document.getElementById('queueList');
    if (!queueList) return;
    if (playQueue.length === 0) {
        queueList.innerHTML = '<div class="text-muted" style="font-size:14px;padding:16px;">Queue is empty. Search and add songs!</div>';
        return;
    }
    queueList.innerHTML = playQueue.map((t, i) => `
        <div class="track-item queue-item ${i <= queueIndex ? 'played' : ''}" style="${i <= queueIndex ? 'opacity:0.5;' : ''}">
            <img src="${t.thumbnail || 'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'}" alt="Art" onerror="this.src='https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'">
            <div class="track-info">
                <div class="track-title">${i === queueIndex + 1 ? '▶ ' : ''}${t.title}</div>
                <div class="track-meta">${formatTime(t.duration)}</div>
            </div>
            <i class="fa-solid fa-xmark" onclick="removeFromQueue(${i})" style="color:var(--text-subdued);cursor:pointer;padding:8px;"></i>
        </div>
    `).join('');
}

function removeFromQueue(index) {
    playQueue.splice(index, 1);
    if (index <= queueIndex) queueIndex--;
    updateQueueUI();
    showToast("Removed from queue");
}

// --- Player Logic ---
function setupPlayerControls() {
    miniPlayer.addEventListener('click', (e) => {
        if(e.target.id === 'miniPlayBtn' || e.target.id === 'miniFavBtn' || e.target.closest('#miniFavBtn') || e.target.closest('#miniPlayBtn')) return;
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

    // Like button in mini player
    document.getElementById('miniFavBtn')?.addEventListener('click', () => toggleLikeCurrentTrack());
    document.getElementById('fullFavBtn')?.addEventListener('click', () => toggleLikeCurrentTrack());

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

    // Next / Prev buttons
    document.getElementById('fullNextBtn')?.addEventListener('click', () => playNextInQueue());
    document.getElementById('fullPrevBtn')?.addEventListener('click', () => {
        if (getLocalPosition() > 3) {
            seekLocal(0);
        } else if (queueIndex > 0) {
            queueIndex -= 2; // Will be incremented in playNextInQueue
            playNextInQueue();
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

async function toggleLikeCurrentTrack() {
    if (!currentUser || !currentTrack) return;
    try {
        const res = await fetch('/api/liked/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: currentUser.id, track: currentTrack })
        });
        const data = await res.json();
        const heartClass = data.is_liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
        const heartColor = data.is_liked ? '#1DB954' : '';
        
        const miniFav = document.getElementById('miniFavBtn');
        const fullFav = document.getElementById('fullFavBtn');
        if (miniFav) { miniFav.className = heartClass; miniFav.style.color = heartColor; }
        if (fullFav) { fullFav.className = heartClass + ' fa-xl'; fullFav.style.color = heartColor; }
        
        showToast(data.message);
        loadLikedSongsList();
    } catch(e) {
        showToast("Failed to update liked status");
    }
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
        if (data.duration) track.duration = data.duration;
    } catch (e) {
        showToast("Failed to resolve stream");
        return;
    }

    if (roomCode && isRoomHost) {
        ws.send(JSON.stringify({ type: 'ACTION_TRACK', track: track, is_video: asVideo }));
    } else {
        applyTrackUI(track, asVideo);
        seekLocal(0);
        playLocal();
    }

    // Track listening history
    if (currentUser) {
        fetch('/api/history/track_played', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: currentUser.id, track: track })
        }).catch(() => {});
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

    // Reset heart state
    const miniFav = document.getElementById('miniFavBtn');
    const fullFav = document.getElementById('fullFavBtn');
    if (miniFav) { miniFav.className = 'fa-regular fa-heart'; miniFav.style.color = ''; }
    if (fullFav) { fullFav.className = 'fa-regular fa-heart fa-xl'; fullFav.style.color = ''; }

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
    else if (!isVideoMode && isHiddenYtReady) hiddenYtPlayer.seekTo(seconds, true);
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
        document.getElementById('chatMessages').innerHTML = '';
        pauseLocal();
        showToast("Left Sync Room");
    });

    // Copy Room Code
    document.getElementById('copyCodeIcon')?.addEventListener('click', () => {
        const code = document.getElementById('activeRoomCode').textContent;
        navigator.clipboard.writeText(code).then(() => {
            showToast("Room code copied!");
        }).catch(() => {
            // Fallback
            const el = document.createElement('textarea');
            el.value = code;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
            showToast("Room code copied!");
        });
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
            const roomNameInput = document.getElementById('roomNameInput');
            const customName = roomNameInput?.value?.trim() || `${user}'s Room`;
            const res = await fetch('/api/room/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: customName })
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
    
    let reconnectAttempts = 0;
    const connectWS = () => {
        const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${wsProto}//${location.host}/ws/room/${code}?user=${encodeURIComponent(user)}`);
        
        ws.onopen = () => {
            reconnectAttempts = 0;
            document.getElementById('roomSetupState').classList.add('hidden');
            document.getElementById('roomActiveState').classList.remove('hidden');
            document.getElementById('activeRoomCode').textContent = code;
            document.getElementById('fullRoomSyncIcon').style.color = '#1DB954';
            showToast(asHost ? "Room Created!" : "Connected to Room!");
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
        
        ws.onclose = () => {
            document.getElementById('fullRoomSyncIcon').style.color = '#e91e63';
            if (reconnectAttempts < 5 && roomCode === code) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                showToast(`Reconnecting (${reconnectAttempts}/5)...`);
                setTimeout(connectWS, delay);
            } else {
                showToast("Disconnected from room");
            }
        };
    };

    connectWS();
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
        if (window.auraIsland) {
            window.auraIsland.setMembers(state.members);
        }
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

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        currentUser = null;
        localStorage.clear();
        showToast("Logged out");
        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.close();
        } else {
            location.reload();
        }
    });
}

// --- Edit Profile & Image Cropper ---
function setupEditProfile() {
    const modal = document.getElementById('editProfileModal');
    const closeBtn = document.getElementById('closeEditProfileBtn');
    const saveBtn = document.getElementById('saveProfileBtn');
    
    const inputDisplay = document.getElementById('editDisplayName');
    const inputUsername = document.getElementById('editUsername');
    const inputBio = document.getElementById('editBio');
    
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
    let currentCropTarget = null;
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
        e.target.value = '';
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
                document.getElementById('profileDisplayName').textContent = currentUser.display_name;
                document.getElementById('profileUsername').textContent = `@${currentUser.username}`;
                document.getElementById('profileBio').textContent = currentUser.bio;
                if(currentUser.avatar_url) document.getElementById('profileAvatar').src = currentUser.avatar_url;
                if(currentUser.banner_url) document.getElementById('profileBannerImg').src = currentUser.banner_url;
                
                showToast("Profile Updated Successfully");
                modal.classList.add('hidden');
                avatarBlob = null;
                bannerBlob = null;
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

// --- Library Setup ---
function setupLibrary() {
    // Liked Songs click
    document.querySelector('.liked-songs-item')?.addEventListener('click', () => {
        document.getElementById('libraryContent').classList.add('hidden');
        document.getElementById('likedSongsPanel').classList.remove('hidden');
        renderLikedSongsPanel();
    });

    // Back from liked songs
    document.getElementById('backFromLiked')?.addEventListener('click', () => {
        document.getElementById('likedSongsPanel').classList.add('hidden');
        document.getElementById('libraryContent').classList.remove('hidden');
    });

    // Create playlist button
    document.getElementById('btnCreatePlaylist')?.addEventListener('click', async () => {
        if (!currentUser) return;
        const name = prompt("Playlist name:");
        if (!name) return;
        try {
            await fetch('/api/playlists/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: currentUser.id, name: name })
            });
            showToast("Playlist created!");
            loadPlaylistsList();
        } catch(e) {
            showToast("Failed to create playlist");
        }
    });
}

// --- Data Loaders ---
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
                        <div class="text-muted" style="font-size: 11px; margin-top: 4px;">${formatTimeAgo(n.created_at)}</div>
                    </div>
                    ${!n.is_read ? `<button onclick="markRead(${n.id})" class="secondary-btn" style="padding: 4px 10px; font-size: 12px;">Mark Read</button>` : ''}
                </div>
            `).join('');
        } else if (listEl) {
            listEl.innerHTML = '<div class="empty-search"><p class="text-muted" style="font-size: 14px;">You have no new notifications.</p></div>';
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

async function markAllRead() {
    if (!currentUser) return;
    await fetch('/api/notifications/read_all', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ user_id: currentUser.id })
    });
    showToast("All notifications marked as read");
    loadNotificationsList();
}

async function loadPlaylistsList() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/playlists/list?user_id=${currentUser.id}`);
        const data = await res.json();
        const container = document.getElementById('playlistsContainer');
        if (!container) return;
        if (data.playlists && data.playlists.length > 0) {
            container.innerHTML = data.playlists.map(p => `
                <div class="library-item playlist-item" data-id="${p.id}" style="cursor:pointer;">
                    <div style="width:56px;height:56px;background:linear-gradient(135deg,#450AF5,#8E8EE5);border-radius:8px;display:flex;align-items:center;justify-content:center;">
                        <i class="fa-solid fa-music" style="font-size:20px;"></i>
                    </div>
                    <div class="lib-info">
                        <h4>${p.name}</h4>
                        <p>${(p.tracks || []).length} songs · ${p.is_public ? 'Public' : 'Private'}</p>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-muted" style="font-size:14px;padding:8px;">No playlists yet. Create one!</div>';
        }
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

async function renderLikedSongsPanel() {
    if (!currentUser) return;
    const list = document.getElementById('likedSongsTrackList');
    if (!list) return;
    list.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';
    
    try {
        const res = await fetch(`/api/liked/list?user_id=${currentUser.id}`);
        const data = await res.json();
        if (data.tracks && data.tracks.length > 0) {
            list.innerHTML = data.tracks.map(track => `
                <div class="track-item" onclick="playTrack(${JSON.stringify(track).replace(/"/g, '&quot;')}, false)">
                    <img src="${track.thumbnail || 'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'}" alt="Art" onerror="this.src='https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'">
                    <div class="track-info">
                        <div class="track-title">${track.title}</div>
                        <div class="track-meta">${formatTime(track.duration)}</div>
                    </div>
                    <i class="fa-solid fa-play" style="color:var(--spotify-green);"></i>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="empty-search"><p class="text-muted" style="font-size:14px;">No liked songs yet. Heart songs to add them here!</p></div>';
        }
    } catch(e) {
        list.innerHTML = '<div class="text-muted" style="padding:16px;">Failed to load</div>';
    }
}

async function loadListeningHistory() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/history/listening?user_id=${currentUser.id}`);
        const data = await res.json();
        const grid = document.getElementById('trendingGrid');
        if (!grid) return;
        
        if (data.tracks && data.tracks.length > 0) {
            grid.innerHTML = data.tracks.slice(0, 8).map(track => `
                <div class="recent-card" data-query="${track.title}" style="cursor:pointer;">
                    <img src="${track.thumbnail || 'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'}" 
                         alt="Art" style="width:48px;height:48px;border-radius:8px;object-fit:cover;" 
                         onerror="this.src='https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=400'">
                    <span class="recent-title">${track.title.length > 25 ? track.title.substring(0,25)+'...' : track.title}</span>
                </div>
            `).join('');

            // Re-attach click handlers
            grid.querySelectorAll('.recent-card').forEach(card => {
                card.addEventListener('click', () => {
                    const q = card.dataset.query;
                    document.querySelector('[data-target="view-search"]')?.click();
                    searchInput.value = q;
                    performSearch(q);
                });
            });
        } else {
            grid.innerHTML = `<div class="empty-search" style="grid-column: span 2;">
                <p class="text-muted" style="font-size: 14px;">Listen to songs, and your history will appear here.</p>
            </div>`;
        }
    } catch(e) {}
}

async function loadUserStats() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/user/stats?user_id=${currentUser.id}`);
        const data = await res.json();
        if (data.stats) {
            document.getElementById('profileRoomsCount').textContent = data.stats.rooms_joined || 0;
            document.getElementById('profileFollowersCount').textContent = data.stats.songs_played || 0;
        }
    } catch(e) {}
}

async function loadSearchHistory() {
    // Pre-load search history for when user navigates to search tab
}

// --- Time Ago Helper ---
function formatTimeAgo(timestamp) {
    const diff = Math.floor(Date.now() / 1000) - timestamp;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    return `${Math.floor(diff/86400)}d ago`;
}
