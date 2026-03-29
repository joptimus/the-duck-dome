import { useState, useEffect } from 'react';
import styles from './ElectricPulse.module.css';

export function ElectricPulse({
  vertical = true,
  color = "#00D4FF",
  minDelay = 3000,
  maxDelay = 7000,
}) {
  const [key, setKey] = useState(0);
  const [duration, setDuration] = useState(1.2);

  useEffect(() => {
    let timeout;
    const schedule = () => {
      const delay = minDelay + Math.random() * (maxDelay - minDelay);
      timeout = setTimeout(() => {
        setDuration(0.8 + Math.random() * 0.8);
        setKey((k) => k + 1);
        schedule();
      }, delay);
    };
    schedule();
    return () => clearTimeout(timeout);
  }, [minDelay, maxDelay]);

  const containerClass = `${styles.container} ${vertical ? styles.vertical : styles.horizontal}`;
  const pulseClass = `${styles.pulse} ${vertical ? styles.pulseVertical : styles.pulseHorizontal}`;
  const animationName = vertical ? 'pulseTravelDown' : 'pulseTravelRight';

  return (
    <div className={containerClass}>
      <div
        key={key}
        className={pulseClass}
        style={{
          background: `radial-gradient(ellipse at center, ${color} 0%, ${color}60 30%, transparent 70%)`,
          boxShadow: `0 0 12px ${color}60, 0 0 24px ${color}25`,
          animation: key > 0 ? `${animationName} ${duration}s ease-out forwards` : 'none',
          opacity: key > 0 ? 1 : 0,
        }}
      />
    </div>
  );
}
