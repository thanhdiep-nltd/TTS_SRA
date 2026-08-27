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
  Brain,
  Lightbulb,
  Compass,
  CheckCircle2,
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
  const activePillars = useMemo(
    () => (item ? item.pillars.filter((p) => p.is_active) : []),
    [item]
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

  if (!item) return null;
  const riskColor = RISK_COLORS[item.cluster_risk_level] || "#94a3b8";

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="absolute inset-0" onClick={onClose} />

      {/* DRAWER CONTAINER */}
      <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
        {/* HEADER */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-brand-50 dark:bg-brand-950/60 border border-brand-100 dark:border-brand-900/50 flex items-center justify-center text-brand-600 dark:text-brand-400 shrink-0 shadow-2xs">
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
                  Cụm: <strong className="text-brand-600 dark:text-brand-400">{item.cluster_name}</strong>
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

          {/* KHỐI PHÂN TÍCH SƯ PHẠM & KHUYẾN NGHỊ TỪ AI LIÊN MÔN */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-brand-50/70 via-slate-50/40 to-slate-50/50 dark:from-brand-950/30 dark:via-slate-950/20 dark:to-slate-900 border border-brand-200/80 dark:border-brand-900/50 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-brand-100 dark:border-brand-900/60 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-brand-600 text-white shadow-xs">
                  <Brain className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-1.5">
                    Nhận Định Sư Phạm Chuyên Sâu Cụm Liên Môn
                  </h4>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    Phân tích cơ chế lan truyền rủi ro & tương tác đa phân môn
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-brand-600 text-white shadow-2xs flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                AI Synthesis
              </span>
            </div>

            {/* NỘI DUNG NHẬN ĐỊNH SƯ PHẠM */}
            <div className="space-y-3 text-xs leading-relaxed text-slate-700 dark:text-slate-200">
              <div className="p-3 rounded-xl bg-white/80 dark:bg-slate-900/80 border border-brand-100 dark:border-brand-950 space-y-1.5">
                <span className="font-bold text-[11px] uppercase tracking-wider text-brand-600 dark:text-brand-400 flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5" />
                  Đánh Giá Tương Tác Giữa Các Môn:
                </span>
                <p>
                  Học sinh đang có mức rủi ro tích hợp toàn cụm là{" "}
                  <strong className="font-mono font-bold" style={{ color: riskColor }}>
                    {item.cluster_risk_score.toFixed(2)} ({item.cluster_risk_level})
                  </strong>
                  .
                  {item.disparity_index >= 15.0 ? (
                    <span>
                      {" "}Hệ thống ghi nhận <strong>Độ lệch pha cao ({item.disparity_index.toFixed(2)})</strong>, phản ánh tình trạng học lệch nghiêm trọng hoặc có sự mất cân bằng năng lực rõ rệt giữa các trụ cột trong cụm {item.cluster_name}.
                    </span>
                  ) : (
                    <span>
                      {" "}Mức độ dao động giữa các môn tương đối đồng đều (Độ lệch pha: {item.disparity_index.toFixed(2)}).
                    </span>
                  )}
                  {item.bottleneck_subject && (
                    <span className="block mt-1 text-rose-600 dark:text-rose-400">
                      🚨 <strong>Môn {item.bottleneck_subject}</strong> ({item.bottleneck_risk?.toFixed(2)}/100) đang đóng vai trò là <em>Nút thắt cổ chai</em> làm suy giảm toàn bộ tiến trình học tập của cả cụm.
                    </span>
                  )}
                  {item.anchor_subject && (
                    <span className="block mt-0.5 text-emerald-600 dark:text-emerald-400">
                      ⭐ <strong>Môn {item.anchor_subject}</strong> ({item.anchor_risk?.toFixed(2)}/100) là <em>Trụ cột nâng đỡ vững chắc</em>, học sinh có thế mạnh và tâm lý tự tin ở môn học này.
                    </span>
                  )}
                </p>
              </div>

              {/* KHUYẾN NGHỊ KẾ HOẠCH HÀNH ĐỘNG SƯ PHẠM */}
              <div className="space-y-2">
                <span className="font-bold text-[11px] uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                  Kế Hoạch Can Thiệp Sư Phạm Liên Môn Khuyến Nghị:
                </span>

                <div className="grid grid-cols-1 gap-2">
                  <div className="p-2.5 rounded-xl bg-white/70 dark:bg-slate-900/70 border border-slate-200/60 dark:border-slate-800 flex items-start gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                      1
                    </div>
                    <div>
                      <strong className="text-slate-900 dark:text-white">
                        {item.bottleneck_subject
                          ? `Phụ đạo trọng điểm gỡ nút thắt môn ${item.bottleneck_subject}`
                          : "Tăng cường củng cố chuyên đề yếu"}
                      </strong>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        {item.bottleneck_subject
                          ? `Giáo viên bộ môn ${item.bottleneck_subject} cần rà soát lại các lỗ hổng kiến thức căn bản của học sinh để phụ đạo kèm 1-1, tránh để môn này tiếp tục kéo tụt kết quả học tập.`
                          : "Theo dõi sát sao tiến độ làm bài tập trên LMS và điểm kiểm tra định kỳ."}
                      </p>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white/70 dark:bg-slate-900/70 border border-slate-200/60 dark:border-slate-800 flex items-start gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                      2
                    </div>
                    <div>
                      <strong className="text-slate-900 dark:text-white">
                        {item.anchor_subject
                          ? `Sử dụng môn ${item.anchor_subject} làm đòn bẩy tâm lý & dự án liên môn`
                          : "Giao nhiệm vụ dự án nhóm tích hợp"}
                      </strong>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        {item.anchor_subject && item.bottleneck_subject
                          ? `Xây dựng bài tập hoặc dự án thực hành liên môn kết hợp giữa môn thế mạnh (${item.anchor_subject}) với môn đang gặp khó (${item.bottleneck_subject}) để khơi gợi hứng thú và sự tự tin.`
                          : "Khuyến khích học sinh tham gia các hoạt động trải nghiệm thực hành liên môn theo nhóm."}
                      </p>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white/70 dark:bg-slate-900/70 border border-slate-200/60 dark:border-slate-800 flex items-start gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                      3
                    </div>
                    <div>
                      <strong className="text-slate-900 dark:text-white">
                        Phối hợp liên giáo viên (GVBM & GVCN)
                      </strong>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        GVCN định kỳ trao đổi hàng tuần với giáo viên các môn trong cụm {item.cluster_name} để cập nhật mức độ cải thiện và điều chỉnh phương pháp kịp thời.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* RADAR CHART NGŨ GIÁC NĂNG LỰC RỦI RO LIÊN MÔN */}
          <div className="p-5 rounded-2xl bg-slate-50/60 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-brand-600 dark:text-brand-400" />
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
