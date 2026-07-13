/* ═══════════════════════════════════════════════════════════════
   M.U.S.E Voice — Full Control App Engine
   Voice (STT/TTS) + WebSocket + Full Hermes API integration
   ═══════════════════════════════════════════════════════════════ */
(function() {
'use strict';

// Fix #1: Catch unhandled promise rejections that cause opaque JS exceptions
window.addEventListener('unhandledrejection', (e) => { e.preventDefault(); });
window.addEventListener('error', (e) => { if (e.error) e.preventDefault(); });

// ─── State ──────────────────────────────────────────────────
const S = {
    recognition: null, synthesis: window.speechSynthesis, voices: [],
    selectedVoice: null, isListening: false, isThinking: false, isSpeaking: false,
    voiceMode: 'push', autoTTS: true, yolo: true, wakeWord: 'muse',
    rate: 1.0, pitch: 1.0, ws: null, reconnectTimer: null,
    audioContext: null, analyser: null, mediaStream: null,
    currentTranscript: '', micPermissionDenied: false, audioInitialized: false,
};
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const orb = $('#muse-orb'), orbLabel = $('#orb-label'), messages = $('#messages'),
      liveTranscript = $('#live-transcript'), transcriptText = liveTranscript.querySelector('.transcript-text'),
      textInput = $('#text-input'), textSend = $('#text-send'),
      statusIndicator = $('#status-indicator'), statusText = statusIndicator.querySelector('.status-text'),
      waveform = $('#waveform'), wfCtx = waveform.getContext('2d');

// ─── Status ─────────────────────────────────────────────────
function setStatus(state, text) { statusIndicator.className = 'status-pill ' + (state||''); statusText.textContent = text; }
function setOrbState(state, label) { orb.className = 'muse-orb ' + state; if (label !== undefined) orbLabel.textContent = label; }

// ─── Messages ───────────────────────────────────────────────
function addMessage(role, text) {
    const w = messages.querySelector('.welcome-msg'); if (w) w.remove();
    const el = document.createElement('div'); el.className = 'msg ' + role;
    let html = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/```(\w*)\n?([\s\S]*?)```/g, (_,l,c) => `<pre><code>${c.trim()}</code></pre>`)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    el.innerHTML = html; messages.appendChild(el); scrollMessages(); return el;
}
function scrollMessages() { $('#conversation').scrollTop = $('#conversation').scrollHeight; }

// ─── STT (with dogfood fix: prevent infinite loop on permission denied) ───
function initSTT() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return false;
    S.recognition = new SR();
    S.recognition.continuous = false; S.recognition.interimResults = true;
    S.recognition.lang = 'en-US'; S.recognition.maxAlternatives = 1;

    S.recognition.onstart = () => {
        S.isListening = true; S.micPermissionDenied = false;
        setOrbState('listening', 'Listening...'); liveTranscript.classList.remove('hidden');
        transcriptText.textContent = ''; startWaveform();
        if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.9);
    };
    S.recognition.onresult = (e) => {
        let interim = '', final = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            if (e.results[i].isFinal) final += t; else interim += t;
        }
        if (interim) transcriptText.textContent = interim;
        if (final) {
            S.currentTranscript = (S.currentTranscript + ' ' + final).trim();
            transcriptText.textContent = S.currentTranscript;
            if (S.voiceMode === 'continuous') checkWakeWord(S.currentTranscript);
        }
    };
    S.recognition.onerror = (e) => {
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
            S.micPermissionDenied = true;
            setStatus('', 'Mic blocked');
            addMessage('assistant', 'Microphone access denied. Please allow mic permissions in your browser settings, then try again. You can still type messages below.');
        }
    };
    S.recognition.onend = () => {
        S.isListening = false; stopWaveform();
        if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);

        // FIX: Don't auto-restart if mic permission was denied
        if (S.voiceMode === 'continuous' && !S.micPermissionDenied && !S.isThinking && !S.isSpeaking) {
            setTimeout(() => { if (S.voiceMode === 'continuous' && !S.micPermissionDenied) { try { S.recognition.start(); } catch(e){} } }, 800);
        }

        if (S.currentTranscript && S.voiceMode !== 'continuous') {
            const msg = S.currentTranscript; S.currentTranscript = '';
            liveTranscript.classList.add('hidden'); sendMessage(msg);
        }
        if (!S.currentTranscript) {
            liveTranscript.classList.add('hidden');
            if (!S.isThinking && !S.isSpeaking) setOrbState('idle', getModeLabel());
        }
    };
    return true;
}

// FIX: Defer audio analyser setup until user interacts (not on page load)
async function setupAudioAnalyser() {
    if (S.audioInitialized) return;
    S.audioInitialized = true;
    try {
        S.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        S.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const source = S.audioContext.createMediaStreamSource(S.mediaStream);
        S.analyser = S.audioContext.createAnalyser();
        S.analyser.fftSize = 128; source.connect(S.analyser);
    } catch(e) { console.warn('Audio analyser unavailable:', e.message); }
}

function startListening() {
    if (!S.recognition) { if (!initSTT()) { addMessage('assistant', 'Voice recognition needs Chrome or Edge. You can type below.'); return; } }
    // Setup audio analyser on first user interaction
    setupAudioAnalyser().catch(() => {});
    S.currentTranscript = '';
    try { S.recognition.continuous = S.voiceMode === 'continuous'; S.recognition.start(); }
    catch(e) { console.error('STT start error:', e); }
}
function stopListening() { if (S.recognition && S.isListening) { try { S.recognition.stop(); } catch(e){} } }

function checkWakeWord(t) {
    const lower = t.toLowerCase().trim(), wake = S.wakeWord.toLowerCase().trim();
    if (lower.startsWith(wake)) {
        const cmd = lower.substring(wake.length).trim();
        if (cmd.length > 0) {
            S.currentTranscript = ''; liveTranscript.classList.add('hidden');
            stopListening(); sendMessage(cmd);
        }
    }
}

// ─── Send Message ───────────────────────────────────────────
function sendMessage(text) {
    text = text.trim(); if (!text) return;
    if (text.toLowerCase() === 'stop talking' || text.toLowerCase() === 'stop') { stopSpeaking(); return; }
    addMessage('user', text);
    setOrbState('thinking', 'Thinking...'); setStatus('thinking', 'Processing...');
    S.isThinking = true;
    if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.7);

    if (S.ws && S.ws.readyState === WebSocket.OPEN) {
        S.ws.send(JSON.stringify({ type: 'message', text, yolo: S.yolo }));
    } else {
        fetch('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ message: text, yolo: S.yolo }) })
        .then(r => r.json())
        .then(d => handleResponse(d.error ? ('Error: ' + d.error) : d.response))
        .catch(e => handleResponse('Connection error: ' + e.message));
    }
}

function handleResponse(text) {
    S.isThinking = false;
    const thinking = messages.querySelector('.msg.thinking'); if (thinking) thinking.remove();
    const streaming = messages.querySelector('.msg.streaming'); if (streaming) streaming.remove();
    if (!text || !text.trim()) text = '(No response from Hermes)';
    addMessage('assistant', text); setStatus('online', 'Ready');
    if (S.autoTTS && S.synthesis) { setTimeout(() => { try { speak(text); } catch(e) { resetOrbIdle(); } }, 100); }
    else resetOrbIdle();
}
function resetOrbIdle() { setOrbState('idle', getModeLabel()); if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5); }

// ─── TTS ────────────────────────────────────────────────────
function speak(text) {
    if (!S.synthesis) { resetOrbIdle(); return; }
    let clean = text.replace(/```[\s\S]*?```/g,' [code] ').replace(/`([^`]+)`/g,'$1')
        .replace(/\*\*([^*]+)\*\*/g,'$1').replace(/[#*_~|>]/g,'').replace(/---/g,'')
        .replace(/\n{3,}/g,'\n\n').trim();
    const chunks = splitText(clean, 200); let i = 0;
    S.isSpeaking = true; setOrbState('speaking', 'Speaking...'); setStatus('', 'Speaking...');
    if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.8);
    startWaveform();
    function next() {
        if (i >= chunks.length) {
            S.isSpeaking = false; stopWaveform(); resetOrbIdle();
            if (S.voiceMode === 'continuous' && !S.micPermissionDenied) setTimeout(() => startListening(), 400);
            return;
        }
        const u = new SpeechSynthesisUtterance(chunks[i]);
        u.rate = S.rate; u.pitch = S.pitch; u.volume = 1.0;
        if (S.selectedVoice) u.voice = S.selectedVoice;
        u.onend = () => { i++; next(); };
        u.onerror = () => { i++; next(); };
        S.synthesis.speak(u);
    }
    next();
}
function splitText(t, max) {
    const s = t.match(/[^.!?]+[.!?]*/g) || [t]; const chunks = []; let cur = '';
    for (const sent of s) { if ((cur+sent).length > max) { if (cur) chunks.push(cur.trim()); cur = sent; } else cur += sent; }
    if (cur) chunks.push(cur.trim()); return chunks.length ? chunks : [t];
}
function stopSpeaking() {
    if (S.synthesis) S.synthesis.cancel();
    S.isSpeaking = false; stopWaveform(); resetOrbIdle();
}

// ─── Waveform ───────────────────────────────────────────────
let wfRAF = null;
function startWaveform() {
    const rect = orb.getBoundingClientRect();
    waveform.width = rect.width * devicePixelRatio; waveform.height = rect.height * devicePixelRatio;
    wfCtx.scale(devicePixelRatio, devicePixelRatio);
    const data = S.analyser ? new Uint8Array(S.analyser.frequencyBinCount) : null;
    const cx2 = rect.width/2, cy2 = rect.height/2, baseR = rect.width/2;
    function draw() {
        wfCtx.clearRect(0, 0, rect.width, rect.height);
        const bars = 48;
        if (data && S.analyser) {
            S.analyser.getByteFrequencyData(data);
            for (let i = 0; i < bars; i++) {
                const angle = (i/bars)*Math.PI*2;
                const amp = data[Math.floor((i/bars)*data.length)]/255;
                const r1 = baseR-4, r2 = baseR-4+amp*20;
                const x1=cx2+r1*Math.cos(angle), y1=cy2+r1*Math.sin(angle);
                const x2=cx2+r2*Math.cos(angle), y2=cy2+r2*Math.sin(angle);
                wfCtx.strokeStyle = `rgba(0,217,255,${0.6+amp*0.4})`; wfCtx.lineWidth = 2;
                wfCtx.beginPath(); wfCtx.moveTo(x1,y1); wfCtx.lineTo(x2,y2); wfCtx.stroke();
            }
        } else {
            const t = Date.now()/200;
            for (let i = 0; i < bars; i++) {
                const angle = (i/bars)*Math.PI*2;
                const amp = (Math.sin(t+i*0.5)*0.5+0.5)*0.4+0.1;
                const r1 = baseR-4, r2 = baseR-4+amp*20;
                const x1=cx2+r1*Math.cos(angle), y1=cy2+r1*Math.sin(angle);
                const x2=cx2+r2*Math.cos(angle), y2=cy2+r2*Math.sin(angle);
                wfCtx.strokeStyle = S.isSpeaking ? 'rgba(212,175,55,0.8)' : 'rgba(0,217,255,0.6)';
                wfCtx.lineWidth = 2; wfCtx.beginPath(); wfCtx.moveTo(x1,y1); wfCtx.lineTo(x2,y2); wfCtx.stroke();
            }
        }
        wfRAF = requestAnimationFrame(draw);
    }
    draw();
}
function stopWaveform() { if (wfRAF) { cancelAnimationFrame(wfRAF); wfRAF = null; } wfCtx.clearRect(0,0,waveform.width,waveform.height); }

// ─── WebSocket ──────────────────────────────────────────────
function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try { S.ws = new WebSocket(`${proto}//${location.host}/ws`); } catch(e) { return; }
    S.ws.onopen = () => setStatus('online', 'Connected');
    S.ws.onmessage = (e) => {
        try {
            const d = JSON.parse(e.data);
            switch(d.type) {
                case 'thinking': break;
                case 'chunk':
                    // Fix #7: Use run_id to create separate streaming elements for concurrent messages
                    let sm = d.run_id ? messages.querySelector(`.msg.streaming[data-run-id="${d.run_id}"]`) : messages.querySelector('.msg.streaming');
                    if (!sm) {
                        const th = messages.querySelector('.msg.thinking'); if (th) th.remove();
                        sm = document.createElement('div');
                        sm.className = 'msg assistant streaming';
                        if (d.run_id) sm.setAttribute('data-run-id', d.run_id);
                        messages.appendChild(sm);
                    }
                    sm.textContent += d.text; scrollMessages(); break;
                case 'done':
                    const sd = d.run_id ? messages.querySelector(`.msg.streaming[data-run-id="${d.run_id}"]`) : messages.querySelector('.msg.streaming');
                    if (sd) sd.remove();
                    handleResponse(d.text); break;
                case 'error':
                    const se = d.run_id ? messages.querySelector(`.msg.streaming[data-run-id="${d.run_id}"]`) : messages.querySelector('.msg.streaming');
                    if (se) se.remove();
                    handleResponse('Error: ' + d.error); break;
                case 'delegate_started': addMessage('assistant', `Agent dispatched: ${d.goal}`); break;
            }
        } catch(err) { console.warn('WS message parse error:', err); }
    };
    // Fix #1: Swallow WebSocket errors silently to prevent opaque exception
    S.ws.onerror = () => { /* silent — onclose will handle reconnection */ };
    S.ws.onclose = () => {
        setStatus('', 'Offline (REST)');
        clearTimeout(S.reconnectTimer);
        S.reconnectTimer = setTimeout(connectWS, 3000);
    };
}

// ─── API Helpers ────────────────────────────────────────────
async function api(path, opts) {
    try {
        const r = await fetch(path, opts);
        return await r.json();
    } catch(e) { return { error: e.message }; }
}
async function apiPost(path, body) {
    return api(path, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
}

// ─── Tab Navigation ─────────────────────────────────────────
function switchTab(name) {
    $$('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    $$('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + name));
    // Fix #5: Use non-blocking async loads with loading indicators
    if (name === 'agents') { loadAgentsTab(); }
    if (name === 'system') { loadSystemTab(); }
}

// Fix #5: Load agents tab data in parallel with loading indicators
async function loadAgentsTab() {
    // Show loading immediately
    $('#active-runs').innerHTML = '<div class="empty-state">Loading...</div>';
    $('#cron-list').innerHTML = '<div class="empty-state">Loading...</div>';
    $('#sessions-list').innerHTML = '<div class="empty-state">Loading...</div>';
    // Fire all requests in parallel — don't await sequentially
    refreshActiveRuns();
    refreshCron();
    refreshSessions();
}

// Fix #5: Load system tab data in parallel with loading indicators
async function loadSystemTab() {
    $('#system-status').textContent = 'Loading...';
    $('#gateway-status').textContent = 'Loading...';
    $('#dashboard-status').textContent = 'Loading...';
    $('#tools-grid').innerHTML = '<div class="empty-state">Loading...</div>';
    $('#models-list').textContent = 'Loading...';
    $('#memory-status').textContent = 'Loading...';
    $('#config-display').textContent = 'Loading...';
    // Fire all requests in parallel
    refreshSystemStatus();
    refreshGateway();
    refreshDashboard();
    refreshTools();
    refreshModels();
    refreshMemory();
    refreshConfig();
}

// ─── Agents Tab ─────────────────────────────────────────────
async function refreshActiveRuns() {
    const el = $('#active-runs');
    const d = await api('/api/runs');
    if (d.runs && d.runs.length > 0) {
        el.innerHTML = d.runs.map(r => `<div class="run-item"><div class="run-spinner"></div>
            <div class="run-info"><div class="run-type">${r.type}</div><div class="run-detail">${r.detail}</div></div>
            <div class="run-time">${r.elapsed}s</div></div>`).join('');
    } else { el.innerHTML = '<div class="empty-state">No active agent runs</div>'; }
}

async function refreshCron() {
    const el = $('#cron-list');
    const d = await api('/api/cron');
    el.innerHTML = `<div class="data-item"><pre class="code-block small">${d.stdout || d.error || 'No cron jobs'}</pre></div>`;
}

async function refreshSessions() {
    const el = $('#sessions-list');
    const d = await api('/api/sessions');
    el.innerHTML = `<div class="data-item"><pre class="code-block small">${(d.stdout || d.error || 'No sessions').substring(0, 600)}</pre></div>`;
}

// Session search
async function searchSessions(query) {
    const el = $('#sessions-list');
    el.innerHTML = '<div class="empty-state">Searching...</div>';
    const d = await api('/api/sessions/search?q=' + encodeURIComponent(query));
    const text = d.stdout || d.error || 'No results';
    el.innerHTML = `<div class="data-item"><span style="font-size:11px;color:var(--cyan)">Found ${d.match_count || 0} matches</span><pre class="code-block small">${text.substring(0, 600)}</pre></div>`;
}

// ─── System Tab ─────────────────────────────────────────────
async function refreshSystemStatus() {
    const d = await api('/api/status');
    $('#system-status').textContent = (d.stdout || d.error || 'N/A').substring(0, 1000);
}
async function refreshGateway() {
    const d = await api('/api/gateway');
    $('#gateway-status').textContent = (d.stdout || d.error || 'N/A').substring(0, 400);
}
async function refreshDashboard() {
    const d = await api('/api/dashboard');
    $('#dashboard-status').textContent = (d.stdout || d.error || 'N/A').substring(0, 400);
}
async function refreshTools() {
    const el = $('#tools-grid');
    const d = await api('/api/tools');
    if (d.stdout) {
        // Parse tool lines
        const lines = d.stdout.split('\n').filter(l => l.trim() && !l.includes('Enable'));
        el.innerHTML = lines.map(line => {
            const enabled = !line.toLowerCase().includes('disabled') && !line.toLowerCase().includes('[ ]');
            const name = line.trim().replace(/^[\s\-*\[\]x✓]+/, '').split(/\s{2,}/)[0].substring(0, 20);
            return `<div class="tool-card ${enabled?'enabled':''}"><span class="tool-name">${name}</span><span class="tool-status ${enabled?'on':'off'}"></span></div>`;
        }).join('');
    } else { el.innerHTML = '<div class="empty-state">Could not load tools</div>'; }
}
async function refreshModels() {
    const d = await api('/api/models');
    $('#models-list').textContent = (d.stdout || d.error || 'N/A').substring(0, 800);
}
async function refreshMemory() {
    const d = await api('/api/memory');
    $('#memory-status').textContent = (d.stdout || d.error || 'N/A').substring(0, 400);
}
async function refreshConfig() {
    const d = await api('/api/config');
    $('#config-display').textContent = (d.stdout || d.error || 'N/A').substring(0, 1000);
}

// ─── Settings ───────────────────────────────────────────────
function loadVoices() {
    S.voices = S.synthesis ? S.synthesis.getVoices() : [];
    const sel = $('#tts-voice'); sel.innerHTML = '<option value="">Auto</option>';
    const en = S.voices.filter(v => v.lang.startsWith('en'));
    const other = S.voices.filter(v => !v.lang.startsWith('en'));
    [...en, ...other].forEach(v => {
        const o = document.createElement('option'); o.value = v.name;
        o.textContent = `${v.name} (${v.lang})${v.default?' ★':''}`; sel.appendChild(o);
    });
}
function getModeLabel() {
    if (S.voiceMode === 'push') return 'Tap to speak';
    if (S.voiceMode === 'hold') return 'Hold to speak';
    if (S.voiceMode === 'continuous') return `Say "${S.wakeWord}" to talk`;
    return 'Tap to speak';
}
function saveSettings() {
    localStorage.setItem('muse-voice', JSON.stringify({
        voiceMode: S.voiceMode, autoTTS: S.autoTTS, yolo: S.yolo, wakeWord: S.wakeWord,
        rate: S.rate, pitch: S.pitch, voice: S.selectedVoice ? S.selectedVoice.name : '',
    }));
}
function loadSettings() {
    const s = localStorage.getItem('muse-voice'); if (!s) return;
    try {
        const d = JSON.parse(s);
        S.voiceMode = d.voiceMode || 'push'; S.autoTTS = d.autoTTS !== false; S.yolo = d.yolo !== false;
        S.wakeWord = d.wakeWord || 'muse'; S.rate = d.rate || 1.0; S.pitch = d.pitch || 1.0;
        $('#tts-rate').value = S.rate; $('#rate-val').textContent = S.rate.toFixed(1);
        $('#tts-pitch').value = S.pitch; $('#pitch-val').textContent = S.pitch.toFixed(1);
        $('#auto-tts').checked = S.autoTTS; $('#yolo-mode').checked = S.yolo;
        $('#wake-word-input').value = S.wakeWord;
        $$('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === S.voiceMode));
        $('#wake-word-group').style.display = S.voiceMode === 'continuous' ? 'flex' : 'none';
        if (d.voice) setTimeout(() => { S.selectedVoice = S.voices.find(v => v.name === d.voice); $('#tts-voice').value = d.voice; }, 300);
    } catch(e) {}
}

// ─── Health Check ───────────────────────────────────────────
async function checkHealth() {
    try {
        const d = await api('/api/health');
        const el = $('#api-status');
        if (d.hermes_available) {
            el.textContent = `Hermes Connected | Runs: ${d.active_runs||0}/${d.max_agents||5}`;
            el.className = 'api-status ok';
            if (statusText.textContent === 'Connecting...') { setStatus('online', 'Ready'); orbLabel.textContent = getModeLabel(); }
        } else {
            el.textContent = 'Hermes not found'; el.className = 'api-status err'; setStatus('', 'Hermes not found');
        }
    } catch(e) { setStatus('', 'Backend offline'); }
}

// ─── Event Bindings ─────────────────────────────────────────
function bindEvents() {
    // Tab switching
    $$('.nav-tab').forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

    // Orb interaction
    let holdTimer = null;
    orb.addEventListener('mousedown', (e) => {
        if (S.voiceMode === 'hold') { e.preventDefault(); holdTimer = setTimeout(() => startListening(), 150); }
    });
    orb.addEventListener('touchstart', (e) => {
        if (S.voiceMode === 'hold') { e.preventDefault(); holdTimer = setTimeout(() => startListening(), 150); }
    }, { passive: false });
    orb.addEventListener('click', () => {
        if (S.voiceMode === 'hold') return;
        if (S.isSpeaking) { stopSpeaking(); return; }
        if (S.isListening) stopListening(); else if (!S.isThinking) startListening();
    });
    orb.addEventListener('mouseup', () => { if (S.voiceMode === 'hold') { clearTimeout(holdTimer); if (S.isListening) stopListening(); } });
    orb.addEventListener('touchend', (e) => { if (S.voiceMode === 'hold') { e.preventDefault(); clearTimeout(holdTimer); if (S.isListening) stopListening(); } }, { passive: false });

    // Text input
    const sendText = () => { const t = textInput.value.trim(); if (t) { sendMessage(t); textInput.value = ''; } };
    textSend.addEventListener('click', sendText);
    textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); sendText(); } });

    // Quick actions
    $$('.quick-btn').forEach(b => b.addEventListener('click', () => {
        const action = b.dataset.action;
        if (action === 'stop-tts') stopSpeaking();
        else if (b.dataset.prompt) sendMessage(b.dataset.prompt);
    }));

    // Welcome hints
    document.addEventListener('click', (e) => { if (e.target.classList.contains('welcome-hint')) sendMessage(e.target.textContent); });

    // Settings
    $('#settings-btn').addEventListener('click', () => $('#settings-panel').classList.remove('hidden'));
    $('#settings-close').addEventListener('click', () => $('#settings-panel').classList.add('hidden'));
    $('.settings-overlay').addEventListener('click', () => $('#settings-panel').classList.add('hidden'));

    // Mode buttons
    $$('.mode-btn').forEach(b => b.addEventListener('click', () => {
        if (S.isListening) stopListening();
        $$('.mode-btn').forEach(x => x.classList.remove('active')); b.classList.add('active');
        S.voiceMode = b.dataset.mode;
        $('#wake-word-group').style.display = S.voiceMode === 'continuous' ? 'flex' : 'none';
        orbLabel.textContent = getModeLabel(); saveSettings();
        if (S.voiceMode === 'continuous') startListening();
    }));
    $('#wake-word-input').addEventListener('input', (e) => { S.wakeWord = e.target.value.trim() || 'muse'; if (S.voiceMode === 'continuous') orbLabel.textContent = getModeLabel(); saveSettings(); });
    $('#tts-voice').addEventListener('change', (e) => { S.selectedVoice = S.voices.find(v => v.name === e.target.value); saveSettings(); });
    $('#tts-rate').addEventListener('input', (e) => { S.rate = parseFloat(e.target.value); $('#rate-val').textContent = S.rate.toFixed(1); saveSettings(); });
    $('#tts-pitch').addEventListener('input', (e) => { S.pitch = parseFloat(e.target.value); $('#pitch-val').textContent = S.pitch.toFixed(1); saveSettings(); });
    $('#auto-tts').addEventListener('change', (e) => { S.autoTTS = e.target.checked; saveSettings(); });
    $('#yolo-mode').addEventListener('change', (e) => { S.yolo = e.target.checked; saveSettings(); });

    // Delegate
    $('#delegate-send').addEventListener('click', async () => {
        const goal = $('#delegate-goal').value.trim(); if (!goal) return;
        const tools = $('#delegate-tools').value;
        addMessage('user', `[DELEGATE] ${goal}`);
        if (S.ws && S.ws.readyState === WebSocket.OPEN) {
            S.ws.send(JSON.stringify({ type: 'delegate', goal, yolo: S.yolo, toolsets: tools }));
        } else {
            const d = await apiPost('/api/delegate', { goal, yolo: S.yolo, toolsets: tools });
            handleResponse(d.response || d.error || 'Delegate failed');
        }
        $('#delegate-goal').value = '';
    });

    // Refresh buttons
    $('#refresh-cron')?.addEventListener('click', refreshCron);
    $('#refresh-sessions')?.addEventListener('click', refreshSessions);
    $('#session-search-btn')?.addEventListener('click', () => {
        const q = $('#session-search').value.trim();
        if (q) searchSessions(q); else refreshSessions();
    });
    $('#session-search')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const q = e.target.value.trim();
            if (q) searchSessions(q); else refreshSessions();
        }
    });
    $('#refresh-status')?.addEventListener('click', () => { refreshSystemStatus(); refreshGateway(); refreshDashboard(); });
    $('#refresh-tools')?.addEventListener('click', refreshTools);
    $('#refresh-models')?.addEventListener('click', refreshModels);
    $('#refresh-config')?.addEventListener('click', refreshConfig);

    // Gateway controls
    $$('[data-gateway]').forEach(b => b.addEventListener('click', async () => {
        const d = await apiPost('/api/gateway', { action: b.dataset.gateway });
        refreshGateway();
    }));
    // Dashboard controls
    $$('[data-dashboard]').forEach(b => b.addEventListener('click', async () => {
        const d = await apiPost('/api/dashboard', { action: b.dataset.dashboard });
        refreshDashboard();
    }));
    // Jarvis controls
    $$('[data-jarvis]').forEach(b => b.addEventListener('click', async () => {
        const d = await apiPost('/api/jarvis', { action: b.dataset.jarvis });
        addMessage('assistant', `Jarvis ${b.dataset.jarvis}: ${d.stdout || d.error || 'done'}`);
    }));

    // Keyboard
    document.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
            e.preventDefault();
            if (S.voiceMode !== 'continuous') { if (S.isListening) stopListening(); else if (!S.isThinking && !S.isSpeaking) startListening(); }
        }
        if (e.key === 'Escape') { if (S.isSpeaking) stopSpeaking(); if (S.isListening) stopListening(); $('#settings-panel').classList.add('hidden'); }
    });
}

// ─── Init ───────────────────────────────────────────────────
function init() {
    loadSettings(); initSTT();
    if (S.synthesis) { loadVoices(); S.synthesis.onvoiceschanged = loadVoices; }
    connectWS(); bindEvents(); checkHealth(); setInterval(checkHealth, 15000);
    showWelcome(); orbLabel.textContent = getModeLabel();
    // Fix #6: Save defaults on first load so settings persist across sessions
    if (!localStorage.getItem('muse-voice')) saveSettings();
}
function showWelcome() {
    messages.innerHTML = `<div class="welcome-msg">
        <div class="welcome-icon"><svg viewBox="0 0 64 64" fill="none">
            <circle cx="32" cy="32" r="28" stroke="url(#wg)" stroke-width="1.5" opacity="0.4"/>
            <circle cx="32" cy="32" r="20" stroke="url(#wg)" stroke-width="1" opacity="0.3"/>
            <circle cx="32" cy="32" r="12" stroke="url(#wg)" stroke-width="1" opacity="0.2"/>
            <circle cx="32" cy="32" r="5" fill="url(#wg2)"/>
            <defs><linearGradient id="wg" x1="0" y1="0" x2="64" y2="64"><stop stop-color="#d4af37"/><stop offset="1" stop-color="#00d9ff"/></linearGradient>
            <radialGradient id="wg2"><stop stop-color="#00d9ff"/><stop offset="1" stop-color="#d4af37"/></radialGradient></defs>
        </svg></div>
        <h2>MUSE Voice — Full Control</h2>
        <p>I am MUSE. I have full access to every tool, agent, and feature.<br>Speak or type — I can do anything.</p>
        <div class="welcome-hints">
            <div class="welcome-hint">Give me a system status report</div>
            <div class="welcome-hint">Delegate a web research task</div>
            <div class="welcome-hint">Check my cron jobs</div>
            <div class="welcome-hint">What tools do you have?</div>
            <div class="welcome-hint">Open a project and start coding</div>
        </div>
    </div>`;
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
