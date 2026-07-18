export interface HomeDeck {
  title: string;
  description: string | null;
  totalWordsCount: number;
  accuracy: number;
  updatedAt: string | null;
}

export interface HomeProgress {
  wordsExplored: number;
  weeklyAccuracy: number;
  currentStreakDays: number;
  totalStudyTimeSeconds: number;
}

export interface HomeWeeklyActivityDay {
  date: string;
  percent: number;
}

export interface HomeDashboard {
  decks: readonly HomeDeck[];
  progress: HomeProgress;
  weeklyActivity: readonly HomeWeeklyActivityDay[];
}
