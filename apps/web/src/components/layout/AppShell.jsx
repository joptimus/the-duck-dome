import { useEffect, useState } from 'react';
import { ParticleField } from '../effects/ParticleField';
import { AmbientOrbs } from '../effects/AmbientOrbs';
import styles from './AppShell.module.css';

export function AppShell({ sidebar, children, panel }) {
  const [displayPanel, setDisplayPanel] = useState(panel);

  useEffect(() => {
    if (panel) {
      setDisplayPanel(panel);
      return undefined;
    }

    if (!displayPanel) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setDisplayPanel(null);
    }, 360);

    return () => window.clearTimeout(timeoutId);
  }, [panel, displayPanel]);

  return (
    <div className={styles.root}>
      <div className={styles.background}>
        <ParticleField />
        <AmbientOrbs />
      </div>

      <aside className={styles.sidebar}>
        {sidebar}
      </aside>

      <div className={styles.mainWithPanel}>
        <div className={styles.content}>
          {children}
        </div>
        <div
          className={`${styles.panelShell} ${panel ? styles.panelShellOpen : ''}`.trim()}
          inert={!panel ? true : undefined}
          aria-hidden={!panel ? 'true' : undefined}
        >
          {displayPanel ? <div className={styles.panelContent}>{displayPanel}</div> : null}
        </div>
      </div>
    </div>
  );
}
