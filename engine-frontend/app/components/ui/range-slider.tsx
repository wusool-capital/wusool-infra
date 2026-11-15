import * as Slider from "@radix-ui/react-slider";

type Props = {
  /** What the slider sets, for screen readers. */
  label: string;
  /** Every position a thumb can take, lowest first. */
  stops: number[];
  /** The two thumbs, as positions in `stops`. */
  value: [number, number];
  onChange: (value: [number, number]) => void;
  /** How a stop reads aloud, such as "$200K". */
  format: (stop: number) => string;
};

/** A two-thumb slider that snaps to fixed stops, so a value is always one the screen names. */
export function RangeSlider({ label, stops, value, onChange, format }: Props) {
  return (
    <Slider.Root
      className="slider"
      min={0}
      max={stops.length - 1}
      step={1}
      minStepsBetweenThumbs={0}
      value={value}
      onValueChange={(next) => onChange([next[0] ?? 0, next[1] ?? stops.length - 1])}
    >
      <Slider.Track className="slider__track">
        <Slider.Range className="slider__range" />
      </Slider.Track>
      <Slider.Thumb className="slider__thumb" aria-label={`${label}, lowest`} aria-valuetext={format(stops[value[0]] ?? 0)} />
      <Slider.Thumb className="slider__thumb" aria-label={`${label}, highest`} aria-valuetext={format(stops[value[1]] ?? 0)} />
    </Slider.Root>
  );
}
