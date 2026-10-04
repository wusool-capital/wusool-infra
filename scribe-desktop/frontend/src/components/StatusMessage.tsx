import { Item, ItemMedia, ItemTitle } from '@/components/ui/item';
import { Spinner } from '@/components/ui/spinner';

interface StatusMessageProps {
  message: string;
}

// One look for every "working on it" state after a recording stops.
export function StatusMessage({ message }: StatusMessageProps) {
  return (
    <Item className="flex-nowrap gap-2 p-0">
      <ItemMedia>
        <Spinner />
      </ItemMedia>
      <ItemTitle>{message}</ItemTitle>
    </Item>
  );
}
