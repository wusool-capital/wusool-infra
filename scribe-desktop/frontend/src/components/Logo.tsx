import React from "react";
import Image from "next/image";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "./ui/dialog";
import { VisuallyHidden } from "./ui/visually-hidden";
import { About } from "./About";

interface LogoProps {
    isCollapsed: boolean;
}

const Logo = React.forwardRef<HTMLButtonElement, LogoProps>(({ isCollapsed }, ref) => {
  return (
    <Dialog aria-describedby={undefined}>
      {isCollapsed ? (
        <DialogTrigger asChild>
          <button ref={ref} className="flex items-center justify-start cursor-pointer bg-transparent border-none p-0 hover:opacity-80 transition-opacity">
            <Image src="/logo-collapsed.png" alt="Logo" width={40} height={32} className="rounded-lg" />
          </button>
        </DialogTrigger>
      ) : (
        <DialogTrigger asChild>
          <button className="h-10 inline-flex items-center gap-2.5 rounded-lg px-1.5 -ml-1.5 cursor-pointer hover:bg-accent/60 transition-colors">
            <Image src="/logo-collapsed.png" alt="" width={30} height={24} className="flex-shrink-0 rounded-[6px]" />
            <span className="text-base font-semibold tracking-tight text-foreground">
              Wusool<span className="font-normal text-muted-foreground">Scribe</span>
            </span>
          </button>
        </DialogTrigger>
      )}
      <DialogContent>
        <VisuallyHidden>
          <DialogTitle>About WusoolScribe</DialogTitle>
        </VisuallyHidden>
        <About />
      </DialogContent>
    </Dialog>
  );
});

Logo.displayName = "Logo";

export default Logo;
