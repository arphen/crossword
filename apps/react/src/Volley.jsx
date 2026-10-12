import React, { useEffect, useRef } from 'react';

// The fireworks of a check: each solved word fires from its notch, the edge
// the word is entered through, in the notch's own colour (read from the
// word's chip, which wears the same lane hue), and its chip in the ladder
// answers with a smaller burst. A short rocket runs into the word and bursts
// over it; the hotter the combo, the bigger the burst, with glitter at the top
// tiers and a ring when the run reaches a new tier. A mistake throws red shards off the
// wrong squares instead. One canvas, drawn only while something is in the
// air, so a fifty-word check is a few hundred dots, not a few hundred nodes.

const GRAVITY = 160;
const MAX_PARTICLES = 900;
const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

function seeded(seed) {
  let state = seed >>> 0 || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export default function Volley({ bus }) {
  const canvas = useRef(/** @type {HTMLCanvasElement | null} */ (null));
  const state = useRef({ particles: [], incoming: null, rings: [], frame: 0, last: 0, scale: 1, light: false, seed: 1 });

  useEffect(() => {
    const element = canvas.current;
    if (!bus || !element) return undefined;
    const world = state.current;
    // The context is taken when the first firework goes up, not on mount, so
    // a board that never checks never asks for one.
    let context = null;

    const fit = () => {
      world.scale = Math.min(1.5, window.devicePixelRatio || 1);
      element.width = Math.round(window.innerWidth * world.scale);
      element.height = Math.round(window.innerHeight * world.scale);
    };

    const draw = (time) => {
      const dt = world.last ? Math.min(0.05, (time - world.last) / 1000) : 1 / 60;
      world.last = time;
      const now = performance.now();
      context.setTransform(world.scale, 0, 0, world.scale, 0, 0);
      context.clearRect(0, 0, element.width, element.height);
      context.globalCompositeOperation = world.light ? 'source-over' : 'lighter';
      const alive = [];
      // Bursts thrown this frame join the next one.
      world.incoming = [];
      for (const p of world.particles) {
        if (now < p.born) {
          alive.push(p);
          continue;
        }
        p.age += dt;
        if (p.age >= p.life) {
          if (p.burst) burst(p.burst, p.x, p.y);
          continue;
        }
        p.vx *= 1 - p.drag * dt;
        p.vy = p.vy * (1 - p.drag * dt) + p.gravity * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.spin += p.turn * dt;
        const fade = 1 - p.age / p.life;
        let alpha = p.alpha * (p.kind === 'rocket' ? 1 : fade * fade);
        if (p.twinkle) alpha *= 0.55 + 0.45 * Math.sin(p.age * 38 + p.twinkle);
        context.globalAlpha = Math.max(0, alpha);
        if (p.kind === 'shard') {
          context.fillStyle = p.color;
          context.save();
          context.translate(p.x, p.y);
          context.rotate(p.spin);
          context.beginPath();
          context.moveTo(-p.size, -p.size * 0.4);
          context.lineTo(p.size, 0);
          context.lineTo(-p.size * 0.3, p.size * 0.7);
          context.closePath();
          context.fill();
          context.restore();
        } else {
          // The streak behind a spark is its velocity over a fixed slice of
          // time, capped, so it reads the same at any frame rate.
          const speed = Math.hypot(p.vx, p.vy) || 1;
          const length = Math.min(p.kind === 'rocket' ? 26 : 14, speed * p.trail * 0.012);
          context.strokeStyle = p.color;
          context.lineCap = 'round';
          context.lineWidth = p.size * (p.kind === 'rocket' ? 1 : 0.5 + fade * 0.5);
          context.beginPath();
          context.moveTo(p.x - (p.vx / speed) * length, p.y - (p.vy / speed) * length);
          context.lineTo(p.x, p.y);
          context.stroke();
        }
        alive.push(p);
      }
      world.particles = alive.concat(world.incoming);
      world.incoming = null;
      const rings = [];
      for (const ring of world.rings) {
        if (now < ring.born) {
          rings.push(ring);
          continue;
        }
        ring.age += dt;
        if (ring.age >= ring.life) continue;
        const progress = ring.age / ring.life;
        context.globalAlpha = ring.alpha * (1 - progress);
        context.strokeStyle = ring.color;
        context.lineWidth = ring.width * (1 - progress * 0.6);
        context.beginPath();
        context.arc(ring.x, ring.y, ring.radius * (0.25 + 0.75 * (1 - (1 - progress) ** 3)), 0, Math.PI * 2);
        context.stroke();
        rings.push(ring);
      }
      world.rings = rings;
      context.globalAlpha = 1;
      if (world.particles.length || world.rings.length) {
        world.frame = requestAnimationFrame(draw);
      } else {
        world.frame = 0;
        world.last = 0;
        context.setTransform(1, 0, 0, 1, 0, 0);
        context.clearRect(0, 0, element.width, element.height);
        element.removeAttribute('data-live');
      }
    };

    const wake = () => {
      if (!context) context = element.getContext?.('2d') || null;
      if (!context) {
        world.particles = [];
        world.rings = [];
        return;
      }
      if (world.frame) return;
      element.setAttribute('data-live', '');
      world.frame = requestAnimationFrame(draw);
    };

    const room = () => Math.max(0, MAX_PARTICLES - world.particles.length - (world.incoming?.length || 0));
    const add = (particle) => (world.incoming || world.particles).push(particle);

    // A burst: sparks thrown out in every direction from where a rocket ends.
    function burst(spec, x, y) {
      const random = seeded((world.seed += 7919));
      const { color, level } = spec;
      const count = Math.min(room(), Math.round((16 + level * 9) * (spec.scale || 1)));
      const reach = 105 + level * 32;
      for (let i = 0; i < count; i += 1) {
        const angle = (i / count) * Math.PI * 2 + random() * 0.4;
        const speed = reach * (0.45 + random() * 0.6);
        add({
          kind: 'spark', born: 0, age: 0, life: 0.55 + random() * 0.5 + level * 0.06,
          x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 30,
          drag: 2.1, gravity: GRAVITY, size: 1.6 + random() * 1.1 + level * 0.15,
          color: i % 5 === 0 ? spec.core : color, alpha: 0.95, trail: 2.2, spin: 0, turn: 0,
          twinkle: level >= 3 && i % 3 === 0 ? random() * 6 : 0,
        });
      }
      // A ring only when the run reaches a new tier: the moment worth marking.
      if (spec.tierUp) {
        world.rings.push({ born: 0, age: 0, life: 0.55, x, y, radius: reach * 0.5, width: 1.2 + level * 0.3, color, alpha: 0.45 });
      }
      // The top tiers crackle: a second, smaller round of glitter a beat later.
      if (level >= 4) {
        const later = performance.now() + 160;
        for (let i = 0; i < Math.min(room(), 10 + level * 3); i += 1) {
          const angle = random() * Math.PI * 2;
          const speed = reach * (0.2 + random() * 0.35);
          add({
            kind: 'spark', born: later + random() * 120, age: 0, life: 0.35 + random() * 0.3,
            x: x + Math.cos(angle) * reach * 0.35, y: y + Math.sin(angle) * reach * 0.3,
            vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
            drag: 3, gravity: GRAVITY * 0.5, size: 1.4, color: spec.core, alpha: 1, trail: 1, spin: 0, turn: 0,
            twinkle: random() * 6,
          });
        }
      }
    }

    const unsubscribe = bus.subscribe((event) => {
      if (reducedMotion()) return;
      world.light = document.documentElement.style.getPropertyValue('color-scheme') === 'light';
      if (event.type === 'start') {
        if (element.width !== Math.round(window.innerWidth * Math.min(1.5, window.devicePixelRatio || 1))) fit();
        return;
      }
      if (event.type === 'word' && event.origin) {
        const level = event.beat?.tier ?? 0;
        const color = event.color || (event.direction === 'across' ? '#f0a35c' : '#6fb6f2');
        const core = world.light ? color : '#fff6e8';
        const across = event.direction === 'across';
        // The rocket runs along the word from its notch and climbs a little
        // off it, then bursts over the word.
        const run = Math.max(28, Math.min(event.span * 0.55, 150));
        const rise = 26 + level * 7;
        const time = 0.2 + level * 0.012;
        const vx = across ? run / time : -rise / time;
        const vy = across ? -rise / time : run / time;
        if (room() > 0) {
          world.particles.push({
            kind: 'rocket', born: 0, age: 0, life: time, x: event.origin.x, y: event.origin.y,
            vx, vy, drag: 0, gravity: 0, size: 2.4 + level * 0.25, color: core, alpha: 1, trail: 3.5, spin: 0, turn: 0,
            burst: { color, core, level, tierUp: Boolean(event.beat?.tierUp), scale: event.length > 9 ? 1.2 : 1 },
          });
        }
        // The clue's own notch in the ladder answers with a smaller burst.
        if (event.chip) burst({ color, core, level, tierUp: false, scale: 0.42 }, event.chip.x, event.chip.y);
        // A spit of sparks at the notch itself as it fires.
        const random = seeded((world.seed += 104729));
        for (let i = 0; i < Math.min(room(), 6 + level * 2); i += 1) {
          const spread = (random() - 0.5) * 1.6;
          const base = across ? Math.PI : -Math.PI / 2;
          const speed = 60 + random() * 90;
          world.particles.push({
            kind: 'spark', born: 0, age: 0, life: 0.25 + random() * 0.25,
            x: event.origin.x, y: event.origin.y,
            vx: Math.cos(base + spread) * speed, vy: Math.sin(base + spread) * speed,
            drag: 4, gravity: GRAVITY * 0.4, size: 1.3, color, alpha: 0.9, trail: 1.5, spin: 0, turn: 0, twinkle: 0,
          });
        }
        wake();
      } else if (event.type === 'break') {
        const random = seeded((world.seed += 15485863));
        const red = world.light ? '#c9343f' : '#ff5b62';
        const now = performance.now();
        for (const cell of event.cells || []) {
          const born = now + (cell.delay || 0);
          world.rings.push({ born, age: 0, life: 0.42, x: cell.x, y: cell.y, radius: cell.size * 0.9, width: 2.4, color: red, alpha: 0.85 });
          for (let i = 0; i < Math.min(room(), 9); i += 1) {
            const angle = random() * Math.PI * 2;
            const speed = 70 + random() * 120;
            world.particles.push({
              kind: 'shard', born, age: 0, life: 0.6 + random() * 0.45,
              x: cell.x + (random() - 0.5) * cell.size * 0.6, y: cell.y + (random() - 0.5) * cell.size * 0.6,
              vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 40,
              drag: 1.6, gravity: GRAVITY * 1.8, size: 2.2 + random() * 3, color: i % 3 ? red : '#ffd5d0',
              alpha: 0.95, trail: 0, spin: random() * 6, turn: (random() - 0.5) * 18, twinkle: 0,
            });
          }
        }
        wake();
      }
    });
    fit();
    window.addEventListener('resize', fit);
    return () => {
      unsubscribe();
      window.removeEventListener('resize', fit);
      cancelAnimationFrame(world.frame);
      world.frame = 0;
      world.particles = [];
      world.rings = [];
    };
  }, [bus]);

  return <canvas ref={canvas} className="volley" aria-hidden="true" />;
}
