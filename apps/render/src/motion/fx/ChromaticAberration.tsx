import React, { useId } from "react";
import { AbsoluteFill } from "remotion";

const CHANNELS = [
  { key: "r", matrix: "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", dir: 1 },
  { key: "g", matrix: "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0", dir: 0 },
  { key: "b", matrix: "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0", dir: -1 },
] as const;

/**
 * RGB split: the children are rendered three times (R, G, B isolated with SVG
 * colour matrices) and recombined with `screen`; R and B are offset by
 * `amount` px along `angle`. amount = 0 reproduces the original exactly.
 */
export const ChromaticAberration: React.FC<{ amount?: number; angle?: number; children: React.ReactNode }> = ({
  amount = 6,
  angle = 0,
  children,
}) => {
  const id = useId().replace(/:/g, "");
  if (amount < 0.25) return <AbsoluteFill>{children}</AbsoluteFill>;
  const rad = (angle * Math.PI) / 180;
  return (
    <AbsoluteFill style={{ isolation: "isolate", background: "#000" }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        {CHANNELS.map((c) => (
          <filter key={c.key} id={`ca-${id}-${c.key}`} colorInterpolationFilters="sRGB">
            <feColorMatrix type="matrix" values={c.matrix} />
          </filter>
        ))}
      </svg>
      {CHANNELS.map((c) => (
        <AbsoluteFill
          key={c.key}
          style={{
            filter: `url(#ca-${id}-${c.key})`,
            mixBlendMode: "screen",
            transform: `translate(${Math.cos(rad) * amount * c.dir}px, ${Math.sin(rad) * amount * c.dir}px)`,
          }}
        >
          {children}
        </AbsoluteFill>
      ))}
    </AbsoluteFill>
  );
};
