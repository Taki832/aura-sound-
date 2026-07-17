// AuraSound 2032 — Aura Island 3D/2D Spatial Social Environment

class AuraIsland {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;
        this.canvas = document.createElement('canvas');
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.members = [];
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.animId = null;
    }

    resize() {
        if (!this.canvas) return;
        this.canvas.width = this.container.clientWidth || 350;
        this.canvas.height = 250;
    }

    setMembers(memberList) {
        this.members = memberList.map((m, i) => ({
            name: m,
            x: 50 + (i * 70) % (this.canvas.width - 60),
            y: 80 + Math.sin(i) * 40,
            angle: Math.random() * Math.PI * 2
        }));
    }

    start() {
        if (this.animId) return;
        this.animate();
    }

    stop() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
    }

    animate() {
        if (!this.canvas || !this.ctx) return;
        const w = this.canvas.width;
        const h = this.canvas.height;

        this.ctx.clearRect(0, 0, w, h);

        // Draw Island Base (Futuristic Floating Ring)
        this.ctx.beginPath();
        this.ctx.ellipse(w / 2, h / 2 + 30, w * 0.4, h * 0.25, 0, 0, Math.PI * 2);
        const islandGrad = this.ctx.createRadialGradient(w/2, h/2, 10, w/2, h/2, w*0.4);
        islandGrad.addColorStop(0, 'rgba(29, 185, 84, 0.3)');
        islandGrad.addColorStop(1, 'rgba(18, 18, 18, 0.8)');
        this.ctx.fillStyle = islandGrad;
        this.ctx.fill();
        this.ctx.strokeStyle = '#1DB954';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        // Draw Members as glowing avatars
        this.members.forEach((m, idx) => {
            m.y += Math.sin(Date.now() / 300 + idx) * 0.5; // Floating effect

            // Pulse ring
            this.ctx.beginPath();
            this.ctx.arc(m.x, m.y, 22 + Math.sin(Date.now() / 200 + idx) * 3, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(0, 229, 255, 0.2)';
            this.ctx.fill();

            // Avatar Circle
            this.ctx.beginPath();
            this.ctx.arc(m.x, m.y, 18, 0, Math.PI * 2);
            this.ctx.fillStyle = '#1DB954';
            this.ctx.fill();

            // Label
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = '12px Inter, sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(m.name, m.x, m.y + 32);
        });

        this.animId = requestAnimationFrame(() => this.animate());
    }
}

window.auraIsland = null;
document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('auraIslandContainer');
    if (el) {
        window.auraIsland = new AuraIsland('auraIslandContainer');
        window.auraIsland.setMembers(['Vishnu (Host)', 'Listener 1', 'Listener 2']);
        window.auraIsland.start();
    }
});
