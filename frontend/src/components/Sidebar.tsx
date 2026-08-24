"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useMemo } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  ClipboardList,
  Table2,
  BookOpen,
  ListChecks,
  FilePlus2,
  Building2,
  Users,
  UserCog,
  FileText,
  ChevronLeft,
  Sun,
  Moon,
  LogOut,
  Settings,
  PanelLeftOpen,
  BarChart3,
  Network,
  Mic,
  Presentation,
  AlertTriangle,
  TrendingUp,
  Gauge,
  Database,
  FolderTree,
} from "lucide-react";

import PresentationModal from "./PresentationModal";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { QUESTION_BANK_ROLES, ROLE_LABELS } from "@/lib/types";
import NotificationBell from "./NotificationBell";

const MENU = [
  { name: "Tổng quan Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { name: "Kế hoạch bài dạy", path: "/lesson-plans", icon: BookOpen },
  { name: "Bảng điểm", path: "/gradebook", icon: Table2 },
  { name: "Phân tích độ khó đề", path: "/exam-difficulty", icon: Gauge },
  { name: "Lỗ hổng kiến thức", path: "/knowledge-gaps", icon: AlertTriangle },
  { name: "Dự đoán pass/fail", path: "/pass-fail-forecast", icon: TrendingUp },
  { name: "Đánh giá tiết dạy", path: "/recordings", icon: Mic },
  { name: "Xuất báo cáo", path: "/reports", icon: FileText },
  { name: "Trợ lý AI (Chatbot)", path: "/chat", icon: MessageSquare },
];

const QUESTION_BANK_MENU = [
  { name: "Ngân hàng câu hỏi", path: "/question-bank", icon: ListChecks },
  { name: "Tạo đề thi", path: "/exam-builder", icon: FilePlus2 },
];

const ADMIN_MENU = [
  { name: "Cơ cấu trường", path: "/admin/school", icon: Building2 },
  { name: "Học sinh", path: "/admin/students", icon: Users },
  { name: "Tài khoản & Phân công", path: "/admin/users", icon: UserCog },
  { name: "Kho tri thức & SGK", path: "/admin/knowledge", icon: Database },
  { name: "Chương trình (catalog)", path: "/admin/curriculum", icon: FolderTree },
  { name: "Đánh giá & Thống kê AI", path: "/admin/ai-metrics", icon: BarChart3 },
  { name: "Giám sát Multi-Agent", path: "/dashboard/agents", icon: Network },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showSettingsPopover, setShowSettingsPopover] = useState(false);
  const [showPresentation, setShowPresentation] = useState(false);

  const mainMenuItems = useMemo(() => {
    const items = [...MENU];
    if (user?.homeroom_class_id) {
      items.splice(2, 0, { name: "Lớp chủ nhiệm", path: "/homeroom", icon: ClipboardList });
    }
    return items;
  }, [user]);

  // Ghi nhớ trạng thái thu gọn qua localStorage
  useEffect(() => {
    const saved = localStorage.getItem("sidebar_collapsed");
    if (saved === "true") {
      setIsCollapsed(true);
    }
  }, []);

  const [hoveredItem, setHoveredItem] = useState<{
    name: string;
    top: number;
    left: number;
    height: number;
    width: number;
  } | null>(null);

  const handleMouseEnter = (name: string, e: React.MouseEvent<HTMLAnchorElement | HTMLButtonElement | HTMLDivElement>) => {
    if (!isCollapsed) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setHoveredItem({
      name,
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    });
  };

  const handleMouseLeave = () => {
    setHoveredItem(null);
  };

  const toggleCollapse = () => {
    const newVal = !isCollapsed;
    setIsCollapsed(newVal);
    setHoveredItem(null); // Clear tooltips when toggling sidebar
    localStorage.setItem("sidebar_collapsed", String(newVal));
  };

  return (
    <aside
      className={`shrink-0 flex flex-col h-screen border-r bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 transition-elastic rounded-tr-2xl rounded-br-2xl relative z-20 ${isCollapsed ? "w-[72px]" : "w-64"
        }`}
    >
      {/* Brand */}
      <div
        className={`border-b border-slate-200 dark:border-slate-800 flex items-center justify-between h-[72px] shrink-0 transition-elastic ${isCollapsed ? "px-4 py-4 justify-center" : "p-6 gap-3"
          }`}
      >
        {isCollapsed ? (
          /* Collapsed State: Morphing Logo Toggle */
          <div className="logo-toggle-container" onClick={toggleCollapse}>
            <div className="logo-icon-state">
              <img src="/logo.svg" className="w-[22px] h-[22px] object-contain brightness-0 invert" alt="Logo" />
            </div>
            <div className="toggle-icon-state open-icon-state">
              <PanelLeftOpen className="w-5 h-5" />
            </div>
            {/* Tooltip bubble matching the option 4.2 design */}
            <div className="tooltip-bubble">
              <span className="tooltip-text-open">Mở thanh bên</span>
            </div>
          </div>
        ) : (
          /* Expanded State: Static Logo + Brand text + Collapse Button */
          <>
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-10 h-10 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center shrink-0 shadow-md animate-in fade-in duration-200">
                <img src="/logo.svg" className="w-7 h-7 object-contain" alt="Logo" />
              </div>
              <div className="min-w-0 animate-in slide-in-from-left-2 duration-200">
                <h1 className="font-bold text-sm leading-tight text-brand-700 dark:text-brand-400 truncate">
                  SchoolAI
                </h1>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium block truncate mt-0.5">
                  Phân tích học tập
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={toggleCollapse}
              className="btn-sidebar-collapse animate-in fade-in zoom-in-75 duration-200"
              title="Thu gọn menu"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1.5 overflow-y-auto overflow-x-hidden [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {!isCollapsed ? (
          <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase px-3 mb-2 tracking-wider">
            Chức năng chính
          </div>
        ) : (
          <div className="h-2" />
        )}
        {mainMenuItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.path;
          return (
            <Link
              key={item.path}
              href={item.path}
              onMouseEnter={(e) => handleMouseEnter(item.name, e)}
              onMouseLeave={handleMouseLeave}
              className={`flex items-center gap-3 py-2.5 rounded-lg text-sm font-medium transition-elastic group relative ${isCollapsed ? "px-0 justify-center hover:scale-[1.15] transition-transform" : "px-3"
                } ${active
                  ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                }`}
            >
              <Icon className={`w-5 h-5 shrink-0 ${active ? "text-white" : "text-slate-400 group-hover:text-brand-500"}`} />
              {!isCollapsed && (
                <span className="animate-in fade-in duration-250">{item.name}</span>
              )}
            </Link>
          );
        })}

        {!!user && QUESTION_BANK_ROLES.includes(user.role) && (
          <>
            {!isCollapsed ? (
              <div className="pt-6 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase px-3 mb-2 tracking-wider">
                Đề thi
              </div>
            ) : (
              <div className="h-6 border-t border-slate-100 dark:border-slate-800/80 my-4" />
            )}
            {QUESTION_BANK_MENU.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.path;
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  onMouseEnter={(e) => handleMouseEnter(item.name, e)}
                  onMouseLeave={handleMouseLeave}
                  className={`flex items-center gap-3 py-2.5 rounded-lg text-sm font-medium transition-elastic group relative ${isCollapsed ? "px-0 justify-center hover:scale-[1.15] transition-transform" : "px-3"
                    } ${active
                      ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                      : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                    }`}
                >
                  <Icon className={`w-5 h-5 shrink-0 ${active ? "text-white" : "text-slate-400 group-hover:text-brand-500"}`} />
                  {!isCollapsed && (
                    <span className="animate-in fade-in duration-250">{item.name}</span>
                  )}
                </Link>
              );
            })}
          </>
        )}

        {(user?.role === "ADMIN" || user?.role === "PRINCIPAL") && (
          <>
            {!isCollapsed ? (
              <div className="pt-6 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase px-3 mb-2 tracking-wider">
                Quản trị
              </div>
            ) : (
              <div className="h-6 border-t border-slate-100 dark:border-slate-800/80 my-4" />
            )}
            {ADMIN_MENU
              .filter((item) => user?.role === "ADMIN" || (item.path !== "/admin/ai-metrics" && item.path !== "/dashboard/agents"))
              .map((item) => {
                const Icon = item.icon;
                const active = pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    href={item.path}
                    onMouseEnter={(e) => handleMouseEnter(item.name, e)}
                    onMouseLeave={handleMouseLeave}
                    className={`flex items-center gap-3 py-2.5 rounded-lg text-sm font-medium transition-elastic group relative ${isCollapsed ? "px-0 justify-center hover:scale-[1.15] transition-transform" : "px-3"
                      } ${active
                        ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                      }`}
                  >
                    <Icon className={`w-5 h-5 shrink-0 ${active ? "text-white" : "text-slate-400 group-hover:text-brand-500"}`} />
                    {!isCollapsed && (
                      <span className="animate-in fade-in duration-250">{item.name}</span>
                    )}
                  </Link>
                );
              })}
          </>
        )}


      </nav>

      {/* User footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 shrink-0 relative">
        {/* Settings Popover Dropdown */}
        {showSettingsPopover && (
          <>
            <div
              className="fixed inset-0 z-30"
              onClick={() => setShowSettingsPopover(false)}
            />
            <div className={`absolute bottom-[80px] mb-1 bg-white dark:bg-slate-850 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl py-2 min-w-[200px] flex flex-col z-40 animate-in slide-in-from-bottom-2 duration-150 ${isCollapsed ? "left-2" : "right-4"
              }`}>
              {/* Item 1: Tài liệu hướng dẫn */}
              <a
                href="https://phoenix.note.transformerlabs.ai/technical-book"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setShowSettingsPopover(false)}
                className="px-4 py-2.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2.5 transition"
              >
                <BookOpen className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                <span>Tài liệu hướng dẫn</span>
              </a>

              {/* Item 2: Đổi giao diện */}
              <button
                type="button"
                onClick={() => {
                  toggleTheme();
                  setShowSettingsPopover(false);
                }}
                className="px-4 py-2.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2.5 transition w-full"
              >
                {theme === "dark" ? (
                  <>
                    <Sun className="w-4 h-4 text-amber-500 shrink-0" />
                    <span>Giao diện sáng</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0" />
                    <span>Giao diện tối</span>
                  </>
                )}
              </button>

              {/* Item 2.5: Thuyết trình */}
              <button
                type="button"
                onClick={() => {
                  setShowPresentation(true);
                  setShowSettingsPopover(false);
                }}
                className="px-4 py-2.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2.5 transition w-full"
              >
                <Presentation className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                <span>Thuyết trình dự án</span>
              </button>

              <div className="h-px bg-slate-100 dark:bg-slate-700 my-1" />

              {/* Item 3: Đăng xuất */}
              <button
                type="button"
                onClick={() => {
                  logout();
                  setShowSettingsPopover(false);
                }}
                className="px-4 py-2.5 text-left text-xs font-semibold text-rose-600 dark:text-rose-450 hover:bg-rose-50 dark:hover:bg-rose-950/20 flex items-center gap-2.5 transition w-full"
              >
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Đăng xuất</span>
              </button>
            </div>
          </>
        )}

        {/* Thông báo */}
        <div className={`flex items-center mb-3 ${isCollapsed ? "justify-center" : "justify-end"}`}>
          <NotificationBell collapsed={isCollapsed} />
        </div>

        {/* User Account Info Display */}
        <div className="relative flex items-center justify-between group">
          <div className={`flex items-center gap-3 min-w-0 ${isCollapsed ? "w-full justify-center" : "flex-1"}`}>
            <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-slate-800/80 border border-brand-100 dark:border-slate-700/50 flex items-center justify-center text-brand-600 dark:text-brand-400 font-bold shrink-0 shadow-sm">
              {user?.full_name?.charAt(0) ?? "?"}
            </div>
            {!isCollapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">
                  {user?.full_name ?? "—"}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-450 truncate">
                  {user ? ROLE_LABELS[user.role] : ""}
                </p>
              </div>
            )}
          </div>

          {/* Settings Trigger Icon Button */}
          <button
            type="button"
            onClick={() => setShowSettingsPopover(!showSettingsPopover)}
            onMouseEnter={(e) => handleMouseEnter("Cài đặt & Tài khoản", e)}
            onMouseLeave={handleMouseLeave}
            className={`p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-slate-200 transition-colors shrink-0 ${isCollapsed ? "absolute inset-0 opacity-0 cursor-pointer w-full h-full" : "ml-2"
              }`}
            title={!isCollapsed ? "Cài đặt & Tài khoản" : undefined}
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Floating Tooltip outside nav scroll container */}
      {hoveredItem && isCollapsed && (
        <div
          className="fixed bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 border border-slate-200/60 dark:border-slate-700/50 px-3 py-1.5 rounded-2xl text-[12.5px] font-semibold shadow-2xl z-[999] pointer-events-none transition-all flex items-center"
          style={{
            top: hoveredItem.top + hoveredItem.height / 2,
            left: hoveredItem.left + hoveredItem.width + 12,
            transform: "translateY(-50%)",
          }}
        >
          {/* Arrow pointing left */}
          <div className="absolute left-[-6px] top-1/2 -translate-y-1/2 border-t-[6px] border-t-transparent border-b-[6px] border-b-transparent border-right-[6px] border-right-white dark:border-right-slate-800" />
          {hoveredItem.name}
        </div>
      )}

      <PresentationModal
        isOpen={showPresentation}
        onClose={() => setShowPresentation(false)}
        theme={theme}
      />
    </aside>
  );
}
