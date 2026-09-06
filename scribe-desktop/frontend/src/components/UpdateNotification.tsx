import { toast } from 'sonner';
import { UpdateInfo } from '@/services/updateService';

let globalShowDialogCallback: (() => void) | null = null;

export function setUpdateDialogCallback(callback: () => void) {
  globalShowDialogCallback = callback;
}

export function showUpdateNotification(updateInfo: UpdateInfo, onUpdateClick?: () => void) {
  const handleClick = () => {
    if (onUpdateClick) {
      onUpdateClick();
    } else if (globalShowDialogCallback) {
      globalShowDialogCallback();
    }
  };

  // Plain title/description/action, not custom JSX: this is the only way
  // the app's global ThemedToaster (src/app/layout.tsx) styling - its
  // themed info icon, classNames, and bottom-right placement - actually
  // applies. Custom JSX bypasses all of that and doubles up the icon.
  toast.info('Update Available', {
    description: `Version ${updateInfo.version} is now available`,
    duration: 10000,
    action: {
      label: 'View Details',
      onClick: handleClick,
    },
  });
}
