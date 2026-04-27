type Props = {
  terms: string[];
};

export default function WarningBanner({ terms }: Props) {
  if (!terms.length || import.meta.env.MODE === 'production') return null;
  return (
    <div className="warningBanner" role="alert">
      Potential restricted language detected in development data: {terms.join(', ')}
    </div>
  );
}
