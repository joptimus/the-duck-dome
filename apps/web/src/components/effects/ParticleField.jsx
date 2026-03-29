import { useRef, useEffect } from 'react';

const PARTICLE_COLORS = ["#00D4FF", "#A855F7", "#C084FC", "#00FFA3"];
const PARTICLE_COUNT = 45;

export function ParticleField() {
  const canvasRef = useRef(null);
  const particles = useRef([]);
  const animFrame = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let w, h;

    const resize = () => {
      w = canvas.width = canvas.parentElement.offsetWidth;
      h = canvas.height = canvas.parentElement.offsetHeight;
    };
    resize();

    particles.current = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.current.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.2,
        s: Math.random() * 2 + 0.5,
        c: PARTICLE_COLORS[~~(Math.random() * PARTICLE_COLORS.length)],
        a: Math.random() * 0.3 + 0.05,
        p: Math.random() * Math.PI * 2,
        ps: 0.008 + Math.random() * 0.012,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h);

      particles.current.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.p += p.ps;

        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        const alpha = p.a * (0.5 + 0.5 * Math.sin(p.p));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.s, 0, Math.PI * 2);
        ctx.fillStyle = p.c;
        ctx.globalAlpha = alpha;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.s * 3.5, 0, Math.PI * 2);
        ctx.globalAlpha = alpha * 0.07;
        ctx.fill();
      });

      ctx.globalAlpha = 1;
      animFrame.current = requestAnimationFrame(draw);
    };

    animFrame.current = requestAnimationFrame(draw);
    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(animFrame.current);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  );
}
