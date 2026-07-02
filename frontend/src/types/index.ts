// Auth types
export interface OTPRequestResponse {
  message: string;
  expires_in: number;
}

export interface OTPVerifyResponse {
  token: string;
  expires_in: number;
  is_new_user: boolean;
}

export interface RegisterResponse {
  cp_id: string;
  name: string;
  rera_id: string;
}

// Dashboard types
export interface DashboardStats {
  month: string;
  tours_shared: number;
  leads_generated: number;
  hot_leads: number;
  conversions: number;
}

export interface SignalItem {
  type: string;
  points: number;
}

export interface LeadSummary {
  lead_id: string;
  buyer_name: string | null;
  buyer_phone: string | null;
  project_name: string;
  score: number;
  classification: string;
  signals: SignalItem[];
  created_at: string;
}

export interface HotLeadsResponse {
  leads: LeadSummary[];
  total: number;
}

export interface SessionEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface LeadDetail {
  lead_id: string;
  buyer_name: string | null;
  buyer_phone: string | null;
  project_name: string;
  score: number;
  classification: string;
  signals: SignalItem[];
  events: SessionEvent[];
}

// Project types
export interface ProjectSummary {
  project_id: string;
  name: string;
  builder_name: string | null;
  location: string | null;
  unit_types: string[];
  tour_status: string;
}

export interface OGCard {
  title: string;
  description: string;
  image_url: string | null;
}

export interface ShareLinkResponse {
  link_id: string;
  url: string;
  og_card: OGCard;
  whatsapp_message: string;
}

// Billing types
export interface PackInfo {
  pack_type: string;
  name: string;
  amount_paise: number;
  credits: number;
}

export interface PurchaseResponse {
  order_id: string;
  amount_paise: number;
  credits: number;
  razorpay_key_id: string;
}

// API Error
export interface APIError {
  error: {
    code: string;
    message: string;
    retry_after?: number;
    attempts_remaining?: number;
    unlock_at?: string;
    expected?: string;
  };
}
