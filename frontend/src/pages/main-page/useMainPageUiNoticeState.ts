import { useCallback, useState } from "react";

export type MainPageUiNoticeState = {
  clearUiNotice: () => void;
  setUiNotice: (notice: string | null) => void;
  uiNotice: string | null;
};

export function useMainPageUiNoticeState(): MainPageUiNoticeState {
  const [uiNotice, setUiNotice] = useState<string | null>(null);

  const clearUiNotice = useCallback(() => {
    setUiNotice(null);
  }, []);

  return {
    clearUiNotice,
    setUiNotice,
    uiNotice,
  };
}
