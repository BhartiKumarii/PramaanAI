import { useEffect, useRef } from 'react'

/**
 * A padlock drawn from glowing green particles on a transparent canvas, so it
 * blends into the page background: particles gather into the shape, then keep
 * shimmering, with soft bokeh drifting behind. Static when the viewer prefers
 * reduced motion.
 */
type P = { tx: number; ty: number; x: number; y: number; r: number; a: number; phase: number; speed: number; vein: boolean }
type B = { x: number; y: number; r: number; vx: number; vy: number; a: number }

const GREEN = '74, 222, 128'
const DEEP = '16, 185, 129'

function lockPoints(): Omit<P, 'x' | 'y'>[] {
  const pts: Omit<P, 'x' | 'y'>[] = []
  const add = (tx: number, ty: number, vein = false) =>
    pts.push({ tx, ty, r: vein ? 1.1 + Math.random() * 1.2 : 0.6 + Math.random() * 1.1, a: 0.35 + Math.random() * 0.6,
               phase: Math.random() * Math.PI * 2, speed: 0.6 + Math.random() * 1.4, vein })
  // body: rounded rectangle outline + scattered fill (coordinates in a 200x220 box, centred)
  const bw = 124, bh = 104, bx = -bw / 2, by = 0
  for (let i = 0; i < 260; i++) {
    const t = Math.random()
    const side = Math.floor(Math.random() * 4)
    const x = side === 0 ? bx + t * bw : side === 1 ? bx + bw : side === 2 ? bx + t * bw : bx
    const y = side === 0 ? by : side === 1 ? by + t * bh : side === 2 ? by + bh : by + t * bh
    add(x + (Math.random() - 0.5) * 3, y + (Math.random() - 0.5) * 3)
  }
  for (let i = 0; i < 260; i++) add(bx + Math.random() * bw, by + Math.random() * bh)
  // bright "veins" across the body (random walks)
  for (let v = 0; v < 14; v++) {
    let x = bx + 8 + Math.random() * (bw - 16), y = by + 8 + Math.random() * (bh - 16)
    let ang = Math.random() * Math.PI * 2
    for (let s = 0; s < 18; s++) {
      add(x, y, true)
      ang += (Math.random() - 0.5) * 1.2
      x = Math.min(bx + bw - 4, Math.max(bx + 4, x + Math.cos(ang) * 3.2))
      y = Math.min(by + bh - 4, Math.max(by + 4, y + Math.sin(ang) * 3.2))
    }
  }
  // shackle: thick arc above the body
  const cx = 0, cy = 2, R = 44
  for (let i = 0; i < 300; i++) {
    const a = Math.PI + Math.random() * Math.PI
    const rr = R - 7 + Math.random() * 14
    const legs = Math.random() < 0.35
    if (legs) {
      const side = Math.random() < 0.5 ? -1 : 1
      add(cx + side * (R - 7 + Math.random() * 14), cy - 26 + Math.random() * 28)
    } else {
      add(cx + Math.cos(a) * rr, cy - 26 + Math.sin(a) * rr)
    }
  }
  return pts
}

export function ParticleLock({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    let w = 0, h = 0, dpr = 1, raf = 0
    const base = lockPoints()
    let parts: P[] = []
    let bokeh: B[] = []
    const start = performance.now()

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = canvas.clientWidth
      h = canvas.clientHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      parts = base.map((p) => ({ ...p, x: (Math.random() - 0.5) * w * 1.4, y: (Math.random() - 0.5) * h * 1.4 }))
      bokeh = Array.from({ length: 14 }, () => ({
        x: Math.random() * w, y: Math.random() * h, r: 6 + Math.random() * 22,
        vx: (Math.random() - 0.5) * 0.12, vy: -0.05 - Math.random() * 0.12, a: 0.04 + Math.random() * 0.1,
      }))
    }

    const frame = (now: number) => {
      const t = (now - start) / 1000
      ctx.clearRect(0, 0, w, h)
      const scale = Math.min(w, h) / 230
      const ox = w / 2, oy = h / 2 - 8 * scale

      // soft halo behind the lock
      const halo = ctx.createRadialGradient(ox, oy + 20 * scale, 0, ox, oy + 20 * scale, 120 * scale)
      halo.addColorStop(0, `rgba(${DEEP}, 0.18)`)
      halo.addColorStop(1, `rgba(${DEEP}, 0)`)
      ctx.fillStyle = halo
      ctx.fillRect(0, 0, w, h)

      // bokeh
      for (const b of bokeh) {
        if (!reduce) {
          b.x += b.vx; b.y += b.vy
          if (b.y < -30) { b.y = h + 30; b.x = Math.random() * w }
        }
        const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r)
        g.addColorStop(0, `rgba(${GREEN}, ${b.a})`)
        g.addColorStop(1, `rgba(${GREEN}, 0)`)
        ctx.fillStyle = g
        ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fill()
      }

      // particles gather (first ~2.5 s), then shimmer in place
      const gather = reduce ? 1 : Math.min(1, t / 2.5)
      const ease = 1 - Math.pow(1 - gather, 3)
      const pulse = reduce ? 0 : (Math.sin(t * 0.9) + 1) / 2
      ctx.globalCompositeOperation = 'lighter'
      for (const p of parts) {
        const jitter = reduce ? 0 : Math.sin(t * p.speed + p.phase) * 0.9
        const tx = ox + (p.tx + jitter) * scale
        const ty = oy + (p.ty + Math.cos(t * p.speed * 0.8 + p.phase) * 0.9) * scale
        const sx = ox + p.x, sy = oy + p.y
        const x = sx + (tx - sx) * ease, y = sy + (ty - sy) * ease
        const twinkle = reduce ? 1 : 0.55 + 0.45 * Math.sin(t * p.speed * 2 + p.phase)
        const alpha = p.a * twinkle * (p.vein ? 0.8 + 0.4 * pulse : 1)
        const color = p.vein ? '190, 255, 200' : GREEN
        ctx.fillStyle = `rgba(${color}, ${alpha})`
        ctx.beginPath(); ctx.arc(x, y, p.r * scale * 0.9, 0, Math.PI * 2); ctx.fill()
        if (p.vein || p.r > 1.4) {
          ctx.fillStyle = `rgba(${GREEN}, ${alpha * 0.18})`
          ctx.beginPath(); ctx.arc(x, y, p.r * scale * 3, 0, Math.PI * 2); ctx.fill()
        }
      }
      ctx.globalCompositeOperation = 'source-over'
      if (!reduce) raf = requestAnimationFrame(frame)
    }

    resize()
    raf = requestAnimationFrame(frame)
    const onResize = () => { resize(); if (reduce) raf = requestAnimationFrame(frame) }
    window.addEventListener('resize', onResize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize) }
  }, [])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
