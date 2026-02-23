const BASE_URL = "http://localhost:8000";

// 공통 Fetcher
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(
      `[Backend API Error] ${response.status}: ${response.statusText}`,
    );
  }
  return response.json();
}

// 1. 주식 시장 (Market)
export interface StockItem {
  ticker: string;
  name: string;
  sector: string;
  current_price: number;
}

// 전체 주식 목록 (GET /stocks)
export const fetchStockList = async () => {
  return request<StockItem[]>("/stocks");
};

// 종목 상세 조회 (GET /stocks/{ticker})
export const fetchStockDetail = async (ticker: string) => {
  return request<StockItem>(`/stocks/${ticker}`);
};

// 차트 데이터 (GET /stocks/{ticker}/chart)
export const fetchStockChart = async (
  ticker: string,
  period: string = "1d",
) => {
  return request<any[]>(`/stocks/${ticker}/chart?period=${period}`);
};

// 2. 뉴스 (News)

// 실제 DB 구조 반영
export interface NewsItem {
  id: number;
  ticker: string;
  title: string;
  summary: string;
  sentiment: string;
  impact_score: number;
  published_at: string;
}

export const fetchNewsList = async () => {
  return request<NewsItem[]>("/news");
};

// 3. 자산 및 주문 (User & Trade)
export interface PortfolioItem {
  ticker: string;
  quantity: number;
  current_price: number;
  profit_rate: number;
}

export interface MyPortfolioResponse {
  name: string;
  cash_balance: number;
  total_asset_value: number;
  portfolio: PortfolioItem[];
}

// 내 자산 조회 (GET /users/me/portfolio)
export const fetchMyPortfolio = async () => {
  return request<MyPortfolioResponse>("/users/me/portfolio");
};

// 4. 주식 주문

interface OrderRequest {
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  order_type: "LIMIT" | "MARKET";
}

// 매수 주문
export const placeBuyOrder = async (
  ticker: string,
  price: number,
  quantity: number,
) => {
  const payload: OrderRequest = {
    ticker: ticker,
    side: "BUY",
    quantity: quantity,
    price: price,
    order_type: "LIMIT",
  };

  return request("/api/trade/order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};

// 매도 주문
export const placeSellOrder = async (
  ticker: string,
  price: number,
  quantity: number,
) => {
  const payload: OrderRequest = {
    ticker: ticker,
    side: "SELL",
    quantity: quantity,
    price: price,
    order_type: "LIMIT",
  };

  return request("/api/trade/order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};
