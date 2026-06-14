import type { components } from './schema'

type S = components['schemas']

export type User = S['User']
export type TokenBundle = S['TokenBundle']
export type RegisterRequest = S['RegisterRequest']
export type LoginRequest = S['LoginRequest']
export type LoginResponse = S['LoginResponse']
export type RegisterResponse = S['RegisterResponse']
export type AccessTokenResponse = S['AccessTokenResponse']

export type ChatRequest = S['ChatRequest']
export type ChatAccepted = S['ChatAccepted']
export type StreamTicket = S['StreamTicket']
export type CancelResponse = S['CancelResponse']

export type Message = S['Message']
export type ClarifyingQuestion = S['ClarifyingQuestion']
export type QuestionOption = S['QuestionOption']
export type MapPoint = S['MapPoint']

export type SessionSummary = S['SessionSummary']
export type SessionList = S['SessionList']
export type SessionDetail = S['SessionDetail']
export type GroupSummary = S['GroupSummary']
export type GroupList = S['GroupList']
export type Group = S['Group']
export type Member = S['Member']
export type Preference = S['Preference']
export type CreateGroupRequest = S['CreateGroupRequest']
export type GroupPreferences = S['GroupPreferences']

export type PlanStatus = S['PlanStatus']
export type PlanBuildStatus = S['PlanBuildStatus']
export type PlanSummary = S['PlanSummary']
export type PlanList = S['PlanList']
export type Plan = S['Plan']
export type PlanItems = S['PlanItems']
export type FlightSel = S['FlightSel']
export type HotelSel = S['HotelSel']
export type TourSel = S['TourSel']
export type PlanMap = S['PlanMap']
export type PlanCalendar = S['PlanCalendar']
export type CalendarEvent = S['CalendarEvent']
export type ModifyRequest = S['ModifyRequest']
export type ModifyAccepted = S['ModifyAccepted']
export type AddPoint = S['AddPoint']
export type ApiError = S['Error']

// SSE: discriminate on the event NAME (not a body field).
export type SseEvent =
  | { event: 'run_status'; data: S['RunStatusEvent'] }
  | { event: 'message_delta'; data: S['MessageDeltaEvent'] }
  | { event: 'message'; data: S['MessageEvent'] }
  | { event: 'clarifying_question'; data: S['ClarifyingQuestionEvent'] }
  | { event: 'plan_status'; data: S['PlanStatusEvent'] }
  | { event: 'map'; data: S['MapEvent'] }
  | { event: 'error'; data: S['ErrorEvent'] }
export type SseEventName = SseEvent['event']
