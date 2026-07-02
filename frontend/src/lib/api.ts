const API_BASE = "";

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("auth_token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        error: { code: "unknown", message: response.statusText },
      }));
      throw { status: response.status, ...error };
    }

    return response.json();
  }

  // Auth
  async requestOTP(phone: string) {
    return this.request<{ message: string; expires_in: number }>(
      "/api/v1/auth/otp/request",
      { method: "POST", body: JSON.stringify({ phone }) }
    );
  }

  async verifyOTP(phone: string, otp: string) {
    return this.request<{ token: string; expires_in: number; is_new_user: boolean }>(
      "/api/v1/auth/otp/verify",
      { method: "POST", body: JSON.stringify({ phone, otp }) }
    );
  }

  async register(name: string, rera_id: string) {
    return this.request<{ cp_id: string; name: string; rera_id: string }>(
      "/api/v1/auth/register",
      { method: "POST", body: JSON.stringify({ name, rera_id }) }
    );
  }

  // Dashboard
  async getDashboardStats() {
    return this.request<{
      month: string;
      tours_shared: number;
      leads_generated: number;
      hot_leads: number;
      conversions: number;
    }>("/api/v1/dashboard/stats");
  }

  async getHotLeads(limit = 50, offset = 0) {
    return this.request<{
      leads: Array<{
        lead_id: string;
        buyer_name: string | null;
        buyer_phone: string | null;
        project_name: string;
        score: number;
        classification: string;
        signals: Array<{ type: string; points: number }>;
        created_at: string;
      }>;
      total: number;
    }>(`/api/v1/dashboard/hot-leads?limit=${limit}&offset=${offset}`);
  }

  async getLeadDetail(leadId: string) {
    return this.request<{
      lead_id: string;
      buyer_name: string | null;
      buyer_phone: string | null;
      project_name: string;
      score: number;
      classification: string;
      signals: Array<{ type: string; points: number }>;
      events: Array<{ type: string; timestamp: string; data: Record<string, unknown> }>;
    }>(`/api/v1/dashboard/leads/${leadId}`);
  }

  // Projects
  async getProjects() {
    return this.request<{
      projects: Array<{
        project_id: string;
        name: string;
        builder_name: string | null;
        location: string | null;
        unit_types: string[];
        tour_status: string;
      }>;
    }>("/api/v1/projects");
  }

  async createShareLink(projectId: string) {
    return this.request<{
      link_id: string;
      url: string;
      og_card: { title: string; description: string; image_url: string | null };
      whatsapp_message: string;
    }>(`/api/v1/projects/${projectId}/share-link`, { method: "POST" });
  }

  // Billing
  async getCreditPacks() {
    return this.request<
      Array<{ pack_type: string; name: string; amount_paise: number; credits: number }>
    >("/api/v1/billing/packs");
  }

  async purchaseCredits(packType: string) {
    return this.request<{
      order_id: string;
      amount_paise: number;
      credits: number;
      razorpay_key_id: string;
    }>("/api/v1/billing/purchase", {
      method: "POST",
      body: JSON.stringify({ pack_type: packType }),
    });
  }

  // Admin
  async createProject(data: {
    name: string;
    builder_id: string;
    location: string;
    unit_types: string[];
  }) {
    return this.request<{ project_id: string; status: string }>(
      "/api/v1/admin/projects",
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  async assignPartnership(cpId: string, projectId: string) {
    return this.request<{ partnership_id: string }>(
      "/api/v1/admin/partnerships",
      { method: "POST", body: JSON.stringify({ cp_id: cpId, project_id: projectId }) }
    );
  }

  async removePartnership(partnershipId: string) {
    return this.request<void>(
      `/api/v1/admin/partnerships/${partnershipId}`,
      { method: "DELETE" }
    );
  }

  async uploadAsset(projectId: string, file: File, assetType: string) {
    const token = this.getToken();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("asset_type", assetType);

    const response = await fetch(
      `${this.baseUrl}/api/v1/admin/projects/${projectId}/assets`,
      {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: { message: "Upload failed" } }));
      throw { status: response.status, ...error };
    }
    return response.json();
  }

  async triggerProcessing(projectId: string) {
    return this.request<{ job_id: string; status: string }>(
      `/api/v1/admin/projects/${projectId}/process`,
      { method: "POST" }
    );
  }
}

export const api = new APIClient(API_BASE);
