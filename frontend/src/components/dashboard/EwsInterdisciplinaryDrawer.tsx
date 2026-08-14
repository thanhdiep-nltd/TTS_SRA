"use client";

import React, { useMemo } from "react";
import {
  X,
  User,
  Sparkles,
  AlertTriangle,
  Award,
  TrendingDown,
  TrendingUp,
  Activity,
  Layers,
  Info,
  ShieldAlert,
} from "lucide-react";

export interface PillarData {
  pillar_id: string;
  pillar_name: string;
  weight: number;
  risk_score: number;
  risk_level: string;
  is_active: boolean;
  enrolled_subjects: Array<{
    subject_id: number;
    subject_code: string;
    subject_name: string;
    risk_score: number;
    risk_level: string;
    last_score?: number | null;
    score_slope?: number | null;
    has_llm?: boolean;
  }>;
}

export interface StudentInterdisciplinaryDetail {
  student_code: string;
  student_name: string;
  class_name: string;
  grade_id?: number | null;
  cluster_code: string;
  cluster_name: string;
  cluster_risk_score: number;
  cluster_risk_level: string;
  bottleneck_subject?: string | null;
  bottleneck_risk?: number | null;
  anchor_subject?: string | null;
  anchor_risk?: number | null;
  disparity_index: number;
  has_llm: boolean;
  pillars: PillarData[];
}

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MODERATE: "#eab308",
  LOW: "#22c55e",
};

export default function EwsInterdisciplinaryDrawer({
  item,
  onClose,
  week,
}: {
  item: StudentInterdisciplinaryDetail | null;
  onClose: () => void;
  week: number;
}) {
  if (!item) return null;

  const riskColor = RISK_COLORS[item.cluster_risk_level] || "#94a3b8";
  const activePillars = useMemo(
    () => item.pillars.filter((p) => p.is_active),
    [item.pillars]
  );

  // Tính toán tọa độ Radar SVG theo số đỉnh thực học (N >= 3)
  const radarSvgData = useMemo(() => {
    const N = activePillars.length;
    if (N < 3) return null;

    const size = 300;
    const center = size / 2;
    const radius = 105;

    // Các điểm đỉnh của polygon dữ liệu học sinh
    const dataPoints = activePillars.map((p, i) => {
      const angle = (Math.PI * 2 * i) / N - Math.PI / 2;
      const r = (Math.min(100, Math.max(0, p.risk_score)) / 100) * radius;
      return {
        x: center + r * Math.cos(angle),
        y: center + r * Math.sin(angle),
        pillar: p,
      };
    });

    const polygonPointsStr = dataPoints.map((pt) => `${pt.x},${pt.y}`).join(" ");

    // Các vòng lưới đồng tâm (20%, 40%, 60%, 80%, 100%)
    const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];
    const gridPolygons = gridLevels.map((lvl) => {
      const pts = activePillars.map((_, i) => {
        const angle = (Math.PI * 2 * i) / N - Math.PI / 2;
        const r = lvl * radius;
        return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
      });
      return { level: lvl, pointsStr: pts.join(" ") };
    });

    // Các trục hướng tâm
    const radialAxes = activePillars.map((p, i) => {
      const angle = (Math.PI * 2 * i) / N - Math.PI / 2;
      const xEnd = center + radius * Math.cos(angle);
      const yEnd = center + radius * Math.sin(angle);
      // Tọa độ nhãn bên ngoài
      const xLabel = center + (radius + 24) * Math.cos(angle);
      const yLabel = center + (radius + 20) * Math.sin(angle);
      return { x1: center, y1: center, x2: xEnd, y2: yEnd, xLabel, yLabel, pillar: p };
    });

    return { size, center, gridPolygons, radialAxes, dataPoints, polygonPointsStr };
  }, [activePillars]);

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="absolute inset-0" onClick={onClose} />

      {/* DRAWER CONTAINER */}
      <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
        {/* HEADER */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-100 dark:border-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 shadow-2xs">
              <User className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                  {item.student_name || item.student_code}
                </h3>
                <span className="px-2 py-0.5 text-xs font-mono font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-700/80">
                  {item.student_code}
                </span>
                {item.has_llm && (
                  <span title="Đã có phân tích rủi ro chuyên sâu từ AI">
                    <Sparkles className="w-4 h-4 text-amber-500 fill-amber-400/30" />
                  </span>
                )}

                {/* 2-Tone Risk Badge Cụm Liên Môn */}
                <div
                  className="inline-flex items-stretch rounded-full border overflow-hidden shadow-xs text-[11px] font-semibold ml-1"
                  style={{ borderColor: `${riskColor}50` }}
                >
                  <span
                    className="px-2.5 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5 leading-normal"
                    style={{ backgroundColor: riskColor }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                    {item.cluster_risk_level}
                  </span>
                  <span
                    className="px-2.5 py-0.5 font-mono font-bold text-xs flex items-center justify-center leading-normal"
                    style={{
                      backgroundColor: `${riskColor}18`,
                      color: riskColor,
                    }}
                  >
                    {item.cluster_risk_score.toFixed(2)}
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 pt-0.5">
                <span>
                  Lớp:{" "}
                  <strong className="text-slate-800 dark:text-slate-200">
                    {item.class_name
                      ? item.class_name.replace(/\s*-\s*Trường\s*\d+/gi, "").replace(/^Lớp\s+/i, "")
                      : "—"}
                  </strong>
                </span>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span>
                  Cụm: <strong className="text-indigo-600 dark:text-indigo-400">{item.cluster_name}</strong>
                </span>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span className="text-slate-400 font-medium">Mốc Tuần {week}</span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* BODY SCROLLABLE */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* CẢNH BÁO MÔN NÚT THẮT & MÔN TRỤ CỘT */}
          {(item.bottleneck_subject || item.anchor_subject) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {item.bottleneck_subject && (
                <div className="p-4 rounded-2xl bg-rose-50/80 dark:bg-rose-950/30 border border-rose-200/80 dark:border-rose-900/40 flex items-start gap-3">
                  <div className="p-2 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 shrink-0">
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[11px] font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
                      Nút Thắt Kéo Tụt (Bottleneck)
                    </span>
                    <h5 className="font-bold text-sm text-slate-900 dark:text-white mt-0.5">
                      {item.bottleneck_subject} ({item.bottleneck_risk?.toFixed(2)}/100)
                    </h5>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                      Môn học này có điểm rủi ro vượt trội và đang kéo tụt toàn bộ tiến trình cụm liên môn. Cần ưu tiên can thiệp phụ đạo sớm.
                    </p>
                  </div>
                </div>
              )}

              {item.anchor_subject && (
                <div className="p-4 rounded-2xl bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-900/40 flex items-start gap-3">
                  <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                      Môn Trụ Cột Nâng Đỡ (Anchor)
                    </span>
                    <h5 className="font-bold text-sm text-slate-900 dark:text-white mt-0.5">
                      {item.anchor_subject} ({item.anchor_risk?.toFixed(2)}/100)
                    </h5>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                      Học sinh duy trì kết quả rất vững ở môn này, có thể dùng làm đòn bẩy tâm lý để kích thích các môn liên quan.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* RADAR CHART NGŨ GIÁC NĂNG LỰC RỦI RO LIÊN MÔN */}
          <div className="p-5 rounded-2xl bg-slate-50/60 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                  Biểu Đồ Radar Cân Bằng Rủi Ro ({activePillars.length} Trụ Cột Thực Học)
                </h4>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                Độ lệch pha: <strong className="text-slate-700 dark:text-slate-300">{item.disparity_index.toFixed(2)}</strong>
              </span>
            </div>

            {radarSvgData ? (
              <div className="flex justify-center py-2">
                <svg
                  width={radarSvgData.size}
                  height={radarSvgData.size}
                  className="overflow-visible"
                >
                  {/* Lưới đa giác đồng tâm */}
                  {radarSvgData.gridPolygons.map((g, idx) => (
                    <polygon
                      key={idx}
                      points={g.pointsStr}
                      fill="none"
                      stroke="currentColor"
                      className="text-slate-200 dark:text-slate-700"
                      strokeWidth={idx === radarSvgData.gridPolygons.length - 1 ? "1.5" : "1"}
                      strokeDasharray={idx === radarSvgData.gridPolygons.length - 1 ? "none" : "3,3"}
                    />
                  ))}

                  {/* Trục hướng tâm */}
                  {radarSvgData.radialAxes.map((ax, idx) => (
                    <g key={idx}>
                      <line
                        x1={ax.x1}
                        y1={ax.y1}
                        x2={ax.x2}
                        y2={ax.y2}
                        stroke="currentColor"
                        className="text-slate-200 dark:text-slate-700"
                        strokeWidth="1"
                      />
                      {/* Nhãn trụ cột */}
                      <text
                        x={ax.xLabel}
                        y={ax.yLabel}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="text-[10px] font-bold fill-slate-700 dark:fill-slate-300"
                      >
                        {ax.pillar.pillar_name}
                      </text>
                    </g>
                  ))}

                  {/* Vùng polygon dữ liệu học sinh */}
                  <polygon
                    points={radarSvgData.polygonPointsStr}
                    fill={riskColor}
                    fillOpacity="0.25"
                    stroke={riskColor}
                    strokeWidth="2.5"
                    className="transition-all duration-300"
                  />

                  {/* Điểm nút tròn trên các đỉnh */}
                  {radarSvgData.dataPoints.map((pt, idx) => (
                    <g key={idx}>
                      <circle
                        cx={pt.x}
                        cy={pt.y}
                        r="4.5"
                        fill={riskColor}
                        stroke="#ffffff"
                        strokeWidth="2"
                        className="shadow-md"
                      />
                      <text
                        x={pt.x}
                        y={pt.y - 8}
                        textAnchor="middle"
                        className="text-[9px] font-mono font-bold fill-slate-900 dark:fill-white"
                      >
                        {pt.pillar.risk_score.toFixed(2)}
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-400">
                Cần tối thiểu 3 môn thực học để vẽ biểu đồ Radar.
              </div>
            )}
          </div>

          {/* DANH SÁCH CHI TIẾT CÁC MÔN THÀNH PHẦN */}
          <div className="space-y-3">
            <h4 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              Chi Tiết Từng Trụ Cột Môn Học ({item.pillars.length} Trụ Cột)
            </h4>

            <div className="space-y-2.5">
              {item.pillars.map((p) => {
                const pColor = RISK_COLORS[p.risk_level] || "#94a3b8";
                const isBottleneck = item.bottleneck_subject === p.pillar_name;
                const isAnchor = item.anchor_subject === p.pillar_name;

                return (
                  <div
                    key={p.pillar_id}
                    className={`p-4 rounded-2xl border transition-all ${
                      !p.is_active
                        ? "bg-slate-50/40 dark:bg-slate-900/40 border-slate-100 dark:border-slate-800/60 opacity-60"
                        : isBottleneck
                        ? "bg-rose-50/30 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/50 shadow-2xs"
                        : isAnchor
                        ? "bg-emerald-50/30 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/50 shadow-2xs"
                        : "bg-white dark:bg-slate-900 border-slate-200/80 dark:border-slate-800 shadow-2xs"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900 dark:text-white">
                          {p.pillar_name}
                        </span>
                        {p.is_active ? (
                          <span className="text-[11px] font-mono text-slate-400">
                            (Trọng số: {(p.weight * 100).toFixed(0)}%)
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400">
                            Không đăng ký học
                          </span>
                        )}
                        {isBottleneck && (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-500 text-white animate-pulse">
                            Nút thắt cổ chai
                          </span>
                        )}
                        {isAnchor && (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-600 text-white">
                            Trụ cột nâng đỡ
                          </span>
                        )}
                      </div>

                      {p.is_active && (
                        <div
                          className="inline-flex items-stretch rounded-full border overflow-hidden text-[10px] font-semibold"
                          style={{ borderColor: `${pColor}50` }}
                        >
                          <span
                            className="px-2 py-0.5 text-white uppercase"
                            style={{ backgroundColor: pColor }}
                          >
                            {p.risk_level}
                          </span>
                          <span
                            className="px-2 py-0.5 font-mono font-bold"
                            style={{ backgroundColor: `${pColor}15`, color: pColor }}
                          >
                            {p.risk_score.toFixed(2)}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Danh sách các phân môn thực tế (nếu học nhiều môn như 2 môn Toán) */}
                    {p.is_active && p.enrolled_subjects.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/80 space-y-1.5">
                        {p.enrolled_subjects.map((sub, sIdx) => (
                          <div
                            key={sIdx}
                            className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-300"
                          >
                            <span className="flex items-center gap-1.5 font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                              {sub.subject_name}
                              <span className="text-[10px] font-mono text-slate-400">
                                [{sub.subject_code}]
                              </span>
                            </span>

                            <div className="flex items-center gap-4">
                              {sub.last_score !== null && sub.last_score !== undefined && (
                                <span className="font-mono">
                                  Điểm thi:{" "}
                                  <strong className={sub.last_score < 5.0 ? "text-rose-500" : "text-slate-700 dark:text-slate-200"}>
                                    {sub.last_score.toFixed(1)}
                                  </strong>
                                </span>
                              )}
                              {sub.score_slope !== null && sub.score_slope !== undefined && (
                                <span className="flex items-center gap-0.5 text-[11px] font-mono">
                                  {sub.score_slope > 0 ? (
                                    <TrendingUp className="w-3 h-3 text-emerald-500" />
                                  ) : (
                                    <TrendingDown className="w-3 h-3 text-rose-500" />
                                  )}
                                  {sub.score_slope > 0 ? `+${sub.score_slope.toFixed(2)}` : sub.score_slope.toFixed(2)}
                                </span>
                              )}
                              <span className="font-mono font-bold" style={{ color: RISK_COLORS[sub.risk_level] || "#94a3b8" }}>
                                Rủi ro: {sub.risk_score.toFixed(2)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
