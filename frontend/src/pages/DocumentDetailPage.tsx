import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  API_BASE_URL,
  type DocumentSummary,
  type PatientGraphResponse,
} from "../config";

type ViewMode = "json" | "graph";

function safePrettyJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function formatPropertyKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [document, setDocument] = useState<DocumentSummary | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [loadingDoc, setLoadingDoc] = useState(true);

  const [graph, setGraph] = useState<PatientGraphResponse | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);

  const [viewMode, setViewMode] = useState<ViewMode>("json");
  const [selectedNode, setSelectedNode] = useState<{
    id: string;
    label: string;
    properties: Record<string, unknown>;
  } | null>(null);

  useEffect(() => {
    if (!documentId) return;

    const load = async () => {
      setLoadingDoc(true);
      try {
        const resp = await fetch(`${API_BASE_URL}/documents/${documentId}`);
        if (!resp.ok) {
          const body = await resp.json().catch(() => null);
          const detail =
            (body && (body.detail as string | undefined)) ??
            `Failed to fetch document (${resp.status})`;
          throw new Error(detail);
        }
        const data = (await resp.json()) as DocumentSummary;
        setDocument(data);
        setDocError(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unexpected error loading document";
        setDocError(msg);
      } finally {
        setLoadingDoc(false);
      }
    };

    load();
  }, [documentId]);

  useEffect(() => {
    const shouldLoadGraph =
      documentId && document && document.status === "completed" && viewMode === "graph";
    if (!shouldLoadGraph) return;

    const loadGraph = async () => {
      setLoadingGraph(true);
      try {
        const resp = await fetch(`${API_BASE_URL}/documents/${documentId}/graph`);
        if (!resp.ok) {
          const body = await resp.json().catch(() => null);
          const detail =
            (body && (body.detail as string | undefined)) ??
            `Failed to fetch graph (${resp.status})`;
          throw new Error(detail);
        }
        const data = (await resp.json()) as PatientGraphResponse;
        setGraph(data);
        setGraphError(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unexpected error loading graph";
        setGraphError(msg);
      } finally {
        setLoadingGraph(false);
      }
    };

    loadGraph();
  }, [documentId, document, viewMode]);

  const patientNode = useMemo(
    () => graph?.nodes.find((n) => n.label === "Patient") ?? null,
    [graph]
  );

  const encounterNodes = useMemo(
    () => graph?.nodes.filter((n) => n.label === "Encounter") ?? [],
    [graph]
  );

  const claimNodes = useMemo(
    () => graph?.nodes.filter((n) => n.label === "Claim") ?? [],
    [graph]
  );

  const conditionNodes = useMemo(
    () => graph?.nodes.filter((n) => n.label === "Condition") ?? [],
    [graph]
  );

  const hospitalNodes = useMemo(
    () => graph?.nodes.filter((n) => n.label === "Hospital") ?? [],
    [graph]
  );

  return (
    <section className="page-layout">
      <div className="breadcrumbs">
        <Link className="breadcrumb-link" to="/">
          Dashboard
        </Link>
        <span>/</span>
        <span>Document</span>
      </div>
      <div className="two-column-detail">
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Document</div>
            <div className="panel-subtitle">
              {documentId ? `ID: ${documentId}` : "Loading…"}
            </div>
          </div>
          {loadingDoc && <div className="muted-text">Loading document…</div>}
          {docError && (
            <div className="muted-text" style={{ color: "#f97373" }}>
              {docError}
            </div>
          )}
          {document && (
            <div className="detail-card-grid">
              <div className="detail-card">
                <div className="detail-card-title">File</div>
                <div className="detail-row">
                  <span className="detail-label">Name</span>
                  <span className="detail-value" title={document.file_name}>
                    {document.file_name}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Pages</span>
                  <span className="detail-value">{document.page_count ?? "—"}</span>
                </div>
              </div>

              <div className="detail-card">
                <div className="detail-card-title">Status</div>
                <div className="detail-row">
                  <span className="detail-label">State</span>
                  <span className="detail-value">
                    <span className={`status-badge status-${document.status}`}>
                      {document.status}
                    </span>
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Created</span>
                  <span className="detail-value">{new Date(document.created_at).toLocaleString()}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Processed</span>
                  <span className="detail-value">
                    {document.processed_at
                      ? new Date(document.processed_at).toLocaleString()
                      : "—"}
                  </span>
                </div>
              </div>

              <div className="detail-card">
                <div className="detail-card-title">Patient</div>
                <div className="detail-row">
                  <span className="detail-label">ID</span>
                  <span className="detail-value">{document.patient_id}</span>
                </div>
                {document.structured_data?.patient?.name && (
                  <div className="detail-row">
                    <span className="detail-label">Name</span>
                    <span className="detail-value">{document.structured_data.patient.name}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Output</div>
            <div className="panel-subtitle">
              <div className="pill-tabs">
                <button
                  type="button"
                  className={`pill-tab ${
                    viewMode === "json" ? "pill-tab-active" : ""
                  }`}
                  onClick={() => setViewMode("json")}
                >
                  JSON
                </button>
                <button
                  type="button"
                  className={`pill-tab ${
                    viewMode === "graph" ? "pill-tab-active" : ""
                  }`}
                  onClick={() => setViewMode("graph")}
                  disabled={!document || document.status !== "completed"}
                >
                  Graph
                </button>
              </div>
            </div>
          </div>

          {viewMode === "json" && (
            <div>
              {!document && !loadingDoc && (
                <div className="muted-text">No document loaded.</div>
              )}
              {document && !document.structured_data && (
                <div className="muted-text">
                  Structured data is not yet available for this document.
                </div>
              )}
              {document?.structured_data && (
                <div className="json-viewer">
                  <pre>{safePrettyJson(document.structured_data)}</pre>
                </div>
              )}
            </div>
          )}

          {viewMode === "graph" && (
            <div>
              {loadingGraph && <div className="muted-text">Loading graph…</div>}
              {graphError && (
                <div className="muted-text" style={{ color: "#f97373" }}>
                  {graphError}
                </div>
              )}
              {graph && !loadingGraph && !graphError && graph.nodes.length === 0 && (
                <div className="muted-text">
                  No graph data returned for this patient. Once Neo4j ingestion runs for this
                  document, relationships will appear here.
                </div>
              )}
              {graph && !loadingGraph && !graphError && graph.nodes.length > 0 && (
                <div className="graph-shell">
                  <svg className="graph-svg">
                    <defs>
                      <marker
                        id="arrowhead"
                        markerWidth="8"
                        markerHeight="6"
                        refX="8"
                        refY="3"
                        orient="auto"
                      >
                        <polygon points="0 0, 8 3, 0 6" fill="rgba(148,163,184,0.9)" />
                      </marker>
                    </defs>
                    {/* Very simple layered layout: Patient at left, others to the right */}
                    {(() => {
                      const centerY = 160;
                      const layerX = {
                        patient: 80,
                        encounter: 260,
                        claim: 440,
                        condition: 260,
                        hospital: 440,
                      };

                      type PositionedNode = {
                        id: string;
                        label: string;
                        x: number;
                        y: number;
                        caption: string;
                        properties?: Record<string, unknown>;
                      };

                      const positioned: PositionedNode[] = [];

                      if (patientNode) {
                        positioned.push({
                          id: patientNode.id,
                          label: "Patient",
                          x: layerX.patient,
                          y: centerY,
                          caption:
                            (patientNode.properties.name as string | undefined) ??
                            patientNode.id,
                          properties: patientNode.properties,
                        });
                      }

                      encounterNodes.forEach((n, idx) => {
                        positioned.push({
                          id: n.id,
                          label: "Encounter",
                          x: layerX.encounter,
                          y: centerY + (idx - (encounterNodes.length - 1) / 2) * 70,
                          caption:
                            (n.properties.department as string | undefined) ??
                            n.id,
                          properties: n.properties,
                        });
                      });

                      claimNodes.forEach((n, idx) => {
                        positioned.push({
                          id: n.id,
                          label: "Claim",
                          x: layerX.claim,
                          y: centerY + (idx - (claimNodes.length - 1) / 2) * 70,
                          caption:
                            (n.properties.status as string | undefined) ??
                            n.id,
                          properties: n.properties,
                        });
                      });

                      conditionNodes.forEach((n, idx) => {
                        positioned.push({
                          id: n.id,
                          label: "Condition",
                          x: layerX.condition,
                          y: centerY + 120 + idx * 50,
                          caption: n.id,
                          properties: n.properties,
                        });
                      });

                      hospitalNodes.forEach((n, idx) => {
                        positioned.push({
                          id: n.id,
                          label: "Hospital",
                          x: layerX.hospital,
                          y: centerY - 120 - idx * 50,
                          caption:
                            (n.properties.city as string | undefined) ?? n.id,
                          properties: n.properties,
                        });
                      });

                      const byId = new Map<string, PositionedNode>();
                      positioned.forEach((p) => byId.set(p.id, p));

                      return (
                        <>
                          {graph.relationships.map((rel) => {
                            const source = byId.get(rel.source);
                            const target = byId.get(rel.target);
                            if (!source || !target) return null;
                            return (
                              <line
                                key={`${rel.source}-${rel.target}-${rel.type}`}
                                x1={source.x}
                                y1={source.y}
                                x2={target.x}
                                y2={target.y}
                                className="graph-edge"
                              />
                            );
                          })}

                          {positioned.map((node) => {
                            const colorByLabel: Record<string, string> = {
                              Patient: "#f97373",
                              Encounter: "#a855f7",
                              Claim: "#fb923c",
                              Condition: "#22d3ee",
                              Hospital: "#facc15",
                            };
                            const fill = colorByLabel[node.label] ?? "#22d3ee";
                            return (
                              <g
                                key={node.id}
                                className="graph-node-clickable"
                                onClick={() =>
                                  setSelectedNode({
                                    id: node.id,
                                    label: node.label,
                                    properties: (node.properties ??
                                      {}) as Record<string, unknown>,
                                  })
                                }
                              >
                                <circle
                                  cx={node.x}
                                  cy={node.y}
                                  r={18}
                                  className="graph-node-circle"
                                  style={{ fill }}
                                />
                                <text
                                  x={node.x}
                                  y={node.y - 22}
                                  textAnchor="middle"
                                  className="graph-node-label"
                                >
                                  {node.label}
                                </text>
                              </g>
                            );
                          })}
                        </>
                      );
                    })()}
                  </svg>
                  {selectedNode && (
                    <div className="graph-overlay">
                      <div className="graph-overlay-card">
                        <div className="graph-overlay-header">
                          <div className="graph-overlay-title">
                            {selectedNode.label}
                          </div>
                          <button
                            type="button"
                            className="graph-overlay-close"
                            onClick={() => setSelectedNode(null)}
                          >
                            ✕
                          </button>
                        </div>
                        <div className="graph-overlay-body">
                          {Object.entries(selectedNode.properties).filter(
                            ([key, value]) =>
                              key !== "created_at" &&
                              key !== "updated_at" &&
                              value !== null &&
                              value !== undefined &&
                              value !== ""
                          ).length === 0 && (
                            <div className="muted-text">
                              No properties available for this node.
                            </div>
                          )}
                          {Object.entries(selectedNode.properties)
                            .filter(
                              ([key, value]) =>
                                key !== "created_at" &&
                                key !== "updated_at" &&
                                value !== null &&
                                value !== undefined &&
                                value !== ""
                            )
                            .map(([key, value]) => (
                              <div
                                className="graph-overlay-row"
                                key={key}
                              >
                                <span className="graph-overlay-key">
                                  {formatPropertyKey(key)}
                                </span>
                                <span className="graph-overlay-value">
                                  {typeof value === "string" ||
                                  typeof value === "number" ||
                                  typeof value === "boolean"
                                    ? String(value)
                                    : JSON.stringify(value)}
                                </span>
                              </div>
                            ))}
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="muted-text" style={{ marginTop: 6 }}>
                    Layout is schematic: patient at left, encounters and conditions in the
                    middle, claims and hospital on the right.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

