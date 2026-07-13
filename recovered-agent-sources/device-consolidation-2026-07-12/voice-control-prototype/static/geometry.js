/* ═══════════════════════════════════════════════════════════════
   M.U.S.E Voice — Sacred Geometry Animated Background
   Renders rotating flower-of-life + sacred patterns on canvas
   ═══════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    const canvas = document.getElementById('bg-canvas');
    const ctx = canvas.getContext('2d');
    let W, H, cx, cy;
    let time = 0;
    let intensity = 0.5; // 0-1, modulated by voice state

    function resize() {
        W = canvas.width = window.innerWidth * window.devicePixelRatio;
        H = canvas.height = window.innerHeight * window.devicePixelRatio;
        canvas.style.width = window.innerWidth + 'px';
        canvas.style.height = window.innerHeight + 'px';
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        cx = window.innerWidth / 2;
        cy = window.innerHeight / 2;
    }
    resize();
    window.addEventListener('resize', resize);

    // Draw a circle
    function circle(x, y, r, stroke, lineWidth, alpha) {
        ctx.beginPath();
        ctx.arc(x, y, Math.max(0.5, r), 0, Math.PI * 2);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineWidth || 1;
        ctx.globalAlpha = alpha || 1;
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    // Flower of Life pattern
    function drawFlowerOfLife(centerX, centerY, radius, rotation, alpha) {
        const r = Math.max(1, radius);
        const nodes = [];
        
        // Center circle
        nodes.push({ x: centerX, y: centerY });
        
        // First ring (6 circles)
        for (let i = 0; i < 6; i++) {
            const angle = rotation + (i * Math.PI / 3);
            nodes.push({
                x: centerX + r * Math.cos(angle),
                y: centerY + r * Math.sin(angle)
            });
        }

        // Second ring (6 more)
        for (let i = 0; i < 6; i++) {
            const angle = rotation + (i * Math.PI / 3) + Math.PI / 6;
            nodes.push({
                x: centerX + r * Math.sqrt(3) * Math.cos(angle),
                y: centerY + r * Math.sqrt(3) * Math.sin(angle)
            });
        }

        // Draw all circles
        ctx.lineWidth = 1;
        for (const node of nodes) {
            circle(node.x, node.y, r, 'rgba(212, 175, 55, 0.08)', 1, alpha);
        }
    }

    // Metatron's Cube
    function drawMetatronsCube(centerX, centerY, radius, rotation, alpha) {
        const r = Math.max(1, radius);
        const points = [];
        
        for (let i = 0; i < 6; i++) {
            const angle = rotation + (i * Math.PI / 3);
            points.push({
                x: centerX + r * Math.cos(angle),
                y: centerY + r * Math.sin(angle)
            });
        }
        
        // Inner hexagon
        for (let i = 0; i < 6; i++) {
            const angle = rotation + Math.PI / 6 + (i * Math.PI / 3);
            points.push({
                x: centerX + r * 0.5 * Math.cos(angle),
                y: centerY + r * 0.5 * Math.sin(angle)
            });
        }
        
        points.push({ x: centerX, y: centerY });
        
        // Connect all points
        ctx.strokeStyle = 'rgba(0, 217, 255, 0.04)';
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = alpha;
        for (let i = 0; i < points.length; i++) {
            for (let j = i + 1; j < points.length; j++) {
                ctx.beginPath();
                ctx.moveTo(points[i].x, points[i].y);
                ctx.lineTo(points[j].x, points[j].y);
                ctx.stroke();
            }
        }
        ctx.globalAlpha = 1;
    }

    // Golden ratio spiral
    function drawSpiral(centerX, centerY, maxRadius, rotation, alpha) {
        const r = Math.max(1, maxRadius);
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(212, 175, 55, 0.06)';
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = alpha;
        
        const turns = 4;
        const steps = 200;
        for (let i = 0; i <= steps; i++) {
            const t = (i / steps) * turns * Math.PI * 2;
            const radius = (r / steps) * i;
            const x = centerX + radius * Math.cos(t + rotation);
            const y = centerY + radius * Math.sin(t + rotation);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    // Particle system
    const particles = [];
    const PARTICLE_COUNT = 40;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            vx: (Math.random() - 0.5) * 0.15,
            vy: (Math.random() - 0.5) * 0.15,
            size: Math.random() * 1.5 + 0.5,
            twinkle: Math.random() * Math.PI * 2,
            color: Math.random() > 0.5 ? 'gold' : 'cyan',
        });
    }

    function drawParticles() {
        for (const p of particles) {
            p.x += p.vx * (0.5 + intensity);
            p.y += p.vy * (0.5 + intensity);
            p.twinkle += 0.02;
            
            // Wrap around
            if (p.x < 0) p.x = window.innerWidth;
            if (p.x > window.innerWidth) p.x = 0;
            if (p.y < 0) p.y = window.innerHeight;
            if (p.y > window.innerHeight) p.y = 0;
            
            const flicker = 0.3 + 0.7 * (Math.sin(p.twinkle) * 0.5 + 0.5);
            const color = p.color === 'gold' 
                ? `rgba(212, 175, 55, ${0.3 * flicker})`
                : `rgba(0, 217, 255, ${0.25 * flicker})`;
            
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // Main render loop
    function render() {
        // Clear with slight trail effect
        ctx.fillStyle = 'rgba(6, 10, 20, 0.92)';
        ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);

        const baseR = Math.min(window.innerWidth, window.innerHeight) * 0.35;
        
        // Large central flower of life
        drawFlowerOfLife(cx, cy, baseR * 0.15, time * 0.0001, 0.6 + intensity * 0.3);
        
        // Outer flower of life
        drawFlowerOfLife(cx, cy, baseR * 0.3, -time * 0.00008, 0.4);
        
        // Metatron's cube
        drawMetatronsCube(cx, cy, baseR * 0.5, time * 0.00005, 0.5 + intensity * 0.2);
        
        // Spiral
        drawSpiral(cx, cy, baseR * 0.8, time * 0.0002, 0.4);
        drawSpiral(cx, cy, baseR * 0.8, -time * 0.0002 + Math.PI, 0.4);
        
        // Large faint circles
        circle(cx, cy, baseR, 'rgba(212, 175, 55, 0.04)', 1, 1);
        circle(cx, cy, baseR * 0.66, 'rgba(0, 217, 255, 0.03)', 1, 1);
        circle(cx, cy, baseR * 0.33, 'rgba(212, 175, 55, 0.05)', 1, 1);
        
        // Particles
        drawParticles();
        
        time += 16;
        requestAnimationFrame(render);
    }

    // Expose intensity control
    window.MUSE_GEOMETRY = {
        setIntensity(val) { intensity = Math.max(0, Math.min(1, val)); },
        pulse() { 
            intensity = 1;
            setTimeout(() => { intensity = 0.5; }, 300);
        }
    };

    render();
})();
