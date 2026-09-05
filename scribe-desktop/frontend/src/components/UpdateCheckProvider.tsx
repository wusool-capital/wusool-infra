'use client'

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { useUpdateCheck } from '@/hooks/useUpdateCheck';
import { UpdateInfo } from '@/services/updateService';
import { UpdateDialog } from './UpdateDialog';
import { setUpdateDialogCallback, showUpdateNotification } from './UpdateNotification';

interface UpdateCheckContextType {
  updateInfo: UpdateInfo | null;
  isChecking: boolean;
  checkForUpdates: (force?: boolean) => Promise<void>;
  showUpdateDialog: () => void;
}

const UpdateCheckContext = createContext<UpdateCheckContextType | undefined>(undefined);

export function UpdateCheckProvider({ children }: { children: React.ReactNode }) {
  const [showDialog, setShowDialog] = useState(false);

  const handleShowDialog = useCallback(() => {
    setShowDialog(true);
  }, []);

  const handleUpdateAvailable = useCallback(
    (info: UpdateInfo) => {
      showUpdateNotification(info, handleShowDialog);
    },
    [handleShowDialog]
  );

  const { updateInfo, isChecking, checkForUpdates } = useUpdateCheck({
    checkOnMount: true,
    showNotification: false,
    onUpdateAvailable: handleUpdateAvailable,
  });

  useEffect(() => {
    // Register the callback so UpdateNotification can trigger the dialog
    setUpdateDialogCallback(handleShowDialog);
    return () => {
      setUpdateDialogCallback(() => {});
    };
  }, [handleShowDialog]);

  // Listen for tray menu events
  useEffect(() => {
    const handleTrayCheck = async () => {
      const info = await checkForUpdates(true); // Force check from tray
      if (info?.available) {
        setShowDialog(true);
      } else if (info) {
        toast.success(`WusoolScribe is up to date (v${info.currentVersion})`);
      } else {
        toast.error('Could not check for updates');
      }
    };

    window.addEventListener('check-updates-from-tray', handleTrayCheck);
    return () => window.removeEventListener('check-updates-from-tray', handleTrayCheck);
  }, [checkForUpdates]);

  return (
    <UpdateCheckContext.Provider
      value={{
        updateInfo,
        isChecking,
        checkForUpdates,
        showUpdateDialog: handleShowDialog,
      }}
    >
      {children}
      <UpdateDialog
        open={showDialog}
        onOpenChange={setShowDialog}
        updateInfo={updateInfo}
      />
    </UpdateCheckContext.Provider>
  );
}

export function useUpdateCheckContext() {
  const context = useContext(UpdateCheckContext);
  if (context === undefined) {
    throw new Error('useUpdateCheckContext must be used within UpdateCheckProvider');
  }
  return context;
}
