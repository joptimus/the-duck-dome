function toFilterId(size, color) {
  return `bolt-glow-${size}-${String(color).replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

export function BoltIcon({ size = 16, color = "#00D4FF", glow = true, style = {} }) {
  const filterId = toFilterId(size, color);

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={style}>
      {glow ? (
        <>
          <defs>
            <filter id={filterId}>
              <feGaussianBlur stdDeviation="2" />
            </filter>
          </defs>
          <path
            d="M13 2L4.5 12.5H11L10 22L18.5 11.5H12L13 2Z"
            fill={color}
            opacity={0.3}
            filter={`url(#${filterId})`}
          />
        </>
      ) : null}
      <path d="M13 2L4.5 12.5H11L10 22L18.5 11.5H12L13 2Z" fill={color} />
      <path
        d="M13 2L4.5 12.5H11L10 22L18.5 11.5H12L13 2Z"
        fill="#FFFFFF"
        opacity={0.35}
      />
    </svg>
  );
}

