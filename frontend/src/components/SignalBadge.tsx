export type SignalVariant = 'positive' | 'neutral' | 'warning' | 'danger' | 'insufficient';

type Props = {
  label?: string;
  variant?: SignalVariant;
};

export function variantForLabel(label?: string): SignalVariant {
  const value = (label ?? '').toLowerCase();
  if (value.includes('insufficient')) return 'insufficient';
  if (value.includes('risk') || value.includes('crisis') || value.includes('negative')) return 'danger';
  if (value.includes('overheated') || value.includes('warning') || value.includes('watch')) return 'warning';
  if (value.includes('positive') || value.includes('favorable') || value.includes('worth')) return 'positive';
  return 'neutral';
}

export default function SignalBadge({ label = 'neutral', variant }: Props) {
  const resolved = variant ?? variantForLabel(label);
  return <span className={`signalBadge ${resolved}`}>{label}</span>;
}
