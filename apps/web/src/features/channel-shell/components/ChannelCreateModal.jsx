import { useEffect, useState } from "react";
import { ChannelType } from "../types";

const initialForm = {
  type: ChannelType.GENERAL,
  name: "",
  repoPath: "",
};

export default function ChannelCreateModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState(initialForm);

  useEffect(() => {
    if (open) {
      setForm(initialForm);
    }
  }, [open]);

  if (!open) return null;

  const isRepo = form.type === ChannelType.REPO;
  const canCreate = form.name.trim().length > 0 && (!isRepo || form.repoPath.trim().length > 0);

  const submit = (event) => {
    event.preventDefault();
    if (!canCreate) return;
    onCreate({
      type: form.type,
      name: form.name.trim(),
      repo_path: isRepo ? form.repoPath.trim() : null,
    });
  };

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <h3>Create Channel</h3>

        <form onSubmit={submit} className="channel-form">
          <div className="channel-form__field">
            <label>Type</label>
            <div className="channel-form__radio-row">
              <label>
                <input
                  type="radio"
                  checked={form.type === ChannelType.GENERAL}
                  onChange={() => setForm((prev) => ({ ...prev, type: ChannelType.GENERAL }))}
                />
                General
              </label>
              <label>
                <input
                  type="radio"
                  checked={form.type === ChannelType.REPO}
                  onChange={() => setForm((prev) => ({ ...prev, type: ChannelType.REPO }))}
                />
                Repo
              </label>
            </div>
          </div>

          <div className="channel-form__field">
            <label htmlFor="channel-name">Channel name</label>
            <input
              id="channel-name"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="e.g. frontend"
            />
          </div>

          {isRepo ? (
            <div className="channel-form__field">
              <label htmlFor="repo-path">Repo path</label>
              <input
                id="repo-path"
                value={form.repoPath}
                onChange={(event) => setForm((prev) => ({ ...prev, repoPath: event.target.value }))}
                placeholder="/Users/james/DevApps/the-duck-dome"
              />
            </div>
          ) : null}

          <div className="channel-form__actions">
            <button type="button" onClick={onClose} className="button button--ghost">
              Cancel
            </button>
            <button type="submit" disabled={!canCreate} className="button button--primary">
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
