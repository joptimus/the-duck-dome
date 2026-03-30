export function Dot({ color, size = 8 }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        display: "inline-block",
        boxShadow: `0 0 6px ${color}, 0 0 14px ${color}60`,
        animation: "pulse 1.5s ease-in-out infinite",
      }}
    />
  );
}

