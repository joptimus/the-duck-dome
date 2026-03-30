import { PlayIcon } from '../icons/Icons';
import styles from './SidebarFooter.module.css';

export function SidebarFooter({ userName, userInitial, onSessionLaunch }) {
  return (
    <div className={styles.footer}>
      <div className={styles.avatar}>{userInitial}</div>
      <span className={styles.userName}>{userName}</span>
      <button className={styles.sessionBtn} onClick={onSessionLaunch}>
        <PlayIcon size={10} color="#fff" />
      </button>
    </div>
  );
}
