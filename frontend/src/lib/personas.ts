// Display metadata for the four fixed personas (visual identity only).
// The behavioural system prompts live on the backend and arrive in Phase 2.
export interface PersonaMeta {
  key: 'doom' | 'critic' | 'fan' | 'newbie'
  name: string
  glyph: string
  color: string // matches tailwind persona.* colours
  tagline: string
  watchesFor: string
}

export const PERSONAS: PersonaMeta[] = [
  {
    key: 'doom',
    name: 'The Doomscroller',
    glyph: '⚡',
    color: '#ff6b57',
    tagline: 'Gives you about three seconds.',
    watchesFor: 'Hooks, pacing, throat-clearing exposition.',
  },
  {
    key: 'critic',
    name: 'The Skeptical Critic',
    glyph: '⌕',
    color: '#a78bfa',
    tagline: 'Believes nothing until it is earned.',
    watchesFor: 'Clichés, weak logic, motives that do not add up.',
  },
  {
    key: 'fan',
    name: 'The Genre Superfan',
    glyph: '★',
    color: '#4ade80',
    tagline: 'Has read everything like this. Twice.',
    watchesFor: 'Tropes done well, lazy shortcuts, genre texture.',
  },
  {
    key: 'newbie',
    name: 'The Casual Newcomer',
    glyph: '◔',
    color: '#5eb8ff',
    tagline: 'Walked in without the backstory.',
    watchesFor: 'Unexplained references, jargon, confusing leaps.',
  },
]
