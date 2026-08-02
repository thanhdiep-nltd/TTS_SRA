"use client";

import React, { useState } from "react";
import { ListChecks, ChevronRight, CheckCircle } from "lucide-react";

export interface OptionCardData {
  title?: string;
  prompt?: string;
  options: string[];
}

interface OptionSelectionCardProps {
  data: OptionCardData;
  onSelectOption: (optionText: string) => void;
  disabled?: boolean;
}

export const OptionSelectionCard: React.FC<OptionSelectionCardProps> = ({
  data,
  onSelectOption,
  disabled = false,
}) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  if (!data || !data.options || data.options.length === 0) return null;

  const cardTitle = data.title || "Vui lòng chọn một tùy chọn";
  const cardPrompt = data.prompt;

  const handleOptionClick = (option: string) => {
    if (disabled || selectedOption) return;
    setSelectedOption(option);
    onSelectOption(option);
  };

  return (
    <div className="my-2.5 p-3.5 sm:p-4 rounded-xl bg-brand-50/40 dark:bg-brand-950/20 border border-brand-200/70 dark:border-brand-900/50 shadow-2xs max-w-md w-full space-y-2.5 transition-all animate-in fade-in duration-200">
      {/* Card Header: Icon + Title */}
      <div className="flex items-center gap-2">
        <div className="flex items-center justify-center w-6 h-6 rounded-md bg-brand-100 dark:bg-brand-950 text-brand-600 dark:text-brand-400 shrink-0">
          <ListChecks className="w-3.5 h-3.5" />
        </div>
        <h4 className="font-bold text-slate-800 dark:text-slate-100 text-xs tracking-tight">
          {cardTitle}
        </h4>
      </div>

      {/* Card Subtitle / Prompt */}
      {cardPrompt && (
        <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed font-medium">
          {cardPrompt}
        </p>
      )}

      {/* Choice Option Buttons */}
      <div className="space-y-1.5 pt-0.5">
        {data.options.map((optionText, idx) => {
          const isSelected = selectedOption === optionText;
          return (
            <button
              key={idx}
              type="button"
              disabled={disabled || (selectedOption !== null && !isSelected)}
              onClick={() => handleOptionClick(optionText)}
              className={`w-full p-2.5 rounded-lg border text-left flex items-center justify-between gap-2.5 text-xs font-medium transition duration-150 cursor-pointer ${
                isSelected
                  ? "bg-brand-600 text-white border-brand-600 shadow-2xs"
                  : selectedOption !== null
                  ? "bg-white/60 dark:bg-slate-900/40 border-slate-200/50 dark:border-slate-800 text-slate-400 dark:text-slate-600 opacity-60 cursor-not-allowed"
                  : "bg-white dark:bg-slate-900 border-brand-200/70 dark:border-brand-900/40 text-slate-800 dark:text-slate-100 hover:border-brand-400 dark:hover:border-brand-600 hover:bg-brand-50/80 dark:hover:bg-brand-950/40 active:scale-[0.99] group"
              }`}
            >
              <span className="truncate flex-1">{optionText}</span>
              {isSelected ? (
                <CheckCircle className="w-3.5 h-3.5 text-white shrink-0 animate-in zoom-in-50 duration-150" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 opacity-70 shrink-0 group-hover:translate-x-0.5 transition-transform" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default OptionSelectionCard;
