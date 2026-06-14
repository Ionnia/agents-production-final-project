// Russian display labels for the `PlanStatus` enum (building | ready | error | accepted | rejected).
const PLAN_STATUS_LABELS: Record<string, string> = {
  building: 'Готовится',
  ready: 'Готово',
  error: 'Ошибка',
  accepted: 'Принят',
  rejected: 'Отклонён',
}

export const planStatusLabel = (s: string): string => PLAN_STATUS_LABELS[s] ?? s
