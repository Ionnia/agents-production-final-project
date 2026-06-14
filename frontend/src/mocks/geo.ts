export const GEO: Record<string, { lat: number; lng: number }> = {
  'Москва': { lat: 55.7558, lng: 37.6173 },
  'Санкт-Петербург': { lat: 59.9311, lng: 30.3609 },
  'Сочи': { lat: 43.5855, lng: 39.7231 },
  'Париж': { lat: 48.8566, lng: 2.3522 },
  'Рим': { lat: 41.9028, lng: 12.4964 },
  'Флоренция': { lat: 43.7696, lng: 11.2558 },
  'Афины': { lat: 37.9838, lng: 23.7275 },
  'Санторини': { lat: 36.3932, lng: 25.4615 },
  'Токио': { lat: 35.6762, lng: 139.6503 },
  'Пекин': { lat: 39.9042, lng: 116.4074 },
  'Дели': { lat: 28.6139, lng: 77.2090 },
  'Нью-Йорк': { lat: 40.7128, lng: -74.0060 },
}
export const DEFAULT_GEO = { lat: 48.0, lng: 16.0 }
export function geo(city?: string) { return (city && GEO[city]) || DEFAULT_GEO }
