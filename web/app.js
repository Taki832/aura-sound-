// AuraSound AI — synchronized audio plus YouTube video-song rooms.
// The server owns the room clock. The browser only corrects drift; it never
// reloads a stream on each heartbeat.

document.addEventListener("DOMContentLoaded", () => {
    if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
    }

    const audioPlayer = document.getElementById("inAppAudio");
    const videoPlayerSection = document.getElementById("videoPlayerSection");
    const closeVideoBtn = document.getElementById("closeVideoBtn");
    const videoTitle = document.getElementById("videoTitle");
    const modeToggleBtn = document.getElementById("modeToggleBtn");
    const modeIcon = document.getElementById("modeIcon");
    const modeLabel = document.getElementById("modeLabel");

    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");
    const resultsGrid = document.getElementById("resultsGrid");
    const videoGrid = document.getElementById("videoGrid");
    const resultsCount = document.getElementById("resultsCount");
    const loadingState = document.getElementById("loadingState");
    const emptyState = document.getElementById("emptyState");
    const sourcePills = document.querySelectorAll(".src-pill");
    const trendingChips = document.querySelectorAll(".t-chip");

    const viewPanes = document.querySelectorAll(".view-pane");
    const pcNavBtns = document.querySelectorAll(".pc-nav-btn");
    const mobileTabBtns = document.querySelectorAll(".tab-item");
    const favoritesGrid = document.getElementById("favoritesGrid");
    const queueGrid = document.getElementById("queueGrid");
    const pcFavCount = document.getElementById("pcFavCount");
    const clearQueueBtn = document.getElementById("clearQueueBtn");

    const mobileRoomPill = document.getElementById("mobileRoomPill");
    const mobileRoomStatusText = document.getElementById("mobileRoomStatusText");
    const pcRoomBadge = document.getElementById("pcRoomBadge");
    const liveRoomBanner = document.getElementById("liveRoomBanner");
    const bannerCode = document.getElementById("bannerCode");
    const accuracyTag = document.getElementById("accuracyTag");
    const copyCodeBtn = document.getElementById("copyCodeBtn");
    const leaveRoomBtn = document.getElementById("leaveRoomBtn");
    const createRoomName = document.getElementById("createRoomName");
    const createRoomBtn = document.getElementById("createRoomBtn");
    const joinRoomCode = document.getElementById("joinRoomCode");
    const joinRoomBtn = document.getElementById("joinRoomBtn");

    const playerArt = document.getElementById("playerArt");
    const playerTitle = document.getElementById("playerTitle");
    const playerArtist = document.getElementById("playerArtist");
    const playerFavBtn = document.getElementById("playerFavBtn");
    const playPauseBtn = document.getElementById("playPauseBtn");
    const scrubberTrack = document.getElementById("scrubberTrack");
    const scrubberFill = document.getElementById("scrubberFill");
    const currentTimeEl = document.getElementById("currentTime");
    const totalDurationEl = document.getElementById("totalDuration");
    const volumeSlider = document.getElementById("volumeSlider");
    const eqBars = document.getElementById("eqBars");
    const toast = document.getElementById("toast");

    const YT_PLAYING = 1;
    const YT_PAUSED = 2;
    const DRIFT_TOLERANCE_SECONDS = 0.35;
    const YOUTUBE_ID_PATTERN = /^[A-Za-z0-9_-]{6,32}$/;

    let activeSource = "all";
    let currentTrack = null;
    let isVideoMode = false;
    let loadedAudioKey = null;
    let loadedYouTubeId = null;
    let lastSearchResults = [];
    let mediaRequestId = 0;
    let youTubePlayer = null;
    let youTubePlayerPromise = null;
    let favorites = JSON.parse(localStorage.getItem("vishnu_favs_ai") || "[]");

    let activeRoomCode = null;
    let roomSocket = null;
    let pendingRoomState = null;
    let isApplyingRoomState = false;
    let toastTimer = null;

    function getUserName() {
        return window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name || "Vishnu";
    }

    function getTrackKey(track) {
        if (!track) return "";
        return String(track.youtube_id || track.id || track.webpage_url || track.title || "");
    }

    function normalizeTrack(track) {
        return {
            ...track,
            title: track?.title || "Unknown track",
            duration: Number(track?.duration) || 0,
            youtube_id: track?.youtube_id || track?.id || "",
            source: track?.source || "youtube",
        };
    }

    function setModeIndicator(videoMode) {
        if (!modeIcon || !modeLabel) return;
        modeIcon.className = videoMode ? "fa-solid fa-clapperboard text-pink" : "fa-solid fa-headphones text-cyan";
        modeLabel.textContent = videoMode ? "Video" : "Audio";
    }

    function setPlayingUI(isPlaying) {
        playPauseBtn.innerHTML = `<i class="fa-solid fa-${isPlaying ? "pause" : "play"}"></i>`;
        eqBars.classList.toggle("playing", isPlaying);
    }

    function switchView(targetView) {
        viewPanes.forEach((pane) => {
            const isTarget = pane.id === `${targetView}View`;
            pane.classList.toggle("hidden", !isTarget);
            pane.classList.toggle("active", isTarget);
        });
        pcNavBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.view === targetView));
        mobileTabBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.view === targetView));

        if (targetView === "video") renderVideoView();
        if (targetView === "favorites") renderFavorites();
        if (targetView === "queue") renderQueueView();
    }

    pcNavBtns.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
    mobileTabBtns.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
    mobileRoomPill?.addEventListener("click", () => switchView("room"));

    modeToggleBtn?.addEventListener("click", () => {
        isVideoMode = !isVideoMode;
        setModeIndicator(isVideoMode);
        showToast(isVideoMode ? "Video mode selected" : "Audio mode selected");
    });

    closeVideoBtn?.addEventListener("click", () => {
        if (activeRoomCode) {
            showToast("Video stays visible while this room is synced");
            return;
        }
        if (youTubePlayer) youTubePlayer.pauseVideo();
        videoPlayerSection.classList.add("hidden");
        setPlayingUI(false);
    });

    sourcePills.forEach((pill) => {
        pill.addEventListener("click", () => {
            sourcePills.forEach((item) => item.classList.remove("active"));
            pill.classList.add("active");
            activeSource = pill.dataset.source || "all";
            void performSearch(searchInput.value.trim() || "Pavalamalli Video Song");
        });
    });

    trendingChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            trendingChips.forEach((item) => item.classList.remove("active"));
            chip.classList.add("active");
            searchInput.value = chip.dataset.query;
            void performSearch(chip.dataset.query);
        });
    });

    searchBtn.addEventListener("click", () => void performSearch(searchInput.value.trim()));
    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") void performSearch(searchInput.value.trim());
    });

    async function performSearch(query) {
        if (!query) return;
        emptyState.classList.add("hidden");
        loadingState.classList.remove("hidden");
        resultsGrid.querySelectorAll(".track-card").forEach((card) => card.remove());

        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(activeSource)}`);
            if (!response.ok) throw new Error("Search request failed");
            const data = await response.json();
            lastSearchResults = Array.isArray(data.results) ? data.results.map(normalizeTrack) : [];
            resultsCount.textContent = `${lastSearchResults.length} tracks`;
            if (lastSearchResults.length) renderResults(lastSearchResults);
            else emptyState.classList.remove("hidden");
            if (document.getElementById("videoView").classList.contains("active")) renderVideoView();
        } catch (error) {
            resultsCount.textContent = "0 tracks";
            emptyState.classList.remove("hidden");
            showToast("Search is unavailable. Please try again.");
        } finally {
            loadingState.classList.add("hidden");
        }
    }

    function makeTrackCard(track, { videoOnly = false } = {}) {
        const isFavorite = favorites.some((favorite) => getTrackKey(favorite) === getTrackKey(track));
        const card = document.createElement("div");
        card.className = "track-card";
        const sourceClass = String(track.source || "youtube").toLowerCase();
        const sourceLabel = escapeHtml(String(track.source || "youtube").toUpperCase());
        const thumbnail = escapeAttribute(track.thumbnail || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100");

        card.innerHTML = `
            <img src="${thumbnail}" class="card-thumb" alt="">
            <div class="card-info">
                <div class="card-title">${escapeHtml(track.title)}</div>
                <div class="card-meta">
                    <span class="source-tag ${sourceClass}">${sourceLabel}</span>
                    <span><i class="fa-regular fa-clock"></i> ${formatTime(track.duration)}</span>
                </div>
            </div>
            <div class="card-actions">
                <button class="btn-action-fav ${isFavorite ? "active" : ""}" title="Favorite"><i class="fa-${isFavorite ? "solid" : "regular"} fa-heart"></i></button>
                <button class="btn-action-video" title="Play YouTube video"><i class="fa-solid fa-film"></i></button>
                ${videoOnly ? "" : '<button class="btn-action-play" title="Play audio"><i class="fa-solid fa-play"></i></button>'}
            </div>`;

        card.querySelector(".btn-action-fav").addEventListener("click", (event) => {
            event.stopPropagation();
            toggleFavorite(track, card.querySelector(".btn-action-fav"));
        });
        card.querySelector(".btn-action-video").addEventListener("click", (event) => {
            event.stopPropagation();
            userSelectTrack(track, true);
        });
        card.querySelector(".btn-action-play")?.addEventListener("click", (event) => {
            event.stopPropagation();
            userSelectTrack(track, false);
        });
        card.addEventListener("click", () => userSelectTrack(track, isVideoMode));
        return card;
    }

    function renderResults(tracks) {
        tracks.forEach((track) => resultsGrid.appendChild(makeTrackCard(track)));
    }

    function renderVideoView() {
        videoGrid.replaceChildren();
        if (!lastSearchResults.length) {
            videoGrid.innerHTML = '<div class="empty-state"><p>Search for a YouTube video song to play it here.</p></div>';
            return;
        }
        lastSearchResults.forEach((track) => videoGrid.appendChild(makeTrackCard(track, { videoOnly: true })));
    }

    function userSelectTrack(track, videoMode) {
        const selectedTrack = normalizeTrack(track);
        void playTrackLocal(selectedTrack, 0, true, videoMode);
        sendRoomAction("ACTION_PLAY", { track: selectedTrack, position: 0, is_video: videoMode });
    }

    async function resolveYouTubeId(track) {
        const candidate = String(track.youtube_id || track.id || "");
        if (YOUTUBE_ID_PATTERN.test(candidate)) return candidate;

        const response = await fetch(`/api/video?q=${encodeURIComponent(track.title)}`);
        if (!response.ok) throw new Error("Unable to resolve YouTube video");
        const data = await response.json();
        if (!YOUTUBE_ID_PATTERN.test(String(data.video_id || ""))) throw new Error("Invalid YouTube video id");
        track.youtube_id = data.video_id;
        if (!track.thumbnail && data.thumbnail) track.thumbnail = data.thumbnail;
        if (!track.duration && data.duration) track.duration = data.duration;
        return data.video_id;
    }

    function ensureYouTubePlayer() {
        if (youTubePlayer) return Promise.resolve(youTubePlayer);
        if (youTubePlayerPromise) return youTubePlayerPromise;

        youTubePlayerPromise = new Promise((resolve, reject) => {
            const createPlayer = () => {
                if (youTubePlayer || !window.YT?.Player) return;
                youTubePlayer = new window.YT.Player("youtubePlayer", {
                    width: "100%",
                    height: "100%",
                    playerVars: {
                        autoplay: 0,
                        controls: 0,
                        playsinline: 1,
                        rel: 0,
                        modestbranding: 1,
                        origin: window.location.origin,
                    },
                    events: {
                        onReady: () => {
                            youTubePlayer.setVolume(Number(volumeSlider.value));
                            resolve(youTubePlayer);
                        },
                        onStateChange: (event) => {
                            if (!isVideoMode) return;
                            if (event.data === YT_PLAYING) setPlayingUI(true);
                            if (event.data === YT_PAUSED || event.data === 0) setPlayingUI(false);
                        },
                        onError: () => showToast("YouTube could not play this video."),
                    },
                });
            };

            if (window.YT?.Player) {
                createPlayer();
                return;
            }

            const previousReadyHandler = window.onYouTubeIframeAPIReady;
            window.onYouTubeIframeAPIReady = () => {
                if (typeof previousReadyHandler === "function") previousReadyHandler();
                createPlayer();
            };

            if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
                const script = document.createElement("script");
                script.src = "https://www.youtube.com/iframe_api";
                script.async = true;
                script.onerror = () => reject(new Error("YouTube player API could not load"));
                document.head.appendChild(script);
            }
        });
        return youTubePlayerPromise;
    }

    function updatePlayerPresentation(track, videoMode) {
        playerTitle.textContent = track.title;
        playerArtist.textContent = `${String(track.source || "YouTube").toUpperCase()} • ${formatTime(track.duration)}`;
        playerArt.innerHTML = track.thumbnail
            ? `<img src="${escapeAttribute(track.thumbnail)}" alt="">`
            : '<i class="fa-solid fa-music"></i>';
        setModeIndicator(videoMode);
    }

    async function playTrackLocal(track, targetPosition = 0, shouldPlay = true, videoMode = false) {
        if (!track) return;
        const selectedTrack = normalizeTrack(track);
        const previousKey = getTrackKey(currentTrack);
        const nextKey = getTrackKey(selectedTrack);
        const trackChanged = previousKey !== nextKey;
        const modeChanged = isVideoMode !== videoMode;
        const requestId = ++mediaRequestId;
        const position = Math.max(0, Number(targetPosition) || 0);

        currentTrack = selectedTrack;
        isVideoMode = videoMode;
        updatePlayerPresentation(selectedTrack, videoMode);

        if (videoMode) {
            audioPlayer.pause();
            videoPlayerSection.classList.remove("hidden");
            videoTitle.textContent = selectedTrack.title;
            try {
                const videoId = await resolveYouTubeId(selectedTrack);
                const player = await ensureYouTubePlayer();
                if (requestId !== mediaRequestId || getTrackKey(currentTrack) !== nextKey || !isVideoMode) return;

                const isNewVideo = loadedYouTubeId !== videoId;
                if (isNewVideo) {
                    loadedYouTubeId = videoId;
                    if (shouldPlay) player.loadVideoById({ videoId, startSeconds: position });
                    else player.cueVideoById({ videoId, startSeconds: position });
                } else {
                    correctYouTubeDrift(position);
                    setYouTubePlayback(shouldPlay);
                }
            } catch (error) {
                showToast("Unable to load this YouTube video.");
            }
            return;
        }

        videoPlayerSection.classList.add("hidden");
        if (youTubePlayer) youTubePlayer.pauseVideo();
        if (trackChanged || modeChanged || loadedAudioKey !== nextKey) {
            loadedAudioKey = nextKey;
            try {
                const response = await fetch(`/api/stream?q=${encodeURIComponent(selectedTrack.title)}`);
                if (!response.ok) throw new Error("Audio stream failed");
                const data = await response.json();
                if (requestId !== mediaRequestId || getTrackKey(currentTrack) !== nextKey || isVideoMode) return;
                if (!data.stream_url) throw new Error("Audio URL missing");
                loadAudioSource(data.stream_url, position, shouldPlay);
            } catch (error) {
                showToast("Unable to load this audio stream.");
            }
        } else {
            correctAudioDrift(position);
            setAudioPlayback(shouldPlay);
        }
    }

    function loadAudioSource(source, position, shouldPlay) {
        audioPlayer.src = source;
        const startAudio = () => {
            correctAudioDrift(position, true);
            setAudioPlayback(shouldPlay);
        };
        audioPlayer.addEventListener("loadedmetadata", startAudio, { once: true });
        audioPlayer.load();
        if (audioPlayer.readyState >= 1) startAudio();
    }

    function setAudioPlayback(shouldPlay) {
        if (shouldPlay) {
            audioPlayer.play().then(() => setPlayingUI(true)).catch(() => {
                setPlayingUI(false);
                if (activeRoomCode) showToast("Tap play once to allow synced audio in this browser.");
            });
        } else {
            audioPlayer.pause();
            setPlayingUI(false);
        }
    }

    function setYouTubePlayback(shouldPlay) {
        if (!youTubePlayer) return;
        if (shouldPlay) {
            youTubePlayer.playVideo();
            setPlayingUI(true);
        } else {
            youTubePlayer.pauseVideo();
            setPlayingUI(false);
        }
    }

    function correctAudioDrift(targetPosition, force = false) {
        if (!Number.isFinite(audioPlayer.duration)) return;
        if (force || Math.abs(audioPlayer.currentTime - targetPosition) > DRIFT_TOLERANCE_SECONDS) {
            try { audioPlayer.currentTime = Math.min(targetPosition, audioPlayer.duration); } catch (_) { /* metadata still loading */ }
        }
    }

    function correctYouTubeDrift(targetPosition) {
        if (!youTubePlayer?.getCurrentTime) return;
        const currentPosition = Number(youTubePlayer.getCurrentTime()) || 0;
        if (Math.abs(currentPosition - targetPosition) > DRIFT_TOLERANCE_SECONDS) {
            youTubePlayer.seekTo(targetPosition, true);
        }
    }

    function activePosition() {
        if (isVideoMode && youTubePlayer?.getCurrentTime) return Number(youTubePlayer.getCurrentTime()) || 0;
        return Number(audioPlayer.currentTime) || 0;
    }

    function activeDuration() {
        if (isVideoMode && youTubePlayer?.getDuration) return Number(youTubePlayer.getDuration()) || currentTrack?.duration || 0;
        return Number(audioPlayer.duration) || currentTrack?.duration || 0;
    }

    function isActivePlaying() {
        if (isVideoMode && youTubePlayer?.getPlayerState) return youTubePlayer.getPlayerState() === YT_PLAYING;
        return !audioPlayer.paused;
    }

    function updateTimeline() {
        const duration = activeDuration();
        const position = activePosition();
        if (!duration) return;
        scrubberFill.style.width = `${Math.min(100, (position / duration) * 100)}%`;
        currentTimeEl.textContent = formatTime(position);
        totalDurationEl.textContent = formatTime(duration);
    }

    setInterval(updateTimeline, 250);

    playPauseBtn.addEventListener("click", () => {
        if (!currentTrack) return;
        const shouldPlay = !isActivePlaying();
        if (isVideoMode) setYouTubePlayback(shouldPlay);
        else setAudioPlayback(shouldPlay);
        sendRoomAction(shouldPlay ? "ACTION_PLAY" : "ACTION_PAUSE", {
            track: currentTrack,
            position: activePosition(),
            is_video: isVideoMode,
        });
    });

    scrubberTrack.addEventListener("click", (event) => {
        const duration = activeDuration();
        if (!duration) return;
        const rect = scrubberTrack.getBoundingClientRect();
        const position = Math.max(0, Math.min(duration, ((event.clientX - rect.left) / rect.width) * duration));
        if (isVideoMode && youTubePlayer) youTubePlayer.seekTo(position, true);
        else audioPlayer.currentTime = position;
        updateTimeline();
        sendRoomAction("ACTION_SEEK", { position });
    });

    volumeSlider.addEventListener("input", (event) => {
        const volume = Number(event.target.value);
        audioPlayer.volume = volume / 100;
        if (youTubePlayer) youTubePlayer.setVolume(volume);
    });
    audioPlayer.volume = Number(volumeSlider.value) / 100;

    playerFavBtn.addEventListener("click", () => {
        if (currentTrack) toggleFavorite(currentTrack, playerFavBtn);
    });
    clearQueueBtn?.addEventListener("click", () => {
        currentTrack = null;
        renderQueueView();
    });

    createRoomBtn.addEventListener("click", () => {
        void createSyncRoom(createRoomName.value.trim() || `${getUserName()}'s Sync Lounge`);
    });
    joinRoomBtn.addEventListener("click", () => {
        const roomCode = joinRoomCode.value.trim().toUpperCase();
        if (!roomCode) return showToast("Enter a room code first.");
        connectToSyncRoom(roomCode);
    });
    copyCodeBtn.addEventListener("click", async () => {
        if (!activeRoomCode) return;
        try {
            await navigator.clipboard.writeText(activeRoomCode);
            showToast("Room code copied.");
        } catch (_) {
            showToast(activeRoomCode);
        }
    });
    leaveRoomBtn.addEventListener("click", leaveSyncRoom);

    async function createSyncRoom(name) {
        try {
            const response = await fetch("/api/room/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, host: getUserName() }),
            });
            if (!response.ok) throw new Error("Room creation failed");
            const room = await response.json();
            connectToSyncRoom(room.room_code);
        } catch (_) {
            showToast("Could not create a sync room.");
        }
    }

    function connectToSyncRoom(roomCode) {
        if (roomSocket) roomSocket.close();
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const safeCode = roomCode.replace(/[^A-Z0-9-]/g, "");
        const url = `${protocol}//${window.location.host}/ws/room/${encodeURIComponent(safeCode)}?user=${encodeURIComponent(getUserName())}`;
        const socket = new WebSocket(url);
        roomSocket = socket;

        socket.onopen = () => {
            if (roomSocket !== socket) return;
            activeRoomCode = safeCode;
            updateRoomUI(true, safeCode);
            showToast(`Synced room active: ${safeCode}`);
        };
        socket.onmessage = (event) => {
            try { queueRoomState(JSON.parse(event.data)); } catch (_) { /* ignore malformed messages */ }
        };
        socket.onerror = () => showToast("Room connection error.");
        socket.onclose = () => {
            if (roomSocket !== socket) return;
            roomSocket = null;
            activeRoomCode = null;
            updateRoomUI(false, null);
        };
    }

    function queueRoomState(message) {
        if (!["INIT_ROOM_STATE", "SERVER_STATE", "SERVER_HEARTBEAT"].includes(message.type)) return;
        pendingRoomState = message;
        if (!isApplyingRoomState) void applyPendingRoomStates();
    }

    async function applyPendingRoomStates() {
        isApplyingRoomState = true;
        while (pendingRoomState) {
            const message = pendingRoomState;
            pendingRoomState = null;
            if (message.track) {
                await playTrackLocal(message.track, message.current_position || 0, Boolean(message.is_playing), Boolean(message.is_video));
            }
        }
        isApplyingRoomState = false;
    }

    function sendRoomAction(type, payload) {
        if (!activeRoomCode || !roomSocket || roomSocket.readyState !== WebSocket.OPEN) return;
        roomSocket.send(JSON.stringify({ type, ...payload }));
    }

    function leaveSyncRoom() {
        roomSocket?.close();
        roomSocket = null;
        activeRoomCode = null;
        updateRoomUI(false, null);
        showToast("Left sync room.");
    }

    function updateRoomUI(isConnected, roomCode) {
        liveRoomBanner.classList.toggle("hidden", !isConnected);
        if (isConnected) {
            bannerCode.textContent = roomCode;
            mobileRoomStatusText.textContent = `Room ${roomCode}`;
            pcRoomBadge.textContent = "SYNCED";
            pcRoomBadge.classList.add("active");
            accuracyTag.textContent = "⚡ 1s server pulse";
        } else {
            mobileRoomStatusText.textContent = "Solo";
            pcRoomBadge.textContent = "OFFLINE";
            pcRoomBadge.classList.remove("active");
        }
    }

    function toggleFavorite(track, button) {
        const key = getTrackKey(track);
        const index = favorites.findIndex((favorite) => getTrackKey(favorite) === key);
        if (index >= 0) {
            favorites.splice(index, 1);
            button?.classList.remove("active");
            if (button?.querySelector("i")) button.querySelector("i").className = "fa-regular fa-heart";
            showToast("Removed from favorites.");
        } else {
            favorites.push(normalizeTrack(track));
            button?.classList.add("active");
            if (button?.querySelector("i")) button.querySelector("i").className = "fa-solid fa-heart";
            showToast("Saved to favorites.");
        }
        localStorage.setItem("vishnu_favs_ai", JSON.stringify(favorites));
        updateFavBadge();
        renderFavorites();
    }

    function updateFavBadge() {
        if (pcFavCount) pcFavCount.textContent = favorites.length;
    }

    function renderFavorites() {
        favoritesGrid.replaceChildren();
        if (!favorites.length) {
            favoritesGrid.innerHTML = '<div class="empty-state"><p>No favorite tracks saved yet.</p></div>';
            return;
        }
        favorites.forEach((track) => favoritesGrid.appendChild(makeTrackCard(track)));
    }

    function renderQueueView() {
        queueGrid.replaceChildren();
        if (!currentTrack) {
            queueGrid.innerHTML = '<div class="empty-state"><p>Queue is empty.</p></div>';
            return;
        }
        const card = document.createElement("div");
        card.className = "track-card active";
        card.innerHTML = `<img src="${escapeAttribute(currentTrack.thumbnail || "")}" class="card-thumb" alt=""><div class="card-info"><div class="card-title">Now playing: ${escapeHtml(currentTrack.title)}</div></div>`;
        queueGrid.appendChild(card);
    }

    function formatTime(seconds) {
        const value = Number(seconds) || 0;
        const minutes = Math.floor(value / 60);
        const remaining = Math.floor(value % 60);
        return `${minutes}:${String(remaining).padStart(2, "0")}`;
    }

    function escapeHtml(value) {
        return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function escapeAttribute(value) {
        return escapeHtml(value);
    }

    function showToast(message) {
        toast.textContent = message;
        toast.classList.remove("hidden");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.add("hidden"), 3000);
    }

    updateFavBadge();
    void performSearch("Pavalamalli Video Song");
});
