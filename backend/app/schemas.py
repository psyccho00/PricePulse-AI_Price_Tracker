from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime

# ==========================================
# Price History Schemas
# ==========================================
class PriceHistoryBase(BaseModel):
    price: float

class PriceHistoryCreate(PriceHistoryBase):
    product_link_id: int

class PriceHistory(PriceHistoryBase):
    id: int
    product_link_id: int
    scraped_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# Product Link Schemas
# ==========================================
class ProductLinkBase(BaseModel):
    url: str
    website: str
    current_price: Optional[float] = None
    currency: str = "INR"
    is_active: bool = True
    in_stock: bool = True
    image_url: Optional[str] = None

class ProductLinkCreate(BaseModel):
    product_id: int
    url: str
    website: str  # e.g., 'amazon', 'flipkart', 'myntra'
    current_price: Optional[float] = None

class ProductLinkUpdate(BaseModel):
    current_price: Optional[float] = None
    is_active: Optional[bool] = None

class ProductLink(ProductLinkBase):
    id: int
    product_id: int
    last_scraped_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# Alert Schemas
# ==========================================
class AlertBase(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    target_price: float = 0.0
    is_active: bool = True
    alert_type: str = "target_price"
    alert_condition_value: Optional[float] = None

class AlertCreate(BaseModel):
    product_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    target_price: float = 0.0
    alert_type: str = "target_price"
    alert_condition_value: Optional[float] = None

class AlertUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    target_price: Optional[float] = None
    is_active: Optional[bool] = None
    alert_type: Optional[str] = None
    alert_condition_value: Optional[float] = None

class Alert(AlertBase):
    id: int
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# Product Schemas
# ==========================================
class ProductBase(BaseModel):
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    # When creating a product, we can optionally pass an initial tracked URL
    initial_url: Optional[str] = None
    initial_website: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    links: List[ProductLink] = []

    class Config:
        from_attributes = True

class ProductDetail(Product):
    alerts: List[Alert] = []
    
    class Config:
        from_attributes = True


# ==========================================
# Price Comparison Schemas
# ==========================================
class PlatformComparison(BaseModel):
    platform: str
    price: Optional[float] = None
    url: str
    in_stock: bool
    is_best_deal: bool
    savings_vs_this: float
    image_url: Optional[str] = None
    percentage_difference: Optional[float] = None

class PriceComparisonResponse(BaseModel):
    product_id: int
    product_name: str
    comparisons: List[PlatformComparison]
    best_platform: Optional[str] = None
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    savings_amount: float
    percentage_spread: Optional[float] = None


# ==========================================
# Price History & Analytics Schemas (Phase 5)
# ==========================================
class PriceHistoryEntry(BaseModel):
    id: int
    product_link_id: int
    price: float
    scraped_at: datetime
    website: str

    class Config:
        from_attributes = True

class WebsiteAnalytics(BaseModel):
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    average_price: Optional[float] = None
    total_price_changes: int

class PriceAnalyticsResponse(BaseModel):
    product_id: int
    product_name: str
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    average_price: Optional[float] = None
    total_price_changes: int
    by_website: Dict[str, WebsiteAnalytics]

class TargetAnalysisResponse(BaseModel):
    product_id: int
    target_price: float
    dates_below_target: List[datetime]
    frequency: float  # Percentage of scrapes below target
    recommendation: str  # Buy Now, Wait, etc.


# ==========================================
# Phase 7 Offer & Payment Optimizer Schemas
# ==========================================
class OfferBase(BaseModel):
    bank: str
    card_type: str  # Credit, Debit, All
    discount_type: str  # Percentage, Flat
    discount_value: float
    min_purchase: float = 0.0
    max_discount: Optional[float] = None

class OfferCreate(OfferBase):
    product_link_id: int

class Offer(OfferBase):
    id: int
    product_link_id: int

    class Config:
        from_attributes = True

class PaymentOptimizationResponse(BaseModel):
    product_id: int
    product_name: str
    listed_price: Optional[float] = None
    best_platform: Optional[str] = None
    best_payment_method: Optional[str] = None
    final_effective_price: Optional[float] = None
    savings: float
    platform_prices: Dict[str, Optional[float]]
    platform_effective_prices: Dict[str, Optional[float]]

# ==========================================
# Phase 6 Prediction Schemas
# ==========================================
class PricePredictionResponse(BaseModel):
    product_id: int
    target_price: float
    current_price: Optional[float] = None
    predicted_price_7d: Optional[float] = None
    predicted_price_14d: Optional[float] = None
    predicted_price_30d: Optional[float] = None
    slope: float
    r_squared: float
    confidence: str  # High, Moderate, Low
    estimated_date_reached: Optional[datetime] = None
    recommendation: str  # Buy Now, Wait for Discount, Monitor Product
    rationale: str

    # New Phase 2 AI Intelligence fields
    ai_buy_score: Optional[int] = None
    star_rating: Optional[str] = None
    buy_score_reasons: Optional[List[str]] = None
    predicted_price_tomorrow: Optional[float] = None
    predicted_price_next_week: Optional[float] = None
    prediction_confidence_pct: Optional[float] = None
    prediction_confidence_explanation: Optional[str] = None
    smart_recommendation: Optional[str] = None
    smart_recommendation_reason: Optional[str] = None
    smart_recommendation_wait_days: Optional[str] = None
    target_probability_pct: Optional[float] = None
    target_probability_reasons: Optional[List[str]] = None
    estimated_wait_time_desc: Optional[str] = None
    historical_success_rate_pct: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_confidence_pct: Optional[float] = None

    # Deal Score fields (separate from AI Buy Score)
    deal_score: Optional[int] = None
    deal_status: Optional[str] = None  # "LOW", "TYPICAL", "HIGH"
    deal_explanation: Optional[str] = None
    price_percentile: Optional[float] = None

class ProductAISummaryEntry(BaseModel):
    product_id: int
    product_name: str
    ai_buy_score: int
    star_rating: str
    smart_recommendation: str
    current_price: Optional[float] = None
    target_price: Optional[float] = None

class PortfolioAISummaryResponse(BaseModel):
    best_product_to_buy: Optional[ProductAISummaryEntry] = None
    product_expected_to_drop_most: Optional[ProductAISummaryEntry] = None
    highest_potential_savings: Optional[ProductAISummaryEntry] = None
    highest_volatility: Optional[ProductAISummaryEntry] = None
    portfolio_ai_score: float
    average_buy_score: float

# ==========================================
# Phase 8 Scheduler Schemas
# ==========================================
class SchedulerStatusResponse(BaseModel):
    is_running: bool
    check_interval_minutes: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    active_jobs: int
    is_updating: bool = False

# ==========================================
# Phase 1: User & Authentication Schemas
# ==========================================
class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str

class UserResetPassword(BaseModel):
    token: str
    new_password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ForgotPasswordRequest(BaseModel):
    email: str


# ==========================================
# Shopping Intelligence Schemas
# ==========================================
class PriceDropResponse(BaseModel):
    product_id: int
    has_drop: bool
    current_price: Optional[float] = None
    previous_price: Optional[float] = None
    absolute_drop: Optional[float] = None
    percentage_drop: Optional[float] = None
    is_new_historical_low: bool = False
    historical_low: Optional[float] = None
    biggest_drop_60d: Optional[float] = None
    biggest_drop_60d_pct: Optional[float] = None
    drop_summary: Optional[str] = None

class ProductMatchCandidate(BaseModel):
    product_id: int
    product_name: str
    confidence: float
    match_reasons: List[str]
    websites: List[str]
    current_price: Optional[float] = None

class ProductMatchResponse(BaseModel):
    source_product_id: int
    source_product_name: str
    matches: List[ProductMatchCandidate]

