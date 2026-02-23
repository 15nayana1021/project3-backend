## 1. 주식 목록 (GET /stocks)

- **설명**: 전체 기업 리스트 조회
- **Response Example**:

```json
[
  {
    "ticker": "RE001",
    "name": "삼송전자",
    "sector": "전자",
    "current_price": 70000
  }
]
```

## 2. 뉴스 목록 (GET /news)

- **설명**: 최신 뉴스 리스트 조회
- **Response Example**:

```json
[
  {
    "id": 1,
    "ticker": "상은테크놀로지",
    "title": "AI 기술 공개",
    "summary": "새로운 AI 알고리즘을...",
    "sentiment": "positive",
    "impact_score": 90,
    "published_at": "2026-02-10 09:18:11"
  }
]
```

## 3. 내 자산 정보 (GET /users/me/portfolio)

- **설명**: 사용자의 현금 잔고 및 보유 주식 현황
- **Response Example**:

```json
{
  "name": "Agent_104",
  "cash_balance": 100000.0,
  "total_asset_value": 120000.0,
  "portfolio": [
    {
      "ticker": "RE001",
      "quantity": 10,
      "current_price": 20.0,
      "profit_rate": 5.0
    }
  ]
}
```

## 4. 주식 주문 (POST /api/trade/order)

- **설명**: 주식 매수 및 매도 주문 요청
- **Endpoint**: `POST /api/trade/order`
- **Request Body Example**:

```json
{
  "ticker": "RE001",
  "side": "BUY",
  "quantity": 10,
  "price": 70000,
  "order_type": "LIMIT"
}
```
