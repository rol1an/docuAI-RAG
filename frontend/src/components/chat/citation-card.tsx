"use client";

import { useState } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import type { Citation } from "@/types";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

// Noise texture as inline SVG data URI — subtle grain like uncoated paper
const NOISE_BG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.08'/%3E%3C/svg%3E")`;

// Morandi palette — warm, desaturated, paper-like
const MORANDI = {
  bg: "#ede8e1",
  bgDark: "#2a2522",
  border: "#cfc5b8",
  borderDark: "#3d3530",
  headerBg: "#e5dfd7",
  headerBgDark: "#312c28",
  filename: "#3e332a",
  filenameDark: "#d4cbc2",
  page: "#7a8fa6",
  pageDark: "#6a8099",
  score: "#8c7d70",
  scoreDark: "#7d6e63",
  scoreBar: "#b8a898",
  scoreBarDark: "#5c4f45",
  snippet: "#6b5f55",
  snippetDark: "#b0a59d",
  icon: "#9a8b7e",
  iconDark: "#7a6e66",
  divider: "#d5cdc5",
  dividerDark: "#3d3530",
};

export function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const scorePercent = Math.round(citation.score * 100);
  const shortName =
    citation.filename.length > 28
      ? citation.filename.slice(0, 25) + "…"
      : citation.filename;

  return (
    <div
      className="relative overflow-hidden rounded-xl transition-shadow hover:shadow-md dark:hover:shadow-black/30"
      style={{
        border: `1px solid ${MORANDI.border}`,
        backgroundImage: NOISE_BG,
        backgroundColor: MORANDI.bg,
        boxShadow: "0 1px 3px rgba(80,60,40,0.08)",
      }}
    >
      {/* Dark mode override via CSS variable trick — we layer a semi-transparent dark bg */}
      <div className="absolute inset-0 rounded-xl opacity-0 dark:opacity-100 pointer-events-none"
        style={{ backgroundColor: MORANDI.bgDark, border: `1px solid ${MORANDI.borderDark}` }}
      />

      {/* Header row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="relative z-10 flex w-full items-center gap-2 px-3 py-2.5 text-left"
        style={{ backgroundColor: "transparent" }}
      >
        {/* Index badge */}
        <span
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
          style={{
            backgroundColor: MORANDI.scoreBar,
            color: "#fff",
          }}
        >
          {index}
        </span>

        {/* File icon */}
        <FileText
          className="h-3.5 w-3.5 shrink-0"
          style={{ color: MORANDI.icon }}
        />

        {/* Filename */}
        <span
          className="flex-1 truncate text-xs font-medium dark:text-[#d4cbc2]"
          style={{ color: MORANDI.filename }}
          title={citation.filename}
        >
          {shortName}
        </span>

        {/* Page number */}
        {citation.page_number != null && (
          <span
            className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium dark:text-[#6a8099]"
            style={{
              color: MORANDI.page,
              backgroundColor: "rgba(122,143,166,0.12)",
            }}
          >
            p.{citation.page_number}
          </span>
        )}

        {/* Score */}
        <span
          className="shrink-0 text-[10px] tabular-nums dark:text-[#7d6e63]"
          style={{ color: MORANDI.score }}
        >
          {scorePercent}%
        </span>

        {/* Expand toggle */}
        {expanded ? (
          <ChevronUp className="h-3 w-3 shrink-0" style={{ color: MORANDI.score }} />
        ) : (
          <ChevronDown className="h-3 w-3 shrink-0" style={{ color: MORANDI.score }} />
        )}
      </button>

      {/* Thin score bar at bottom of header */}
      <div
        className="relative z-10 mx-3"
        style={{
          height: "2px",
          borderRadius: "1px",
          backgroundColor: "rgba(180,160,140,0.2)",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${scorePercent}%`,
            borderRadius: "1px",
            backgroundColor: MORANDI.scoreBar,
            transition: "width 0.6s ease",
          }}
        />
      </div>

      {/* Expandable snippet */}
      {expanded && (
        <>
          <div
            className="relative z-10 mx-3 my-2"
            style={{ height: "1px", backgroundColor: MORANDI.divider }}
          />
          <p
            className="relative z-10 px-3 pb-3 pt-1 text-[11px] leading-relaxed dark:text-[#b0a59d]"
            style={{ color: MORANDI.snippet }}
          >
            {citation.text_snippet}
          </p>
        </>
      )}
    </div>
  );
}

interface CitationListProps {
  citations: Citation[];
}

export function CitationList({ citations }: CitationListProps) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2 space-y-1.5">
      <p
        className="text-[10px] font-medium uppercase tracking-wider"
        style={{ color: MORANDI.score }}
      >
        Sources
      </p>
      <div className="grid gap-1.5 sm:grid-cols-1">
        {citations.map((c, i) => (
          <CitationCard key={`${c.doc_id}-${i}`} citation={c} index={i + 1} />
        ))}
      </div>
    </div>
  );
}
