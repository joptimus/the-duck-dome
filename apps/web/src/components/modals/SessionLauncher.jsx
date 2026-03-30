import { useState } from 'react';
import { Modal } from './Modal';
import styles from './SessionLauncher.module.css';

const SESSION_TYPES = [
  {
    name: 'Code Review',
    desc: 'Structured review with builder, reviewer, and red team roles.',
    roles: ['builder', 'reviewer', 'red_team', 'synthesiser'],
  },
  {
    name: 'Debate',
    desc: 'Explore a topic from multiple perspectives.',
    roles: ['proposer', 'for', 'against', 'moderator'],
  },
  {
    name: 'Design Critique',
    desc: 'Present and critique a design decision.',
    roles: ['presenter', 'critic', 'synthesiser'],
  },
  {
    name: 'Planning',
    desc: 'Plan a feature or project with structured roles.',
    roles: ['planner', 'challenger', 'synthesiser'],
  },
];

export function SessionLauncher({ open, onClose }) {
  const [selected, setSelected] = useState(null);
  const [goal, setGoal] = useState('');

  return (
    <Modal open={open} onClose={onClose} title={<>⚡ Start a Session</>}>
      <input
        className={styles.goalInput}
        placeholder="What's the goal of this session?"
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
      />

      <div className={styles.sectionTitle}>Session Types</div>
      <div className={styles.grid}>
        {SESSION_TYPES.map((type) => (
          <div
            key={type.name}
            className={`${styles.card} ${selected === type.name ? styles.cardSelected : ''}`}
            onClick={() => setSelected(type.name)}
          >
            <div className={styles.cardName}>{type.name}</div>
            <div className={styles.cardDesc}>{type.desc}</div>
            <div className={styles.roles}>
              {type.roles.map((r) => (
                <span key={r} className={styles.role}>{r}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.customSection}>
        <div className={styles.customTitle}>+ Design a session</div>
        <input
          className={styles.customInput}
          placeholder="Describe a custom session for an agent to draft..."
        />
      </div>
    </Modal>
  );
}
