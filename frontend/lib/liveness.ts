/** Active-liveness challenge copy and response types. */

export interface LivenessChallengeIssue {
  challenge: string;
  token: string;
  expires_in: number;
}

export interface LivenessChallengeResult {
  live: boolean;
  passed: boolean;
  challenge?: string;
  reason?: string;
  score?: number;
  rppg_score?: number;
  blink_score?: number;
  motion_score?: number;
}

interface ChallengeCopy {
  title: string;
  instruction: string;
}

const CHALLENGE_COPY: Record<string, ChallengeCopy> = {
  blink: {
    title: 'Blink twice',
    instruction: 'Look at the camera and blink twice slowly while the frames are captured.',
  },
  turn_left: {
    title: 'Turn your head left',
    instruction: 'Slowly turn your head to your left, then look back at the camera.',
  },
  turn_right: {
    title: 'Turn your head right',
    instruction: 'Slowly turn your head to your right, then look back at the camera.',
  },
};

/** Copy for a challenge name; unknown names get a neutral fallback. */
export function challengeCopy(challenge: string | null | undefined): ChallengeCopy {
  if (!challenge) {
    return { title: 'Liveness challenge', instruction: 'Follow the on-screen instruction, then continue.' };
  }
  return (
    CHALLENGE_COPY[challenge] ?? {
      title: 'Follow the challenge',
      instruction: 'Move your head or blink as instructed, then continue the scan.',
    }
  );
}
