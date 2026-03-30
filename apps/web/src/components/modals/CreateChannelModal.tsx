import { useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "./Modal";
import {
  BoltIcon,
  CheckIcon,
  ChevronIcon,
  CubeIcon,
  FolderIcon,
  GitIcon,
  HashIcon,
  MessageIcon,
  XIcon,
} from "../icons";
import styles from "./CreateChannelModal.module.css";

const CHANNEL_TYPES = {
  GENERAL: "general",
  REPO: "repo",
};

const TYPE_OPTIONS = [
  {
    value: CHANNEL_TYPES.GENERAL,
    label: "General",
    description: "Open conversation",
    accentClass: styles.typeGeneral,
    icon: MessageIcon,
  },
  {
    value: CHANNEL_TYPES.REPO,
    label: "Repo",
    description: "Tied to a codebase",
    accentClass: styles.typeRepo,
    icon: CubeIcon,
  },
];

function slugifyChannelName(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function compactPath(path) {
  if (!path) return "";
  const normalized = String(path).replace(/\\/g, "/");
  return normalized
    .replace(/^([A-Za-z]:)?\/Users\/[^/]+/i, "~")
    .replace(/^\/home\/[^/]+/i, "~");
}

export default function CreateChannelModal({ open, onClose, onCreate, repos = [] }) {
  const [type, setType] = useState(CHANNEL_TYPES.GENERAL);
  const [name, setName] = useState("");
  const [typeOpen, setTypeOpen] = useState(false);
  const [repoOpen, setRepoOpen] = useState(false);
  const [repoFilter, setRepoFilter] = useState("");
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const typeRef = useRef(null);
  const repoRef = useRef(null);
  const repoFilterRef = useRef(null);

  const selectedType = TYPE_OPTIONS.find((option) => option.value === type) || TYPE_OPTIONS[0];
  const isRepo = type === CHANNEL_TYPES.REPO;

  const filteredRepos = useMemo(() => {
    const query = repoFilter.trim().toLowerCase();
    if (!query) return repos;
    return repos.filter((repo) => {
      const haystack = `${repo.name || ""} ${repo.path || ""}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [repoFilter, repos]);

  const slugifiedName = useMemo(() => slugifyChannelName(name), [name]);
  const canCreate = slugifiedName.length > 0 && (!isRepo || !!selectedRepo);

  const resetState = () => {
    setType(CHANNEL_TYPES.GENERAL);
    setName("");
    setTypeOpen(false);
    setRepoOpen(false);
    setRepoFilter("");
    setSelectedRepo(null);
    setIsSubmitting(false);
  };

  useEffect(() => {
    if (!open) return;
    resetState();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event) => {
      if (typeRef.current && !typeRef.current.contains(event.target)) {
        setTypeOpen(false);
      }
      if (repoRef.current && !repoRef.current.contains(event.target)) {
        setRepoOpen(false);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (repoOpen && repoFilterRef.current) {
      repoFilterRef.current.focus();
    }
  }, [repoOpen]);

  const closeModal = () => {
    resetState();
    onClose();
  };

  const handleTypeSelect = (nextType) => {
    setType(nextType);
    setTypeOpen(false);
    if (nextType === CHANNEL_TYPES.GENERAL) {
      setSelectedRepo(null);
      setRepoOpen(false);
      setRepoFilter("");
    }
  };

  const handleRepoSelect = (repo) => {
    setSelectedRepo(repo);
    setRepoOpen(false);
    setRepoFilter("");
    if (!name.trim()) {
      setName(repo.name || "");
    }
  };

  const handleCreate = async () => {
    if (!canCreate || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onCreate({
        name: slugifiedName,
        type,
        repoPath: isRepo ? selectedRepo?.path || null : null,
        repo_path: isRepo ? selectedRepo?.path || null : null,
      });
      closeModal();
    } catch (error) {
      console.error("Failed to create channel:", error);
      setIsSubmitting(false);
    }
  };

  const TypeIcon = selectedType.icon;

  return (
    <Modal
      open={open}
      onClose={closeModal}
      showHeader={false}
      showTopBar={false}
      cardClassName={styles.modalCard}
      bodyClassName={styles.modalBody}
    >
      <div className={`${styles.modalRoot} ${isRepo ? styles.repo : styles.general}`}>
        <div className={styles.topAccent} />

        <div className={styles.header}>
          <div className={styles.headerTitleRow}>
            <HashIcon size={18} color="var(--accent)" />
            <h2 className={styles.title}>Create Channel</h2>
          </div>
          <button type="button" className={styles.closeButton} onClick={closeModal} aria-label="Close">
            <XIcon size={16} />
          </button>
        </div>

        <p className={styles.subtitle}>Channels organize conversations and agent work.</p>

        <div className={styles.content}>
          <div className={styles.field} ref={typeRef}>
            <label className={styles.label}>Type</label>
            <button
              type="button"
              className={`${styles.typeTrigger} ${typeOpen ? styles.open : ""}`}
              onClick={() => setTypeOpen((prev) => !prev)}
            >
              <span className={styles.optionMain}>
                <TypeIcon size={15} color="var(--accent)" />
                <span>
                  <span className={styles.optionLabel}>{selectedType.label}</span>
                  <span className={styles.optionDescription}>{selectedType.description}</span>
                </span>
              </span>
              <span className={`${styles.chevron} ${typeOpen ? styles.chevronOpen : ""}`}>
                <ChevronIcon size={11} />
              </span>
            </button>

            {typeOpen && (
              <div className={styles.typeMenu}>
                {TYPE_OPTIONS.map((option) => {
                  const OptionIcon = option.icon;
                  const isSelected = option.value === type;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      className={`${styles.typeOption} ${option.accentClass} ${isSelected ? styles.selected : ""}`}
                      onClick={() => handleTypeSelect(option.value)}
                    >
                      <span className={styles.optionMain}>
                        <OptionIcon size={15} color="var(--option-accent)" />
                        <span>
                          <span className={styles.optionLabel}>{option.label}</span>
                          <span className={styles.optionDescription}>{option.description}</span>
                        </span>
                      </span>
                      {isSelected && <CheckIcon size={13} color="var(--option-accent)" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {isRepo && (
            <div className={`${styles.field} ${styles.fadeUp}`} ref={repoRef}>
              <label className={styles.label}>Repository</label>
              <button
                type="button"
                className={`${styles.repoTrigger} ${repoOpen ? styles.open : ""} ${selectedRepo ? styles.hasValue : ""}`}
                onClick={() => setRepoOpen((prev) => !prev)}
              >
                <span className={styles.repoTriggerMain}>
                  {selectedRepo ? <CubeIcon size={14} color="var(--purple)" /> : <FolderIcon size={14} color="var(--text-muted)" />}
                  {selectedRepo ? (
                    <span className={styles.repoSelectedText}>
                      <span className={styles.repoName}>{selectedRepo.name}</span>
                      <span className={styles.repoPath}>{compactPath(selectedRepo.path)}</span>
                    </span>
                  ) : (
                    <span className={styles.repoPlaceholder}>Select a repository...</span>
                  )}
                </span>
                <span className={`${styles.chevron} ${repoOpen ? styles.chevronOpen : ""}`}>
                  <ChevronIcon size={11} />
                </span>
              </button>

              {repoOpen && (
                <div className={styles.repoMenu}>
                  <div className={styles.repoFilterRow}>
                    <HashIcon size={11} color="var(--text-muted)" />
                    <input
                      ref={repoFilterRef}
                      className={styles.repoFilterInput}
                      value={repoFilter}
                      onChange={(event) => setRepoFilter(event.target.value)}
                      placeholder="Filter repos..."
                    />
                  </div>

                  <div className={styles.repoList}>
                    {filteredRepos.length === 0 ? (
                      <div className={styles.emptyState}>No repos match "{repoFilter.trim()}"</div>
                    ) : (
                      filteredRepos.map((repo) => {
                        const isSelected = selectedRepo?.path === repo.path;
                        return (
                          <button
                            key={repo.path}
                            type="button"
                            className={`${styles.repoOption} ${isSelected ? styles.repoSelected : ""}`}
                            onClick={() => handleRepoSelect(repo)}
                          >
                            <span className={styles.repoOptionMain}>
                              <CubeIcon size={13} color="var(--purple)" />
                              <span className={styles.repoSelectedText}>
                                <span className={styles.repoOptionName}>{repo.name}</span>
                                <span className={styles.repoOptionPath}>{compactPath(repo.path)}</span>
                              </span>
                            </span>
                            {isSelected && <CheckIcon size={13} color="var(--purple)" />}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className={styles.field}>
            <label className={styles.label}>Channel Name</label>
            <div className={`${styles.nameInputWrap} ${name ? styles.nameHasValue : ""}`}>
              <span className={styles.hashPrefix}>#</span>
              <input
                className={styles.nameInput}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={isRepo ? "e.g. agentchattr" : "e.g. frontend"}
              />
            </div>
            {slugifiedName && (
              <div className={styles.preview}>
                Will be created as <span>#{slugifiedName}</span>
              </div>
            )}
          </div>

          {isRepo && selectedRepo && slugifiedName && (
            <div className={`${styles.summaryBar} ${styles.fadeUp}`}>
              <GitIcon size={16} color="var(--purple)" />
              <p>
                Agents in <span>#{slugifiedName}</span> will work inside <code>{selectedRepo.name}/</code>
              </p>
            </div>
          )}

          <div className={styles.actions}>
            <button type="button" className={styles.cancelButton} onClick={closeModal}>
              Cancel
            </button>
            <button
              type="button"
              className={`${styles.createButton} ${canCreate ? styles.createButtonEnabled : ""}`}
              onClick={handleCreate}
              disabled={!canCreate || isSubmitting}
            >
              <BoltIcon size={13} color={canCreate ? "#ffffff" : "var(--text-muted)"} glow={false} />
              <span>{isSubmitting ? "Creating..." : "Create Channel"}</span>
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
