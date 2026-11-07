import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface SettingsSectionProps {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** One settings area: a heading, then a single panel whose rows are split by rules. */
export function SettingsSection({ title, description, children, className }: SettingsSectionProps) {
  return (
    <section className={cn('space-y-3', className)}>
      <div>
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      <div className="divide-y divide-border rounded-lg border border-border bg-card">{children}</div>
    </section>
  );
}

interface SettingsRowProps {
  title: ReactNode;
  description?: ReactNode;
  /** The control, aligned to the title line on the right. */
  control?: ReactNode;
  /** Content under the text that spans the row, such as a list or a field. */
  children?: ReactNode;
  htmlFor?: string;
}

export function SettingsRow({ title, description, control, children, htmlFor }: SettingsRowProps) {
  const Title = htmlFor ? 'label' : 'div';
  return (
    <div className="px-5 py-4">
      <div className="flex items-start justify-between gap-6">
        {/* min-w-0 lets long descriptions wrap instead of running under the control. */}
        <div className="min-w-0 flex-1">
          <Title htmlFor={htmlFor} className="block text-sm font-medium text-foreground">
            {title}
          </Title>
          {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
        </div>
        {control && <div className="flex shrink-0 items-center">{control}</div>}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
