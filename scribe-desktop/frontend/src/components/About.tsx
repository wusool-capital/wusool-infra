import React, { useState, useEffect } from "react";
import { getVersion } from '@tauri-apps/api/app';
import { open } from '@tauri-apps/plugin-shell';
import Image from 'next/image';

export function About() {
    const [currentVersion, setCurrentVersion] = useState<string>('0.4.0');

    useEffect(() => {
        getVersion().then(setCurrentVersion).catch(console.error);
    }, []);

    return (
        <div className="p-4 space-y-4 h-[80vh] overflow-y-auto">
            {/* Compact Header */}
            <div className="text-center">
                <div className="mb-3">
                    <Image
                        src="icon_128x128.png"
                        alt="WusoolScribe Logo"
                        width={64}
                        height={64}
                        className="mx-auto"
                    />
                </div>
                <h1 className="text-xl font-bold text-foreground">WusoolScribe</h1>
                <span className="text-sm text-muted-foreground"> v{currentVersion}</span>
                <p className="text-medium text-muted-foreground mt-1">
                    Real-time notes and summaries, recorded locally and pushed to Scribe.
                </p>
            </div>

            {/* Features Grid - Compact */}
            <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                    <div className="bg-muted rounded p-3 hover:bg-accent transition-colors">
                        <h3 className="font-bold text-sm text-foreground mb-1">Local recording</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">Meeting audio and transcription happen entirely on this machine.</p>
                    </div>
                    <div className="bg-muted rounded p-3 hover:bg-accent transition-colors">
                        <h3 className="font-bold text-sm text-foreground mb-1">Push to Scribe</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">Summaries are generated server-side once you push a meeting.</p>
                    </div>
                    <div className="bg-muted rounded p-3 hover:bg-accent transition-colors">
                        <h3 className="font-bold text-sm text-foreground mb-1">Buyer/Seller tagging</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">Tag meetings with a company and role to organize and match them.</p>
                    </div>
                    <div className="bg-muted rounded p-3 hover:bg-accent transition-colors">
                        <h3 className="font-bold text-sm text-foreground mb-1">Works everywhere</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">Google Meet, Zoom, Teams -- online or offline.</p>
                    </div>
                </div>
            </div>

            <p className="text-center text-xs text-muted-foreground pt-1">
                Made with ❤️ by{' '}
                <button
                    onClick={() => open('https://www.azmora.ai/')}
                    className="text-primary hover:underline cursor-pointer"
                >
                    Azmora
                </button>
            </p>
        </div>
    )
}
