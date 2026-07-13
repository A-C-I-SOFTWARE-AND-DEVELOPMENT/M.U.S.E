/* ═══════════════════════════════════════════════════════════════
   M.U.S.E Voice — Core Voice Engine
   Web Speech API (STT/TTS) + WebSocket to Hermes backend
   ═══════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // ─── State ──────────────────────────────────────────────────
    const State = {
        recognition: null,
        synthesis: window.speechSynthesis,
        voices: [],
        selectedVoice: null,
        isListening: false,
        isThinking: false,
        isSpeaking: false,
        voiceMode: 'push',  // push | hold | continuous
        autoTTS: true,
        yolo: true,
        wakeWord: 'muse',
        rate: 1.0,
        pitch: 1.0,
        ws: null,
        reconnectTimer: null,
        audioContext: null,
        analyser: null,
        mediaStream: null,
        currentTranscript: '',
        continuousRestartTimer: null,
        heldStart: false,
    };

    // ─── DOM References ─────────────────────────────────────────
    const $ = (s) => document.querySelector(s);
    const orb = $('#muse-orb');
    const orbLabel = $('#orb-label');
    const messages = $('#messages');
    const liveTranscript = $('#live-transcript');
    const transcriptText = liveTranscript.querySelector('.transcript-text');
    const textInput = $('#text-input');
    const textSend = $('#text-send');
    const statusIndicator = $('#status-indicator');
    const statusDot = statusIndicator.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('.status-text');
    const waveform = $('#waveform');
    const wfCtx = waveform.getContext('2d');

    // ─── Status Management ──────────────────────────────────────
    function setStatus(state, text) {
        statusIndicator.className = 'status-pill ' + (state || '');
        statusText.textContent = text;
    }

    function setOrbState(state, label) {
        orb.className = 'muse-orb ' + state;
        if (label !== undefined) orbLabel.textContent = label;
    }

    // ─── Messages ───────────────────────────────────────────────
    function addMessage(role, text) {
        // Remove welcome message
        const welcome = messages.querySelector('.welcome-msg');
        if (welcome) welcome.remove();

        const el = document.createElement('div');
        el.className = 'msg ' + role;
        
        // Basic markdown: code blocks, inline code, bold
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => 
                `<pre style="background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;font-family:'SF Mono',monospace;margin:8px 0"><code>${code.trim()}</code></pre>`)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        
        el.innerHTML = html;
        messages.appendChild(el);
        scrollMessages();
        return el;
    }

    function addThinking() {
        const el = document.createElement('div');
        el.className = 'msg thinking';
        el.innerHTML = '<span>MUSE is thinking</span><span class="thinking-dots"><span></span><span></span><span></span></span>';
        messages.appendChild(el);
        scrollMessages();
        return el;
    }

    function scrollMessages() {
        const conv = $('#conversation');
        conv.scrollTop = conv.scrollHeight;
    }

    // ─── Speech Recognition (STT) ───────────────────────────────
    function initSpeechRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            console.warn('Speech Recognition not supported');
            return false;
        }

        State.recognition = new SR();
        State.recognition.continuous = State.voiceMode === 'continuous';
        State.recognition.interimResults = true;
        State.recognition.lang = 'en-US';
        State.recognition.maxAlternatives = 1;

        State.recognition.onstart = () => {
            State.isListening = true;
            setOrbState('listening', 'Listening...');
            liveTranscript.classList.remove('hidden');
            transcriptText.textContent = '';
            startWaveform();
            if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.9);
        };

        State.recognition.onresult = (event) => {
            let interim = '';
            let final = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += transcript;
                } else {
                    interim += transcript;
                }
            }

            if (interim) {
                transcriptText.textContent = interim;
            }

            if (final) {
                State.currentTranscript = (State.currentTranscript + ' ' + final).trim();
                transcriptText.textContent = State.currentTranscript;

                // In continuous mode, check for wake word
                if (State.voiceMode === 'continuous') {
                    checkWakeWord(State.currentTranscript);
                }
            }
        };

        State.recognition.onerror = (event) => {
            console.error('STT error:', event.error);
            if (event.error === 'not-allowed') {
                setStatus('', 'Mic blocked');
                addMessage('assistant', 'I need microphone access to hear you. Please allow microphone permissions and try again.');
            } else if (event.error === 'no-speech') {
                // Normal, just restart if in continuous mode
            } else if (event.error === 'aborted') {
                // Intentional
            }
        };

        State.recognition.onend = () => {
            State.isListening = false;
            stopWaveform();
            if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);

            // In continuous mode, auto-restart
            if (State.voiceMode === 'continuous' && !State.isThinking && !State.isSpeaking) {
                State.continuousRestartTimer = setTimeout(() => {
                    if (State.voiceMode === 'continuous') {
                        try { State.recognition.start(); } catch(e) {}
                    }
                }, 500);
            }

            // In push mode, if we have a transcript, send it
            if (State.voiceMode === 'push' && State.currentTranscript) {
                const msg = State.currentTranscript;
                State.currentTranscript = '';
                liveTranscript.classList.add('hidden');
                sendMessage(msg);
            }

            // In hold mode, send transcript when recording ends
            if (State.voiceMode === 'hold' && State.currentTranscript) {
                const msg = State.currentTranscript;
                State.currentTranscript = '';
                liveTranscript.classList.add('hidden');
                sendMessage(msg);
            }

            if (!State.currentTranscript) {
                liveTranscript.classList.add('hidden');
                if (!State.isThinking && !State.isSpeaking) {
                    setOrbState('idle', getModeLabel());
                }
            }
        };

        return true;
    }

    function startListening() {
        if (!State.recognition) {
            if (!initSpeechRecognition()) {
                addMessage('assistant', 'Voice recognition is not supported in this browser. Please use Chrome or Edge. You can still type messages below.');
                return;
            }
        }

        State.currentTranscript = '';
        try {
            State.recognition.continuous = State.voiceMode === 'continuous';
            State.recognition.start();
        } catch(e) {
            console.error('Start listening error:', e);
        }
    }

    function stopListening() {
        if (State.recognition && State.isListening) {
            try { State.recognition.stop(); } catch(e) {}
        }
    }

    // ─── Wake Word Detection ────────────────────────────────────
    function checkWakeWord(transcript) {
        const lower = transcript.toLowerCase().trim();
        const wake = State.wakeWord.toLowerCase().trim();
        
        if (lower.startsWith(wake)) {
            // Remove wake word and send the rest
            const command = lower.substring(wake.length).trim();
            if (command.length > 0) {
                State.currentTranscript = '';
                liveTranscript.classList.add('hidden');
                stopListening();
                sendMessage(command);
            }
        }
    }

    // ─── Send Message to Hermes ─────────────────────────────────
    function sendMessage(text) {
        text = text.trim();
        if (!text) return;

        // Handle stop command
        if (text.toLowerCase() === 'stop talking' || text.toLowerCase() === 'stop') {
            stopSpeaking();
            return;
        }

        addMessage('user', text);
        setOrbState('thinking', 'Thinking...');
        setStatus('thinking', 'Processing...');
        State.isThinking = true;
        if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.7);

        // Use WebSocket if available, otherwise fall back to fetch
        if (State.ws && State.ws.readyState === WebSocket.OPEN) {
            State.ws.send(JSON.stringify({
                type: 'message',
                text: text,
                yolo: State.yolo,
            }));
        } else {
            // Fallback: POST /api/chat
            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, yolo: State.yolo }),
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    handleResponse('Error: ' + data.error);
                } else {
                    handleResponse(data.response);
                }
            })
            .catch(err => handleResponse('Connection error: ' + err.message));
        }
    }

    function handleResponse(text) {
        State.isThinking = false;

        // Remove thinking indicator
        const thinking = messages.querySelector('.msg.thinking');
        if (thinking) thinking.remove();

        if (!text || !text.trim()) {
            text = '(No response from Hermes)';
        }

        addMessage('assistant', text);
        setStatus('online', 'Ready');
        
        if (State.autoTTS && State.synthesis) {
            // Small delay to ensure UI updates first
            setTimeout(() => {
                try {
                    speak(text);
                } catch(e) {
                    console.error('TTS error:', e);
                    setOrbState('idle', getModeLabel());
                    if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);
                }
            }, 100);
        } else {
            setOrbState('idle', getModeLabel());
            if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);
        }
    }

    // ─── Text-to-Speech ─────────────────────────────────────────
    function speak(text) {
        if (!State.synthesis) {
            setOrbState('idle', getModeLabel());
            return;
        }

        // Strip markdown for speech
        let cleanText = text
            .replace(/```[\s\S]*?```/g, ' [code block] ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/[#*_~|>]/g, '')
            .replace(/---/g, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim();

        // Split into chunks for long text (synthesis can choke on very long strings)
        const chunks = splitText(cleanText, 200);
        let chunkIndex = 0;

        State.isSpeaking = true;
        setOrbState('speaking', 'Speaking...');
        setStatus('', 'Speaking...');
        if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.8);
        startWaveform();

        function speakNext() {
            if (chunkIndex >= chunks.length) {
                // Done speaking
                State.isSpeaking = false;
                stopWaveform();
                setOrbState('idle', getModeLabel());
                setStatus('online', 'Ready');
                if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);
                
                // Resume listening in continuous mode
                if (State.voiceMode === 'continuous') {
                    setTimeout(() => startListening(), 300);
                }
                return;
            }

            const utter = new SpeechSynthesisUtterance(chunks[chunkIndex]);
            utter.rate = State.rate;
            utter.pitch = State.pitch;
            utter.volume = 1.0;

            if (State.selectedVoice) {
                utter.voice = State.selectedVoice;
            }

            utter.onend = () => {
                chunkIndex++;
                speakNext();
            };

            utter.onerror = () => {
                chunkIndex++;
                speakNext();
            };

            State.synthesis.speak(utter);
        }

        speakNext();
    }

    function splitText(text, maxLen) {
        const sentences = text.match(/[^.!?]+[.!?]*/g) || [text];
        const chunks = [];
        let current = '';

        for (const sentence of sentences) {
            if ((current + sentence).length > maxLen) {
                if (current) chunks.push(current.trim());
                current = sentence;
            } else {
                current += sentence;
            }
        }
        if (current) chunks.push(current.trim());
        return chunks.length ? chunks : [text];
    }

    function stopSpeaking() {
        if (State.synthesis) {
            State.synthesis.cancel();
        }
        State.isSpeaking = false;
        stopWaveform();
        setOrbState('idle', getModeLabel());
        setStatus('online', 'Ready');
        if (window.MUSE_GEOMETRY) window.MUSE_GEOMETRY.setIntensity(0.5);
    }

    // ─── Waveform Visualization ─────────────────────────────────
    let waveformRAF = null;

    async function setupAudioAnalyser() {
        try {
            State.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            State.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const source = State.audioContext.createMediaStreamSource(State.mediaStream);
            State.analyser = State.audioContext.createAnalyser();
            State.analyser.fftSize = 128;
            source.connect(State.analyser);
        } catch(e) {
            console.warn('Audio analyser setup failed:', e);
        }
    }

    function startWaveform() {
        // Resize waveform canvas
        const rect = waveform.parentElement.getBoundingClientRect();
        waveform.width = rect.width * window.devicePixelRatio;
        waveform.height = rect.height * window.devicePixelRatio;
        wfCtx.scale(window.devicePixelRatio, window.devicePixelRatio);

        const data = State.analyser ? new Uint8Array(State.analyser.frequencyBinCount) : null;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const baseR = rect.width / 2;

        function draw() {
            wfCtx.clearRect(0, 0, rect.width, rect.height);

            if (data && State.analyser) {
                State.analyser.getByteFrequencyData(data);
                
                const bars = 48;
                wfCtx.lineWidth = 2;
                
                for (let i = 0; i < bars; i++) {
                    const angle = (i / bars) * Math.PI * 2;
                    const dataIndex = Math.floor((i / bars) * data.length);
                    const amplitude = data[dataIndex] / 255;
                    const r1 = baseR - 4;
                    const r2 = baseR - 4 + amplitude * 20;
                    
                    const x1 = cx + r1 * Math.cos(angle);
                    const y1 = cy + r1 * Math.sin(angle);
                    const x2 = cx + r2 * Math.cos(angle);
                    const y2 = cy + r2 * Math.sin(angle);
                    
                    const grad = wfCtx.createLinearGradient(x1, y1, x2, y2);
                    grad.addColorStop(0, 'rgba(0, 217, 255, 0.8)');
                    grad.addColorStop(1, 'rgba(212, 175, 55, 0.2)');
                    wfCtx.strokeStyle = grad;
                    
                    wfCtx.beginPath();
                    wfCtx.moveTo(x1, y1);
                    wfCtx.lineTo(x2, y2);
                    wfCtx.stroke();
                }
            } else {
                // Fake waveform (when no mic analyser)
                const bars = 48;
                const t = Date.now() / 200;
                wfCtx.lineWidth = 2;
                
                for (let i = 0; i < bars; i++) {
                    const angle = (i / bars) * Math.PI * 2;
                    const amplitude = (Math.sin(t + i * 0.5) * 0.5 + 0.5) * 0.4 + 0.1;
                    const r1 = baseR - 4;
                    const r2 = baseR - 4 + amplitude * 20;
                    
                    const x1 = cx + r1 * Math.cos(angle);
                    const y1 = cy + r1 * Math.sin(angle);
                    const x2 = cx + r2 * Math.cos(angle);
                    const y2 = cy + r2 * Math.sin(angle);
                    
                    const color = State.isSpeaking 
                        ? 'rgba(212, 175, 55, 0.8)' 
                        : 'rgba(0, 217, 255, 0.6)';
                    wfCtx.strokeStyle = color;
                    
                    wfCtx.beginPath();
                    wfCtx.moveTo(x1, y1);
                    wfCtx.lineTo(x2, y2);
                    wfCtx.stroke();
                }
            }

            waveformRAF = requestAnimationFrame(draw);
        }
        draw();
    }

    function stopWaveform() {
        if (waveformRAF) {
            cancelAnimationFrame(waveformRAF);
            waveformRAF = null;
        }
        wfCtx.clearRect(0, 0, waveform.width, waveform.height);
    }

    // ─── WebSocket Connection ───────────────────────────────────
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        
        try {
            State.ws = new WebSocket(wsUrl);
        } catch(e) {
            console.warn('WebSocket failed, using REST fallback');
            return;
        }

        State.ws.onopen = () => {
            setStatus('online', 'Connected');
        };

        State.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch(data.type) {
                case 'thinking':
                    // Already showing thinking indicator
                    break;
                    
                case 'chunk':
                    // Stream chunk - update or create streaming message
                    let streamMsg = messages.querySelector('.msg.streaming');
                    if (!streamMsg) {
                        const thinking = messages.querySelector('.msg.thinking');
                        if (thinking) thinking.remove();
                        streamMsg = document.createElement('div');
                        streamMsg.className = 'msg assistant streaming';
                        messages.appendChild(streamMsg);
                    }
                    streamMsg.textContent += data.text;
                    scrollMessages();
                    break;
                    
                case 'done':
                    // Remove streaming message - handleResponse will add the final one
                    const streamDone = messages.querySelector('.msg.streaming');
                    if (streamDone) streamDone.remove();
                    handleResponse(data.text);
                    break;
                    
                case 'error':
                    const streamErr = messages.querySelector('.msg.streaming');
                    if (streamErr) streamErr.remove();
                    handleResponse('Error: ' + data.error);
                    break;
            }
        };

        State.ws.onerror = () => {
            setStatus('', 'Reconnecting...');
        };

        State.ws.onclose = () => {
            setStatus('', 'Offline (REST mode)');
            // Reconnect after delay
            clearTimeout(State.reconnectTimer);
            State.reconnectTimer = setTimeout(connectWebSocket, 3000);
        };
    }

    // ─── Settings ───────────────────────────────────────────────
    function loadVoices() {
        State.voices = State.synthesis ? State.synthesis.getVoices() : [];
        const select = $('#tts-voice');
        select.innerHTML = '<option value="">Auto (System Default)</option>';
        
        // Prefer English voices
        const englishVoices = State.voices.filter(v => v.lang.startsWith('en'));
        const sorted = [...englishVoices, ...State.voices.filter(v => !v.lang.startsWith('en'))];
        
        for (const voice of sorted) {
            const opt = document.createElement('option');
            opt.value = voice.name;
            opt.textContent = `${voice.name} (${voice.lang})${voice.default ? ' ★' : ''}`;
            select.appendChild(opt);
        }
    }

    function getModeLabel() {
        switch(State.voiceMode) {
            case 'push': return 'Tap to speak';
            case 'hold': return 'Hold to speak';
            case 'continuous': return `Say "${State.wakeWord}" to talk`;
            default: return 'Tap to speak';
        }
    }

    function saveSettings() {
        const settings = {
            voiceMode: State.voiceMode,
            autoTTS: State.autoTTS,
            yolo: State.yolo,
            wakeWord: State.wakeWord,
            rate: State.rate,
            pitch: State.pitch,
            voice: State.selectedVoice ? State.selectedVoice.name : '',
        };
        localStorage.setItem('muse-voice-settings', JSON.stringify(settings));
    }

    function loadSettings() {
        const saved = localStorage.getItem('muse-voice-settings');
        if (saved) {
            try {
                const s = JSON.parse(saved);
                State.voiceMode = s.voiceMode || 'push';
                State.autoTTS = s.autoTTS !== false;
                State.yolo = s.yolo !== false;
                State.wakeWord = s.wakeWord || 'muse';
                State.rate = s.rate || 1.0;
                State.pitch = s.pitch || 1.0;
                
                // Apply to UI
                $('#tts-rate').value = State.rate;
                $('#rate-val').textContent = State.rate.toFixed(1);
                $('#tts-pitch').value = State.pitch;
                $('#pitch-val').textContent = State.pitch.toFixed(1);
                $('#auto-tts').checked = State.autoTTS;
                $('#yolo-mode').checked = State.yolo;
                $('#wake-word-input').value = State.wakeWord;
                
                document.querySelectorAll('.mode-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.mode === State.voiceMode);
                });
                
                $('#wake-word-group').style.display = State.voiceMode === 'continuous' ? 'flex' : 'none';
                
                if (s.voice) {
                    setTimeout(() => {
                        State.selectedVoice = State.voices.find(v => v.name === s.voice) || null;
                        $('#tts-voice').value = s.voice;
                    }, 200);
                }
            } catch(e) {}
        }
    }

    // ─── Event Bindings ─────────────────────────────────────────
    function bindEvents() {
        // Orb click (push-to-talk)
        let holdTimer = null;
        
        orb.addEventListener('mousedown', (e) => {
            if (State.voiceMode === 'hold') {
                e.preventDefault();
                State.heldStart = true;
                holdTimer = setTimeout(() => {
                    if (State.heldStart) startListening();
                }, 150);
            }
        });

        orb.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (State.voiceMode === 'hold') {
                State.heldStart = true;
                holdTimer = setTimeout(() => {
                    if (State.heldStart) startListening();
                }, 150);
            }
        }, { passive: false });

        orb.addEventListener('click', () => {
            if (State.voiceMode === 'hold') return; // handled by mousedown/up
            if (State.isSpeaking) {
                stopSpeaking();
                return;
            }
            if (State.isListening) {
                stopListening();
            } else if (!State.isThinking) {
                startListening();
            }
        });

        orb.addEventListener('mouseup', () => {
            if (State.voiceMode === 'hold') {
                clearTimeout(holdTimer);
                State.heldStart = false;
                if (State.isListening) stopListening();
            }
        });

        orb.addEventListener('touchend', (e) => {
            if (State.voiceMode === 'hold') {
                e.preventDefault();
                clearTimeout(holdTimer);
                State.heldStart = false;
                if (State.isListening) stopListening();
            }
        }, { passive: false });

        // Text input
        const sendFromInput = () => {
            const text = textInput.value.trim();
            if (text) {
                sendMessage(text);
                textInput.value = '';
            }
        };

        textSend.addEventListener('click', sendFromInput);
        textInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendFromInput();
            }
        });

        // Quick action buttons
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                if (action === 'stop-tts') {
                    stopSpeaking();
                } else {
                    sendMessage(btn.dataset.prompt);
                }
            });
        });

        // Welcome hints
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('welcome-hint')) {
                sendMessage(e.target.textContent);
            }
        });

        // Settings panel
        $('#settings-btn').addEventListener('click', () => {
            $('#settings-panel').classList.remove('hidden');
        });

        $('#settings-close').addEventListener('click', () => {
            $('#settings-panel').classList.add('hidden');
        });

        $('.settings-overlay').addEventListener('click', () => {
            $('#settings-panel').classList.add('hidden');
        });

        // Voice mode buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Stop current listening
                if (State.isListening) stopListening();
                
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                State.voiceMode = btn.dataset.mode;
                
                $('#wake-word-group').style.display = State.voiceMode === 'continuous' ? 'flex' : 'none';
                orbLabel.textContent = getModeLabel();
                saveSettings();
                
                if (State.voiceMode === 'continuous') {
                    startListening();
                }
            });
        });

        // Wake word input
        $('#wake-word-input').addEventListener('input', (e) => {
            State.wakeWord = e.target.value.trim() || 'muse';
            if (State.voiceMode === 'continuous') {
                orbLabel.textContent = getModeLabel();
            }
            saveSettings();
        });

        // TTS voice select
        $('#tts-voice').addEventListener('change', (e) => {
            State.selectedVoice = State.voices.find(v => v.name === e.target.value) || null;
            saveSettings();
        });

        // Rate slider
        $('#tts-rate').addEventListener('input', (e) => {
            State.rate = parseFloat(e.target.value);
            $('#rate-val').textContent = State.rate.toFixed(1);
            saveSettings();
        });

        // Pitch slider
        $('#tts-pitch').addEventListener('input', (e) => {
            State.pitch = parseFloat(e.target.value);
            $('#pitch-val').textContent = State.pitch.toFixed(1);
            saveSettings();
        });

        // Auto TTS toggle
        $('#auto-tts').addEventListener('change', (e) => {
            State.autoTTS = e.target.checked;
            saveSettings();
        });

        // YOLO toggle
        $('#yolo-mode').addEventListener('change', (e) => {
            State.yolo = e.target.checked;
            saveSettings();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Space bar - push to talk (when not typing)
            if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                if (State.voiceMode !== 'continuous') {
                    if (State.isListening) {
                        stopListening();
                    } else if (!State.isThinking && !State.isSpeaking) {
                        startListening();
                    }
                }
            }
            
            // Escape - stop everything
            if (e.key === 'Escape') {
                if (State.isSpeaking) stopSpeaking();
                if (State.isListening) stopListening();
                $('#settings-panel').classList.add('hidden');
            }
        });
    }

    // ─── Health Check ───────────────────────────────────────────
    async function checkHealth() {
        try {
            const res = await fetch('/api/health');
            const data = await res.json();
            const statusEl = $('#api-status');
            
            if (data.hermes_available) {
                statusEl.textContent = `Hermes: Connected (${data.hermes_bin})`;
                statusEl.className = 'api-status ok';
                setStatus('online', 'Ready');
            } else {
                statusEl.textContent = `Hermes not found. Install hermes or add to PATH.`;
                statusEl.className = 'api-status err';
                setStatus('', 'Hermes not found');
            }
        } catch(e) {
            setStatus('', 'Backend offline');
        }
    }

    // ─── Init ───────────────────────────────────────────────────
    function init() {
        // Load settings first
        loadSettings();
        
        // Init speech recognition
        initSpeechRecognition();
        
        // Load voices
        if (State.synthesis) {
            loadVoices();
            State.synthesis.onvoiceschanged = loadVoices;
        }
        
        // Setup audio analyser for waveform
        setupAudioAnalyser().catch(() => {});
        
        // Connect WebSocket
        connectWebSocket();
        
        // Bind events
        bindEvents();
        
        // Health check
        checkHealth();
        setInterval(checkHealth, 30000);
        
        // Show welcome
        showWelcome();
        
        // Set initial orb label
        orbLabel.textContent = getModeLabel();
    }

    function showWelcome() {
        messages.innerHTML = `
            <div class="welcome-msg">
                <div class="welcome-icon">
                    <svg viewBox="0 0 64 64" fill="none">
                        <circle cx="32" cy="32" r="28" stroke="url(#wg1)" stroke-width="1.5" opacity="0.4"/>
                        <circle cx="32" cy="32" r="20" stroke="url(#wg1)" stroke-width="1" opacity="0.3"/>
                        <circle cx="32" cy="32" r="12" stroke="url(#wg1)" stroke-width="1" opacity="0.2"/>
                        <circle cx="32" cy="32" r="5" fill="url(#wg2)"/>
                        <defs>
                            <linearGradient id="wg1" x1="0" y1="0" x2="64" y2="64">
                                <stop stop-color="#d4af37"/>
                                <stop offset="1" stop-color="#00d9ff"/>
                            </linearGradient>
                            <radialGradient id="wg2">
                                <stop stop-color="#00d9ff"/>
                                <stop offset="1" stop-color="#d4af37"/>
                            </radialGradient>
                        </defs>
                    </svg>
                </div>
                <h2>MUSE Voice</h2>
                <p>I am MUSE. Speak to me and I will act.<br>Tap the orb below or use your wake word.</p>
                <div class="welcome-hints">
                    <div class="welcome-hint">What can you do?</div>
                    <div class="welcome-hint">Check system status</div>
                    <div class="welcome-hint">Open a project</div>
                    <div class="welcome-hint">Search the web</div>
                </div>
            </div>
        `;
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
