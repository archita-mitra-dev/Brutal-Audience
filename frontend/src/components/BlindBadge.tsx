/** States exactly what the audience was and was not told, so the claim is checkable. */
export default function BlindBadge({ blind }: { blind: boolean }) {
  return (
    <p className="max-w-2xl rounded-sm border border-ink-600 bg-ink-900/70 px-3 py-2 text-xs text-bone-500" role="note">
      <span className="mr-2 font-mono uppercase tracking-wider text-lab">{blind ? 'Blind audience test' : 'Not blind'}</span>
      {blind
        ? 'The readers were not shown your title or name, were given no explanation of what you meant, and only ever saw the text up to the segment they were on.'
        : 'The readers were shown your title. They still saw no author name or explanation, and only the text up to the segment they were on.'}
    </p>
  )
}
