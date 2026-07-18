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

window.visualizerEngine = null;
document.addEventListener('DOMContentLoaded', () => {
    window.visualizerEngine = new AudioVisualizer('visualizerCanvas');
    window.visualizerEngine.start();
});
