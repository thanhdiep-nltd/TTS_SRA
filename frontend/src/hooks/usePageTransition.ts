"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useApiBusy } from "@/lib/useApiBusy";

/**
 * Hook quản lý trạng thái tải trang (Page Transition).
 * - Đợi hình ảnh (assets) và API call (isApiBusy = false) để kết thúc.
 * - CHỈ xuất hiện khi: F5 (tải lại trang), Login thành công (từ /login sang trang khác), và Logout (về /login).
 */
export function usePageTransition() {
  const [isTransitioning, setIsTransitioning] = useState(true);
  const [isAssetsLoaded, setIsAssetsLoaded] = useState(false);
  
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isApiBusy = useApiBusy();
  
  const prevPathnameRef = useRef(pathname);
  const isInitialMount = useRef(true);

  useEffect(() => {
    let shouldTransition = false;
    
    if (isInitialMount.current) {
      shouldTransition = true;
      isInitialMount.current = false;
    } else {
      const isLogout = pathname === "/login" && prevPathnameRef.current !== "/login";
      const isLogin = prevPathnameRef.current === "/login" && pathname !== "/login";
      
      if (isLogout || isLogin) {
        shouldTransition = true;
      }
    }

    prevPathnameRef.current = pathname;

    if (!shouldTransition) {
      return;
    }

    setIsTransitioning(true);
    setIsAssetsLoaded(false);

    const checkImagesLoaded = () => {
      const images = Array.from(document.images);
      
      if (images.length === 0) {
        setIsAssetsLoaded(true);
        return;
      }

      let loadedCount = 0;
      const onImageComplete = () => {
        loadedCount++;
        if (loadedCount === images.length) {
          setIsAssetsLoaded(true);
        }
      };

      images.forEach((img) => {
        if (img.complete) {
          onImageComplete();
        } else {
          img.addEventListener("load", onImageComplete, { once: true });
          img.addEventListener("error", onImageComplete, { once: true });
        }
      });
    };

    const timerId = setTimeout(() => {
      if (document.readyState === "complete") {
        checkImagesLoaded();
      } else {
        const handleWindowLoad = () => checkImagesLoaded();
        window.addEventListener("load", handleWindowLoad, { once: true });
      }
    }, 50);

    return () => clearTimeout(timerId);
  }, [pathname, searchParams]);

  useEffect(() => {
    if (isTransitioning && isAssetsLoaded && !isApiBusy) {
      const timer = setTimeout(() => {
        setIsTransitioning(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isTransitioning, isAssetsLoaded, isApiBusy]);

  useEffect(() => {
    if (isTransitioning) {
      const fallbackTimer = setTimeout(() => {
        setIsTransitioning(false);
      }, 8000); 
      return () => clearTimeout(fallbackTimer);
    }
  }, [isTransitioning]);

  return { isLoading: isTransitioning };
}
