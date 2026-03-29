const AGENT_COLORS = {
  claude: "#FF8A5C",
  codex: "#00FFAA",
  gemini: "#6BAAFF",
  kimi: "#3D9EFF",
  qwen: "#A78BFF",
  kilo: "#EEFF41",
  minimax: "#3DFFC8",
};

export function AgentLogo({ agent, size = 20 }) {
  const color = AGENT_COLORS[agent] || "var(--text-muted)";

  if (agent === "claude") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        {[0, 45, 90, 135].map((angle) => (
          <line
            key={angle}
            x1="12"
            y1="4"
            x2="12"
            y2="10"
            stroke={color}
            strokeWidth="2.2"
            strokeLinecap="round"
            transform={`rotate(${angle} 12 12)`}
          />
        ))}
        <circle cx="12" cy="12" r="2.5" fill={color} />
      </svg>
    );
  }

  if (agent === "codex") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path
          d="M12 3L19.8 7.5V16.5L12 21L4.2 16.5V7.5L12 3Z"
          stroke={color}
          strokeWidth="1.8"
        />
        <circle cx="12" cy="12" r="3" fill={color} opacity="0.8" />
      </svg>
    );
  }

  if (agent === "gemini") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path d="M12 2C12 2 13.5 8 12 12C10.5 8 12 2 12 2Z" fill={color} />
        <path d="M12 22C12 22 10.5 16 12 12C13.5 16 12 22 12 22Z" fill={color} />
        <path d="M2 12C2 12 8 10.5 12 12C8 13.5 2 12 2 12Z" fill={color} />
        <path d="M22 12C22 12 16 13.5 12 12C16 10.5 22 12 22 12Z" fill={color} />
        <circle cx="12" cy="12" r="2" fill={color} />
      </svg>
    );
  }

  if (agent === "kimi") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path d="M16 4a8 8 0 0 1 0 16A6 6 0 0 0 16 4Z" fill={color} opacity="0.9" />
        <circle cx="10" cy="12" r="7" stroke={color} strokeWidth="1.8" fill="none" />
      </svg>
    );
  }

  if (agent === "qwen") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8" stroke={color} strokeWidth="1.8" />
        <circle cx="12" cy="12" r="4" stroke={color} strokeWidth="1.5" opacity="0.6" />
        <circle cx="12" cy="12" r="1.5" fill={color} />
        <line x1="12" y1="4" x2="12" y2="2" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
        <line x1="12" y1="22" x2="12" y2="20" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
        <line x1="4" y1="12" x2="2" y2="12" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
        <line x1="22" y1="12" x2="20" y2="12" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }

  if (agent === "kilo") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path d="M7 4L3 12L7 20" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M17 4L21 12L17 20" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="14" y1="5" x2="10" y2="19" stroke={color} strokeWidth="1.8" strokeLinecap="round" opacity="0.7" />
      </svg>
    );
  }

  if (agent === "minimax") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path d="M2 16C5 10 8 18 12 12C16 6 19 14 22 8" stroke={color} strokeWidth="2" strokeLinecap="round" />
        <circle cx="12" cy="12" r="2" fill={color} />
      </svg>
    );
  }

  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <text
        x="12"
        y="16"
        textAnchor="middle"
        fill={color}
        fontSize="14"
        fontWeight="700"
        fontFamily="Orbitron"
      >
        {agent?.[0]?.toUpperCase() || "?"}
      </text>
    </svg>
  );
}

