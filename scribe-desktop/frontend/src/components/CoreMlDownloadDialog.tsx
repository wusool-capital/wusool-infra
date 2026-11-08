"use client"

import type { CoreMlModels } from "@/hooks/useCoreMlModels"
import { Button } from "./ui/button"
import { Progress } from "./ui/progress"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog"

const megabytes = (bytes: number) => Math.round(bytes / 1_000_000)

interface CoreMlDownloadDialogProps {
  coreMl: CoreMlModels
  description: string
  /** The button that skips the download, e.g. "Not Now" or "Use Standard Speed". */
  skipLabel: string
  onSkip?: () => void
  onDownloaded?: () => void
}

/** The one-time CoreML model download, with progress; closing it mid-download cancels. */
export function CoreMlDownloadDialog({ coreMl, description, skipLabel, onSkip, onDownloaded }: CoreMlDownloadDialogProps) {
  const { download, progress } = coreMl

  const startDownload = async () => {
    if (await coreMl.start()) onDownloaded?.()
  }

  const skip = () => {
    coreMl.close()
    onSkip?.()
  }

  return (
    <Dialog open={download.stage !== "closed"} onOpenChange={(open) => !open && coreMl.close()}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Download Faster Speaker Separation</DialogTitle>
          <DialogDescription>
            {download.stage === "failed" ? `The download didn't finish: ${download.error}` : description}
          </DialogDescription>
        </DialogHeader>
        {download.stage === "downloading" && (
          <div className="space-y-2">
            <Progress value={progress.total > 0 ? (progress.downloaded / progress.total) * 100 : 0} />
            <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
              {progress.total > 0
                ? `${megabytes(progress.downloaded)} of ${megabytes(progress.total)} MB`
                : progress.downloaded > 0
                  ? `${megabytes(progress.downloaded)} MB downloaded`
                  : "Preparing download…"}
            </p>
          </div>
        )}
        <DialogFooter>
          {download.stage === "downloading" ? (
            <Button variant="outline" onClick={coreMl.close}>
              Cancel
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={skip}>
                {skipLabel}
              </Button>
              <Button onClick={() => void startDownload()}>
                {download.stage === "failed" ? "Try Again" : "Download"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
