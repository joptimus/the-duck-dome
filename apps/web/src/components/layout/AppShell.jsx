import { useState } from 'react';
import { ParticleField } from '../effects/ParticleField';
import { AmbientOrbs } from '../effects/AmbientOrbs';
import styles from './AppShell.module.css';

export function AppShell({ sidebar, children, panel }) {
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
        {panel && (
          <div className={styles.panel}>
            {panel}
          </div>
        )}
      </div>
    </div>
  );
}
