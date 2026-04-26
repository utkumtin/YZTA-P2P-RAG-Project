export default function StreamingIndicator() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', verticalAlign: 'middle', padding: '4px 0' }}>
      <Dot delay="0s" />
      <Dot delay=".18s" />
      <Dot delay=".36s" />
    </span>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span style={{
      width: 6, height: 6, borderRadius: 99, background: 'var(--accent-fg)',
      display: 'block', animation: `yz-pulse 1.1s ${delay} infinite ease-in-out`,
    }} />
  )
}
