import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import type { Point } from '@/lib/steering';
import { vertexPositions, buildSteeringVector } from '@/lib/steering';
import type { SteeringVector, VertexDef } from '@/lib/types';

interface OctagonProps {
  vertices: VertexDef[];
  profileId: string;
  locked?: boolean;
  /** Controlled node position in unit space (-1..1). */
  node: Point;
  onNodeChange: (p: Point) => void;
  onVector: (v: SteeringVector) => void;
  size?: number;
}

const VIEW = 320; // SVG viewBox units
const CENTER = VIEW / 2;
const R = 128; // octagon circumradius in view units
const INSCRIBED = R * Math.cos(Math.PI / 8); // node constrained to inscribed circle

function toView(p: Point): Point {
  return { x: CENTER + p.x * R, y: CENTER + p.y * R };
}

export function Octagon({
  vertices,
  profileId,
  locked = false,
  node,
  onNodeChange,
  onVector,
  size = 320,
}: OctagonProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);
  const [glow, setGlow] = useState('#3dd68c');
  const [pulse, setPulse] = useState(false);
  const debounceRef = useRef<number | null>(null);

  const unitVerts = useMemo(() => vertexPositions(vertices.length, 1), [vertices.length]);
  const viewVerts = useMemo(() => unitVerts.map(toView), [unitVerts]);
  const polygon = useMemo(
    () => viewVerts.map((p) => `${p.x},${p.y}`).join(' '),
    [viewVerts],
  );

  // Recompute steering whenever node moves; push glow var + debounced emit.
  useEffect(() => {
    const v = buildSteeringVector(profileId, node, vertices);
    setGlow(v.glowState.color);
    setPulse(v.glowState.pulse);
    document.documentElement.style.setProperty('--octa-glow', v.glowState.color);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => onVector(v), 120);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [node, profileId, vertices, onVector]);

  const clampToInscribed = useCallback((unit: Point): Point => {
    // Constrain the central node to the octagon's inscribed circle.
    const maxUnit = INSCRIBED / R;
    const d = Math.hypot(unit.x, unit.y);
    if (d <= maxUnit) return unit;
    const s = maxUnit / d;
    return { x: unit.x * s, y: unit.y * s };
  }, []);

  const pointerToUnit = useCallback((clientX: number, clientY: number): Point => {
    const svg = svgRef.current!;
    const rect = svg.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * VIEW;
    const vy = ((clientY - rect.top) / rect.height) * VIEW;
    return clampToInscribed({ x: (vx - CENTER) / R, y: (vy - CENTER) / R });
  }, [clampToInscribed]);

  // Pointer capture on the SVG keeps all move/up events flowing to this element
  // even if the pointer leaves it mid-drag — more robust than window listeners.
  const startDrag = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (locked) return;
      e.preventDefault();
      dragging.current = true;
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* capture may fail for synthetic pointers; drag still works */
      }
      onNodeChange(pointerToUnit(e.clientX, e.clientY));
    },
    [locked, onNodeChange, pointerToUnit],
  );

  const handleMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (!dragging.current || locked) return;
      onNodeChange(pointerToUnit(e.clientX, e.clientY));
    },
    [locked, onNodeChange, pointerToUnit],
  );

  const endDrag = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    dragging.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }, []);

  const nodeView = toView(node);

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      width={size}
      height={size}
      onPointerDown={startDrag}
      onPointerMove={handleMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      className="octa-glow-transition touch-none select-none"
      style={{
        filter: pulse ? undefined : `drop-shadow(0 0 14px ${glow})`,
        animation: pulse ? 'octa-pulse 1.6s ease-in-out infinite' : undefined,
        maxWidth: '100%',
      }}
    >
      <defs>
        <radialGradient id="octaFill" cx="50%" cy="50%" r="55%">
          <stop offset="0%" stopColor={glow} stopOpacity="0.16" />
          <stop offset="70%" stopColor={glow} stopOpacity="0.04" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Spokes to each vertex */}
      {viewVerts.map((p, i) => (
        <line
          key={`spoke-${i}`}
          x1={CENTER}
          y1={CENTER}
          x2={p.x}
          y2={p.y}
          stroke="var(--hairline)"
          strokeWidth={1}
        />
      ))}

      {/* Octagon body */}
      <polygon
        points={polygon}
        fill="url(#octaFill)"
        stroke={glow}
        strokeWidth={2}
        className="octa-glow-transition"
        strokeLinejoin="round"
      />

      {/* Tension lines node -> each vertex (live energy beams) */}
      {viewVerts.map((p, i) => (
        <line
          key={`beam-${i}`}
          x1={nodeView.x}
          y1={nodeView.y}
          x2={p.x}
          y2={p.y}
          stroke={vertices[i].accent}
          strokeWidth={1}
          strokeOpacity={0.45}
        />
      ))}

      {/* Vertex dots + labels */}
      {viewVerts.map((p, i) => {
        const outward = 1.16;
        const lx = CENTER + (p.x - CENTER) * outward;
        const ly = CENTER + (p.y - CENTER) * outward;
        return (
          <g key={`v-${i}`}>
            <circle cx={p.x} cy={p.y} r={5} fill={vertices[i].accent}>
              <title>{vertices[i].description}</title>
            </circle>
            <text
              x={lx}
              y={ly}
              fill="var(--ink-dim)"
              fontSize={9}
              fontFamily="'JetBrains Mono', monospace"
              letterSpacing="0.1em"
              textAnchor="middle"
              dominantBaseline="middle"
              style={{ textTransform: 'uppercase' }}
            >
              {vertices[i].label}
            </text>
          </g>
        );
      })}

      {/* Central draggable node */}
      <motion.g
        animate={{ x: nodeView.x - CENTER, y: nodeView.y - CENTER }}
        transition={{ type: 'spring', stiffness: 520, damping: 38 }}
      >
        <circle cx={CENTER} cy={CENTER} r={16} fill={glow} fillOpacity={0.18} />
        <circle
          cx={CENTER}
          cy={CENTER}
          r={9}
          fill={glow}
          stroke="#0a0e14"
          strokeWidth={2}
          style={{ cursor: locked ? 'not-allowed' : 'grab' }}
        />
      </motion.g>
    </svg>
  );
}
