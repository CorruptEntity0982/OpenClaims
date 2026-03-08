import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL, type DocumentSummary, type DocumentStatus } from "../config";

interface UploadState {
  patientId: string;
  file: File | null;
  isSubmitting: boolean;
  error: string | null;
}

const POLL_INTERVAL_MS = 5000;

function statusClass(status: DocumentStatus): string {
  switch (status) {
    case "uploaded":
      return "status-badge status-uploaded";
    case "processing":
      return "status-badge status-processing";
    case "completed":
      return "status-badge status-completed";
    case "failed":
      return "status-badge status-failed";
    default:
      return "status-badge status-uploaded";
  }
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString();
  } catch {
    return value;
  }
}

export default function DashboardPage() {
  const [uploadState, setUploadState] = useState<UploadState>({
    patientId: "",
    file: null,
    isSubmitting: false,
    error: null,
  });
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [polling, setPolling] = useState(true);
  const navigate = useNavigate();

  const hasActiveProcessing = useMemo(
    () => documents.some((d) => d.status === "processing" || d.status === "uploaded"),
    [documents]
  );

  useEffect(() => {
    let timer: number | undefined;

    const loadDocuments = async () => {
      setIsLoadingDocs(true);
      try {
        const resp = await fetch(`${API_BASE_URL}/documents?limit=100&offset=0`, {
          headers: { Accept: "application/json" },
        });
        if (!resp.ok) {
          // eslint-disable-next-line no-console
          console.error("Failed to fetch documents", resp.status);
          return;
        }
        const data = (await resp.json()) as DocumentSummary[];
        setDocuments(data);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("Error fetching documents", err);
      } finally {
        setIsLoadingDocs(false);
      }
    };

    loadDocuments();

    if (polling) {
      timer = window.setInterval(loadDocuments, POLL_INTERVAL_MS);
    }

    return () => {
      if (timer) {
        window.clearInterval(timer);
      }
    };
  }, [polling]);

  const handleUploadSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!uploadState.patientId || !uploadState.file) {
      setUploadState((prev) => ({
        ...prev,
        error: "Patient ID and PDF file are required.",
      }));
      return;
    }

    const formData = new FormData();
    formData.append("patient_id", uploadState.patientId);
    formData.append("file", uploadState.file);

    setUploadState((prev) => ({ ...prev, isSubmitting: true, error: null }));

    try {
      const resp = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const errBody = await resp.json().catch(() => null);
        const detail =
          (errBody && (errBody.detail as string | undefined)) ??
          `Upload failed with status ${resp.status}`;
        throw new Error(detail);
      }

      const created = (await resp.json()) as DocumentSummary;
      setDocuments((prev) => [created, ...prev]);
      setUploadState({
        patientId: uploadState.patientId,
        file: null,
        isSubmitting: false,
        error: null,
      });
      setPolling(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error during upload";
      setUploadState((prev) => ({ ...prev, isSubmitting: false, error: message }));
    }
  };

  return (
    <section className="page-layout">
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Upload document</div>
          <div className="panel-subtitle">
            Start the extraction pipeline on a new clinical PDF
          </div>
        </div>
        <form className="upload-form" onSubmit={handleUploadSubmit}>
          <div>
            <div className="field-label">Patient ID</div>
            <input
              className="text-input"
              placeholder="Paste an existing patient UUID (from /patients)"
              value={uploadState.patientId}
              onChange={(e) =>
                setUploadState((prev) => ({ ...prev, patientId: e.target.value }))
              }
            />
          </div>
          <div className="field-row">
            <div>
              <div className="field-label">PDF file</div>
              <input
                type="file"
                accept="application/pdf"
                className="file-input"
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  setUploadState((prev) => ({ ...prev, file }));
                }}
              />
            </div>
            <div style={{ alignSelf: "flex-end" }}>
              <button
                type="submit"
                className="primary-button"
                disabled={uploadState.isSubmitting}
              >
                {uploadState.isSubmitting ? "Uploading…" : "Upload & process"}
              </button>
              <div className="muted-text">Files are validated and processed asynchronously.</div>
            </div>
          </div>
          {uploadState.error && (
            <div className="muted-text" style={{ color: "#f97373" }}>
              {uploadState.error}
            </div>
          )}
        </form>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Documents</div>
          <div className="panel-subtitle">
            Polling{" "}
            <button
              type="button"
              className="pill-button"
              onClick={() => setPolling((p) => !p)}
            >
              {polling ? "Pause" : "Resume"}
            </button>
          </div>
        </div>
        <div className="table-shell">
          <div className="table-header">
            <span>Document</span>
            <span>Patient</span>
            <span>Created</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {isLoadingDocs && documents.length === 0 && (
            <div className="table-row">
              <span className="muted-text">Loading documents…</span>
            </div>
          )}
          {documents.map((doc) => {
            const canView = doc.status === "completed";
            return (
              <div
                key={doc.id}
                className={`table-row ${
                  doc.status === "processing" || doc.status === "uploaded" ? "row-faded" : ""
                }`}
              >
                <span className="file-name-cell" title={doc.file_name}>
                  {doc.file_name}
                </span>
                <span className="muted-text">{doc.patient_id}</span>
                <span className="muted-text">{formatDate(doc.created_at)}</span>
                <span>
                  <span className={statusClass(doc.status)}>{doc.status}</span>
                </span>
                <span>
                  <button
                    type="button"
                    className="pill-button"
                    disabled={!canView}
                    onClick={() => navigate(`/documents/${doc.id}`)}
                  >
                    View results
                  </button>
                </span>
              </div>
            );
          })}
          {!isLoadingDocs && documents.length === 0 && (
            <div className="table-row">
              <span className="muted-text">No documents yet. Upload a PDF to get started.</span>
            </div>
          )}
        </div>
        {hasActiveProcessing && (
          <div className="muted-text" style={{ marginTop: 6 }}>
            We&apos;ll refresh the table every {POLL_INTERVAL_MS / 1000} seconds while tasks are
            processing.
          </div>
        )}
      </div>
    </section>
  );
}

