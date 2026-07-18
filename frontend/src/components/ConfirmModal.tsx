"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed -inset-10 bg-black/45 z-[90] animate-in fade-in duration-200" />
      {/* Modal Box */}
      <div className="fixed inset-0 flex items-center justify-center p-4 z-[100] animate-in zoom-in-95 duration-200">
        <div className="w-full max-w-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-2xl flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-full bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="space-y-1 flex-1">
              <h4 className="font-bold text-slate-800 dark:text-white text-sm leading-snug">
                {title}
              </h4>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed whitespace-pre-line">
                {message}
              </p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-3">
            <button
              onClick={onCancel}
              className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
            >
              Hủy
            </button>
            <button
              onClick={onConfirm}
              className="px-3.5 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-bold cursor-pointer transition-colors shadow-sm"
            >
              Xác nhận
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
