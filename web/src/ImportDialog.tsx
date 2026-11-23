import { useState } from "react";
import { Upload, X } from "lucide-react";
import Modal from "./Modal";
import { MAX_IMPORT_BYTES, parseImport } from "./imports";
import type { ImportedData } from "./imports";
import type { Scenario } from "./types";

export default function ImportDialog({
  defaults,
  onImport,
  onClose,
}: {
  defaults: Scenario;
  onImport: (data: ImportedData) => void;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const readFile = async (file?: File) => {
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) {
      setError("Import must be no larger than 1 MB.");
      return;
    }
    try {
      setText(await file.text());
      setName(file.name);
      setError("");
    } catch {
      setError("Could not read this file. Try pasting its JSON.");
    }
  };
  const submit = () => {
    try {
      const data = parseImport(text, defaults);
      onImport(data);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid import.");
    }
  };
  return (
    <Modal onClose={onClose} labelledBy="import-title">
      <div className="drawer-heading">
        <div>
          <span className="eyebrow">BRING YOUR OWN INPUTS</span>
          <h2 id="import-title">Import scenario or evidence</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Close import"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <p className="drawer-description">
        Load a JSON scenario, partial scenario inputs, or a full QubitYield
        evidence export. Maximum 1 MB. Imported evidence is labeled as supplied
        data, not independently verified.
      </p>
      <label className="file-drop">
        <Upload size={22} />
        <span>{name || "Choose a JSON file"}</span>
        <input
          type="file"
          accept=".json,application/json"
          onChange={(event) => void readFile(event.target.files?.[0])}
        />
      </label>
      <label className="workbench-field">
        <span>Or paste JSON</span>
        <textarea
          data-autofocus
          value={text}
          maxLength={MAX_IMPORT_BYTES}
          onChange={(event) => {
            setText(event.target.value);
            setError("");
          }}
          rows={9}
          placeholder={'{ "value_mode": "fixed_output_savings" }'}
        />
      </label>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <div className="modal-actions">
        <button className="outlined-button" onClick={onClose}>
          Cancel
        </button>
        <button
          className="primary-button"
          onClick={submit}
          disabled={!text.trim()}
        >
          Validate and import
        </button>
      </div>
    </Modal>
  );
}
