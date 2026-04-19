"use client";

import { FileText, Quote, MapPin } from "lucide-react";
import type { AnswerStructured, Citation } from "@/types";

// Reuse same Morandi palette as citation-card
const MORANDI = {
  bg: "#ede8e1",
  bgDark: "#2a2522",
  border: "#cfc5b8",
  borderDark: "#3d3530",
  sectionBg: "#e5dfd7",
  sectionBgDark: "#312c28",
  heading: "#3e332a",
  headingDark: "#d4cbc2",
  text: "#5a4f47",
  textDark: "#b8afa8",
  quote: "#6b5f55",
  quoteDark: "#a89e96",
  accent: "#7a8fa6",
  accentDark: "#6a8099",
  divider: "#d5cdc5",
  dividerDark: "#3d3530",
  badge: "#b8a898",
};

const NOISE_BG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.08'/%3E%3C/svg%3E")`;

interface TriadCardProps {
  structured: AnswerStructured;
  citations?: Citation[];
}

export function TriadCard({ structured, citations = [] }: TriadCardProps) {
  if (!structured.parse_success) return null;

  return (
    <div
      className="relative mt-3 overflow-hidden rounded-2xl"
      style={{
        border: `1px solid ${MORANDI.border}`,
        backgroundImage: NOISE_BG,
        backgroundColor: MORANDI.bg,
        boxShadow: "0 2px 8px rgba(80,60,40,0.10)",
      }}
    >
      {/* Dark mode overlay */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 dark:opacity-100 pointer-events-none"
        style={{ backgroundColor: MORANDI.bgDark, border: `1px solid ${MORANDI.borderDark}` }}
      />

      {/* ── 证据区 ───────────────────────────────────────── */}
      {structured.evidence.length > 0 && (
        <div
          className="relative z-10"
          style={{ borderTop: `1px solid ${MORANDI.divider}` }}
        >
          <div
            className="flex items-center gap-2 px-4 py-2.5"
            style={{ backgroundColor: "rgba(180,160,140,0.08)", borderBottom: `1px solid ${MORANDI.divider}` }}
          >
            <Quote
              className="h-3.5 w-3.5"
              style={{ color: MORANDI.accent }}
            />
            <span
              className="text-xs font-semibold uppercase tracking-widest dark:text-[#d4cbc2]"
              style={{ color: MORANDI.heading }}
            >
              证据
            </span>
          </div>

          <div className="space-y-2 px-4 py-3">
            {structured.evidence.map((ev, i) => {
              const citation = citations[ev.citation_index];
              return (
                <div key={i} className="flex gap-2.5">
                  {/* Left accent bar */}
                  <div
                    className="mt-1 w-0.5 shrink-0 self-stretch rounded-full"
                    style={{ backgroundColor: MORANDI.badge }}
                  />
                  <div className="flex-1 space-y-1">
                    <p
                      className="text-[12px] italic leading-relaxed dark:text-[#a89e96]"
                      style={{ color: MORANDI.quote }}
                    >
                      &ldquo;{ev.quote}&rdquo;
                    </p>
                    {citation && (
                      <p
                        className="text-[10px] dark:text-[#6a8099]"
                        style={{ color: MORANDI.accent }}
                      >
                        [{ev.citation_index + 1}] {citation.filename}
                        {citation.page_number != null && `, p.${citation.page_number}`}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 来源区 ───────────────────────────────────────── */}
      {citations.length > 0 && (
        <div
          className="relative z-10"
          style={{ borderTop: `1px solid ${MORANDI.divider}` }}
        >
          <div
            className="flex items-center gap-2 px-4 py-2"
            style={{ backgroundColor: "rgba(180,160,140,0.06)" }}
          >
            <MapPin
              className="h-3 w-3"
              style={{ color: MORANDI.accent }}
            />
            <span
              className="text-[10px] font-semibold uppercase tracking-widest dark:text-[#d4cbc2]"
              style={{ color: MORANDI.heading }}
            >
              来源
            </span>
          </div>

          <div className="flex flex-wrap gap-2 px-4 pb-3 pt-1">
            {citations.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1"
                style={{
                  backgroundColor: "rgba(122,143,166,0.10)",
                  border: `1px solid ${MORANDI.border}`,
                }}
              >
                <FileText
                  className="h-2.5 w-2.5 shrink-0"
                  style={{ color: MORANDI.accent }}
                />
                <span
                  className="text-[10px] font-medium dark:text-[#6a8099]"
                  style={{ color: MORANDI.accent }}
                >
                  [{i + 1}]
                </span>
                <span
                  className="max-w-[120px] truncate text-[10px] dark:text-[#b8afa8]"
                  style={{ color: MORANDI.quote }}
                  title={c.filename}
                >
                  {c.filename}
                </span>
                {c.page_number != null && (
                  <span
                    className="shrink-0 text-[10px] dark:text-[#6a8099]"
                    style={{ color: MORANDI.accent }}
                  >
                    p.{c.page_number}
                  </span>
                )}
                <span
                  className="shrink-0 text-[10px] tabular-nums dark:text-[#7d6e63]"
                  style={{ color: MORANDI.badge }}
                >
                  {Math.round(c.score * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
