// AuraSound 2032 — Aura Island WebGL 3D Spatial Social Environment
class AuraIsland {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container || !window.THREE) return;
        
        this.members = [];
        this.avatars = [];
        this.animId = null;
        
        this.initThreeJS();
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    initThreeJS() {
        // Scene setup
        this.scene = new THREE.Scene();
        
        // Camera setup
        this.camera = new THREE.PerspectiveCamera(60, this.container.clientWidth / 250, 0.1, 1000);
        this.camera.position.set(0, 15, 30);
        this.camera.lookAt(0, 0, 0);

        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth || 350, 250);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.innerHTML = '';
        this.container.appendChild(this.renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        
        const pointLight = new THREE.PointLight(0x1DB954, 1.5, 50);
        pointLight.position.set(0, 20, 0);
        this.scene.add(pointLight);

        // Draw Island Base (Floating glowing ring)
        const ringGeo = new THREE.RingGeometry(10, 12, 64);
        const ringMat = new THREE.MeshBasicMaterial({ 
            color: 0x1DB954, 
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.8
        });
        this.islandRing = new THREE.Mesh(ringGeo, ringMat);
        this.islandRing.rotation.x = Math.PI / 2;
        this.scene.add(this.islandRing);

        // Inner glowing core
        const coreGeo = new THREE.CircleGeometry(10, 64);
        const coreMat = new THREE.MeshBasicMaterial({ 
            color: 0x00E5FF, 
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.2
        });
        this.islandCore = new THREE.Mesh(coreGeo, coreMat);
        this.islandCore.rotation.x = Math.PI / 2;
        this.islandCore.position.y = -0.1;
        this.scene.add(this.islandCore);
        
        // Particle system for ambiance
        const particlesGeo = new THREE.BufferGeometry();
        const particlesCount = 200;
        const posArray = new Float32Array(particlesCount * 3);
        for(let i=0; i<particlesCount*3; i++) {
            posArray[i] = (Math.random() - 0.5) * 40;
        }
        particlesGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        const particlesMat = new THREE.PointsMaterial({
            size: 0.2,
            color: 0x1DB954,
            transparent: true,
            opacity: 0.5
        });
        this.particles = new THREE.Points(particlesGeo, particlesMat);
        this.scene.add(this.particles);
    }

    resize() {
        if (!this.renderer) return;
        const width = this.container.clientWidth || 350;
        const height = 250;
        this.renderer.setSize(width, height);
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
    }

    createAvatarNode(name, index, total) {
        const group = new THREE.Group();
        
        // Sphere Avatar
        const geometry = new THREE.SphereGeometry(1.5, 32, 32);
        const material = new THREE.MeshPhongMaterial({ 
            color: 0x1DB954,
            emissive: 0x00E5FF,
            emissiveIntensity: 0.5,
            shininess: 100
        });
        const sphere = new THREE.Mesh(geometry, material);
        group.add(sphere);

        // HTML Label for Name
        const labelDiv = document.createElement('div');
        labelDiv.className = 'aura-label';
        labelDiv.textContent = name;
        labelDiv.style.position = 'absolute';
        labelDiv.style.color = '#fff';
        labelDiv.style.fontSize = '12px';
        labelDiv.style.fontWeight = 'bold';
        labelDiv.style.textShadow = '0 2px 4px rgba(0,0,0,0.8)';
        labelDiv.style.pointerEvents = 'none';
        this.container.appendChild(labelDiv);

        const angle = (index / total) * Math.PI * 2;
        const radius = 6;
        
        return {
            group: group,
            sphere: sphere,
            label: labelDiv,
            baseAngle: angle,
            radius: radius,
            yOffset: Math.random() * Math.PI * 2
        };
    }

    setMembers(memberList) {
        if (!this.scene) return;
        
        // Remove old avatars
        this.avatars.forEach(a => {
            this.scene.remove(a.group);
            if (a.label && a.label.parentNode) {
                a.label.parentNode.removeChild(a.label);
            }
        });
        this.avatars = [];
        this.members = memberList;

        const total = memberList.length;
        memberList.forEach((m, i) => {
            const avatar = this.createAvatarNode(m, i, total);
            this.scene.add(avatar.group);
            this.avatars.push(avatar);
        });
    }

    start() {
        if (this.animId) return;
        this.clock = new THREE.Clock();
        this.animate();
    }

    stop() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
    }

    updateLabels() {
        const widthHalf = this.container.clientWidth / 2;
        const heightHalf = 250 / 2;

        this.avatars.forEach(a => {
            const vector = new THREE.Vector3();
            a.group.getWorldPosition(vector);
            vector.y += 2.5; // Offset label above sphere
            vector.project(this.camera);

            const x = (vector.x * widthHalf) + widthHalf;
            const y = -(vector.y * heightHalf) + heightHalf;

            a.label.style.left = `${x}px`;
            a.label.style.top = `${y}px`;
            a.label.style.transform = 'translate(-50%, -50%)';
            a.label.style.display = (vector.z > 1) ? 'none' : 'block';
        });
    }

    animate() {
        if (!this.renderer) return;
        
        const time = this.clock.getElapsedTime();

        // Rotate scene slightly for dynamic feel
        this.scene.rotation.y = Math.sin(time * 0.2) * 0.2;
        
        // Pulse island ring
        this.islandRing.scale.setScalar(1 + Math.sin(time * 2) * 0.05);

        // Rotate particles
        this.particles.rotation.y = time * 0.05;

        // Animate avatars
        this.avatars.forEach((a, i) => {
            // Orbit slowly
            const currentAngle = a.baseAngle + (time * 0.5);
            a.group.position.x = Math.cos(currentAngle) * a.radius;
            a.group.position.z = Math.sin(currentAngle) * a.radius;
            
            // Bob up and down
            a.group.position.y = 2 + Math.sin(time * 2 + a.yOffset) * 1.5;
            
            // Pulse emission
            a.sphere.material.emissiveIntensity = 0.3 + Math.abs(Math.sin(time * 3 + i)) * 0.5;
        });

        this.renderer.render(this.scene, this.camera);
        this.updateLabels();
        
        this.animId = requestAnimationFrame(() => this.animate());
    }
}

window.auraIsland = null;
document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('auraIslandContainer');
    if (el) {
        // Setup Three.js wait
        let checkThree = setInterval(() => {
            if (window.THREE) {
                clearInterval(checkThree);
                window.auraIsland = new AuraIsland('auraIslandContainer');
                window.auraIsland.start();
            }
        }, 100);
    }
});
