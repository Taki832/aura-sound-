// AuraSound 2032 — Canvas & Beat-Reactive Visualizer Engine

class AudioVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.animId = null;
        this.bars = 32;
        this.values = new Array(this.bars).fill(10);
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        if (!this.canvas) return;
        this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 300;
        this.canvas.height = 120;
    }

    start() {
        if (this.animId) return;
        this.draw();
    }

    stop() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
    }

    draw() {
        if (!this.canvas || !this.ctx) return;
        const width = this.canvas.width;
        const height = this.canvas.height;
        const barWidth = (width / this.bars) - 4;

        this.ctx.clearRect(0, 0, width, height);

        for (let i = 0; i < this.bars; i++) {
            // Beat reactivity depends on actual playback
            const isPlaying = window.isPlaying || false;
            const targetHeight = isPlaying ? (Math.random() * (height * 0.8) + 12) : 4;
            this.values[i] += (targetHeight - this.values[i]) * 0.2;

            const x = i * (barWidth + 4);
            const y = height - this.values[i];

            // Neon Gradient
            const grad = this.ctx.createLinearGradient(0, height, 0, 0);
            grad.addColorStop(0, '#1DB954');
            grad.addColorStop(1, '#00e5ff');

            this.ctx.fillStyle = grad;
            this.ctx.shadowBlur = 15;
            this.ctx.shadowColor = '#1DB954';
            
            // Draw rounded bars
            this.ctx.beginPath();
            this.ctx.roundRect(x, y, barWidth, this.values[i], [6, 6, 0, 0]);
            this.ctx.fill();
        }

        this.animId = requestAnimationFrame(() => this.draw());
    }
}

class HeroCanvasVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.initParticles();
        this.time = 0;
        this.draw();
    }

    resize() {
        if (!this.canvas) return;
        this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
        this.canvas.height = this.canvas.parentElement ? this.canvas.parentElement.clientHeight : 185;
    }

    initParticles() {
        this.particles = [];
        for (let i = 0; i < 40; i++) {
            this.particles.push({
                x: Math.random() * (this.canvas ? this.canvas.width : 600),
                y: Math.random() * (this.canvas ? this.canvas.height : 185),
                radius: Math.random() * 3 + 1,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                color: Math.random() > 0.5 ? '#1DB954' : '#450AF5'
            });
        }
    }

    draw() {
        if (!this.canvas || !this.ctx) return;
        const width = this.canvas.width;
        const height = this.canvas.height;
        this.time += 0.02;

        this.ctx.clearRect(0, 0, width, height);

        // Draw dynamic neon aura wave
        this.ctx.beginPath();
        this.ctx.moveTo(0, height);
        for (let x = 0; x <= width; x += 10) {
            const y = height * 0.65 + Math.sin(x * 0.015 + this.time) * 18 + Math.cos(x * 0.008 - this.time * 0.8) * 12;
            this.ctx.lineTo(x, y);
        }
        this.ctx.lineTo(width, height);
        this.ctx.closePath();
        
        const grad = this.ctx.createLinearGradient(0, 0, width, height);
        grad.addColorStop(0, 'rgba(69, 10, 245, 0.3)');
        grad.addColorStop(0.5, 'rgba(29, 185, 84, 0.25)');
        grad.addColorStop(1, 'rgba(0, 229, 255, 0.2)');
        this.ctx.fillStyle = grad;
        this.ctx.fill();

        // Particles
        for (let p of this.particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > width) p.vx *= -1;
            if (p.y < 0 || p.y > height) p.vy *= -1;

            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = p.color;
            this.ctx.shadowBlur = 10;
            this.ctx.shadowColor = p.color;
            this.ctx.fill();
        }

        requestAnimationFrame(() => this.draw());
    }
}

window.visualizerEngine = null;
document.addEventListener('DOMContentLoaded', () => {
    window.visualizerEngine = new AudioVisualizer('visualizerCanvas');
    window.visualizerEngine.start();
    new HeroCanvasVisualizer('heroCanvas');
});
