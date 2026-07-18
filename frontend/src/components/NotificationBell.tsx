"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, Megaphone, User as UserIcon, Clock, X } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ANNOUNCEMENT_ROLES, type NotificationItem } from "@/lib/types";
import { Spinner } from "./Loading";
import AnnouncementComposeModal from "./AnnouncementComposeModal";

const POLL_MS = 45_000;

// Icon chuông + dropdown thông báo, đặt trong footer Sidebar. Không có WebSocket — chỉ poll nhẹ
// số chưa đọc theo định kỳ (đủ cho quy mô vài chục GV/trường, xem docs/exam_generation_ui_design.md §C.6).
export default function NotificationBell({ collapsed }: { collapsed: boolean }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedNotif, setSelectedNotif] = useState<NotificationItem | null>(null);

  const refreshCount = useCallback(() => {
    api.get<{ count: number }>("/notifications/unread-count").then((r) => setUnread(r.count)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, POLL_MS);
    return () => clearInterval(id);
  }, [refreshCount]);

  const loadList = useCallback(() => {
    setLoading(true);
    api
      .get<NotificationItem[]>("/notifications?limit=10")
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const toggleOpen = () => {
    const next = !open;
    setOpen(next);
    if (next) loadList();
  };

  const handleMarkRead = async (id: string) => {
    const item = items.find((n) => n.id === id);
    if (item && !item.read_at) {
      setItems((cur) => cur.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
      setUnread((c) => Math.max(0, c - 1));
      try {
        await api.post(`/notifications/${id}/read`);
      } catch {
        // Lỗi mark-read lặt vặt
      }
    }
  };

  const handleMarkAll = async () => {
    const now = new Date().toISOString();
    setItems((cur) => cur.map((n) => ({ ...n, read_at: n.read_at ?? now })));
    setUnread(0);
    try {
      await api.post("/notifications/read-all");
    } catch {
      // tương tự handleMarkRead
    }
  };

  const handleItemClick = (n: NotificationItem) => {
    handleMarkRead(n.id);
    setSelectedNotif(n);
    setOpen(false); // Đóng dropdown danh sách
  };

  const canCompose = !!user && ANNOUNCEMENT_ROLES.includes(user.role);

  return (
    <>
      <div className="relative">
        <button
          type="button"
          onClick={toggleOpen}
          title="Thông báo"
          className="relative p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unread > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-accent-600 text-white text-[10px] font-bold flex items-center justify-center">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>

        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <div
              className={`absolute bottom-[48px] ${collapsed ? "left-2" : "left-4"} w-[340px] max-w-[90vw] bg-white dark:bg-slate-850 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl z-40 flex flex-col animate-in slide-in-from-bottom-2 duration-150`}
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Thông báo</span>
                <div className="flex items-center gap-3">
                  {canCompose && (
                    <button
                      type="button"
                      onClick={() => { setComposeOpen(true); setOpen(false); }}
                      className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
                    >
                      <Megaphone className="w-3.5 h-3.5" /> Soạn
                    </button>
                  )}
                  {unread > 0 && (
                    <button type="button" onClick={handleMarkAll} className="text-xs text-slate-500 hover:underline">
                      Đọc tất cả
                    </button>
                  )}
                </div>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {loading ? (
                  <div className="px-4 py-6 flex justify-center"><Spinner className="w-5 h-5" /></div>
                ) : items.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-slate-400">Chưa có thông báo nào.</div>
                ) : (
                  items.map((n) => (
                    <button
                      key={n.id}
                      type="button"
                      onClick={() => handleItemClick(n)}
                      className={`w-full text-left px-4 py-3 border-b border-slate-50 dark:border-slate-800/60 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition ${
                        !n.read_at ? "bg-brand-50/50 dark:bg-brand-500/5" : ""
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {!n.read_at && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0" />}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{n.title}</p>
                          <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-0.5">{n.message}</p>
                          <p className="text-[10px] text-slate-400 mt-1">{formatRelative(n.created_at)}</p>
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {composeOpen && <AnnouncementComposeModal onClose={() => setComposeOpen(false)} />}
      
      {selectedNotif && (
        <NotificationDetailModal
          notification={selectedNotif}
          onClose={() => setSelectedNotif(null)}
        />
      )}
    </>
  );
}

interface DetailModalProps {
  notification: NotificationItem;
  onClose: () => void;
}

function NotificationDetailModal({ notification, onClose }: DetailModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div 
        className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white">Chi tiết thông báo</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-550 dark:text-slate-400" />
          </button>
        </div>
        
        <div className="p-5 space-y-4">
          <div>
            <h4 className="text-lg font-bold text-slate-900 dark:text-white break-words">
              {notification.title}
            </h4>
            
            <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 text-xs text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-1.5">
                <UserIcon className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                <span>Người gửi: <b>{notification.sender_name ?? "Hệ thống"}</b></span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-slate-400" />
                <span>Gửi lúc: {new Date(notification.created_at).toLocaleString("vi-VN")}</span>
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-200 dark:bg-slate-800" />

          <div className="max-h-[300px] overflow-y-auto pr-1">
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
              {notification.message}
            </p>
          </div>
        </div>
        
        <div className="flex justify-end px-5 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 rounded-b-2xl">
          <button onClick={onClose} className="px-4 py-2 bg-brand-600 hover:bg-brand-550 text-white rounded-lg text-sm font-semibold shadow-sm cursor-pointer transition">
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

function formatRelative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Vừa xong";
  if (mins < 60) return `${mins} phút trước`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return `${days} ngày trước`;
}
