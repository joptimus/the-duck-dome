import { useMemo } from "react";
import styles from "./Waveform.module.css";

export function Waveform({ color = "#00D4FF", bars = 16 }) {
  const barConfigs = useMemo(
    () =>
      Array.from({ length: bars }, (_, index) => ({
        duration: 0.3 + Math.random() * 0.5,
        delay: index * 0.04,
      })),
    [bars],
  );

  return (
    <div className={styles.container}>
      {barConfigs.map((config, index) => (
        <div
          key={index}
          className={styles.bar}
          style={{
            background: color,
            animation: `barPulse ${config.duration}s ease-in-out ${config.delay}s infinite alternate`,
          }}
        />
      ))}
    </div>
  );
}

